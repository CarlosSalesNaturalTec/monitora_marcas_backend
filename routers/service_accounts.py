# /backend/routers/service_accounts.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List
import logging
import uuid
from datetime import datetime, timezone

from schemas.service_account_schemas import ServiceAccount, ServiceAccountCreate
from auth import get_current_user
from firebase_admin import firestore, auth
from google.cloud import secretmanager

router = APIRouter(
    prefix="/instagram/service-accounts",
    tags=["Instagram Service Accounts"],
    dependencies=[Depends(get_current_user)]
)

db = firestore.client()
secret_manager_client = secretmanager.SecretManagerServiceClient()
PROJECT_ID = "monitora-parlamentar-elmar" # Substituir por variável de ambiente no futuro

@router.post("/", response_model=ServiceAccount, status_code=201)
async def create_service_account(
    username: str = Form(...), 
    session_file: UploadFile = File(...)
):
    """
    Cria uma nova conta de serviço do Instagram.
    - Faz upload do arquivo de sessão para o Google Secret Manager.
    - Salva os metadados da conta no Firestore.
    """
    logging.info(f"Recebida requisição para criar conta de serviço para: {username}")
    
    # 1. Verificar se a conta já existe
    accounts_ref = db.collection('service_accounts')
    existing_account = accounts_ref.where('username', '==', username).limit(1).get()
    if existing_account:
        raise HTTPException(status_code=409, detail=f"A conta de serviço '{username}' já existe.")

    # 2. Fazer upload do conteúdo do arquivo para o Secret Manager
    try:
        secret_id = f"instagram-session-{username}"
        
        # Criar o secret se não existir
        parent = f"projects/{PROJECT_ID}"
        try:
            secret_manager_client.create_secret(
                request={"parent": parent, "secret_id": secret_id, "secret": {"replication": {"automatic": {}}}}
            )
            logging.info(f"Secret '{secret_id}' criado no Secret Manager.")
        except Exception: # Idealmente, capturar google.api_core.exceptions.AlreadyExists
            logging.info(f"Secret '{secret_id}' já existe, adicionando nova versão.")

        # Adicionar uma nova versão ao secret com o payload do arquivo
        session_content = await session_file.read()
        secret_path = f"{parent}/secrets/{secret_id}"
        response = secret_manager_client.add_secret_version(
            request={"parent": secret_path, "payload": {"data": session_content}}
        )
        secret_version_path = response.name
        logging.info(f"Nova versão do secret criada: {secret_version_path}")

    except Exception as e:
        logging.error(f"Falha ao fazer upload da sessão para o Secret Manager: {e}")
        raise HTTPException(status_code=500, detail="Falha ao processar o arquivo de sessão.")

    # 3. Salvar os dados no Firestore
    try:
        doc_id = str(uuid.uuid4())
        account_data = {
            "username": username,
            "status": "active",
            "secret_manager_path": secret_version_path,
            "last_used_at": None,
            "created_at": datetime.now(timezone.utc)
        }
        accounts_ref.document(doc_id).set(account_data)
        
        # Adicionar o ID ao dicionário para retornar o objeto completo
        account_data["id"] = doc_id
        logging.info(f"Conta de serviço '{username}' salva no Firestore com ID {doc_id}.")
        
        return ServiceAccount(**account_data)

    except Exception as e:
        logging.error(f"Falha ao salvar a conta no Firestore: {e}")
        # Tentar deletar a versão do secret criada para consistência
        try:
            secret_manager_client.destroy_secret_version(request={"name": secret_version_path})
        except Exception as cleanup_error:
            logging.error(f"Falha ao limpar a versão do secret após erro: {cleanup_error}")
        raise HTTPException(status_code=500, detail="Falha ao salvar os dados da conta.")


@router.get("/", response_model=List[ServiceAccount])
async def get_all_service_accounts():
    """
    Lista todas as contas de serviço do Instagram cadastradas.
    """
    try:
        accounts_ref = db.collection('service_accounts').order_by('username')
        accounts = []
        for doc in accounts_ref.stream():
            account_data = doc.to_dict()
            account_data['id'] = doc.id
            accounts.append(ServiceAccount(**account_data))
        return accounts
    except Exception as e:
        logging.error(f"Erro ao buscar contas de serviço: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar contas de serviço.")

@router.post("/{account_id}/update-session", response_model=ServiceAccount)
async def update_service_account_session(
    account_id: str,
    session_file: UploadFile = File(...)
):
    """
    Atualiza o arquivo de sessão de uma conta de serviço existente.
    - Adiciona uma nova versão ao secret no Secret Manager.
    - Atualiza o caminho da versão e o status no Firestore.
    """
    logging.info(f"Recebida requisição para atualizar a sessão da conta ID: {account_id}")
    
    # 1. Buscar a conta no Firestore
    account_ref = db.collection('service_accounts').document(account_id)
    account_doc = account_ref.get()
    if not account_doc.exists:
        raise HTTPException(status_code=404, detail="Conta de serviço não encontrada.")
    
    account_data = account_doc.to_dict()
    username = account_data.get("username")
    secret_id = f"instagram-session-{username}"
    parent = f"projects/{PROJECT_ID}"
    secret_path = f"{parent}/secrets/{secret_id}"

    # 2. Adicionar nova versão do secret
    try:
        session_content = await session_file.read()
        response = secret_manager_client.add_secret_version(
            request={"parent": secret_path, "payload": {"data": session_content}}
        )
        new_secret_version_path = response.name
        logging.info(f"Nova versão de sessão criada para '{username}': {new_secret_version_path}")
    except Exception as e:
        logging.error(f"Falha ao atualizar a sessão no Secret Manager para '{username}': {e}")
        raise HTTPException(status_code=500, detail="Falha ao processar o novo arquivo de sessão.")

    # 3. Atualizar o documento no Firestore
    try:
        update_data = {
            "secret_manager_path": new_secret_version_path,
            "status": "active" # Reativa a conta
        }
        account_ref.update(update_data)
        
        # Carregar dados atualizados para o retorno
        updated_doc = account_ref.get().to_dict()
        updated_doc['id'] = account_id
        logging.info(f"Sessão da conta '{username}' (ID: {account_id}) atualizada no Firestore.")
        
        return ServiceAccount(**updated_doc)
    except Exception as e:
        logging.error(f"Falha ao atualizar a conta no Firestore após update de sessão: {e}")
        raise HTTPException(status_code=500, detail="Falha ao atualizar os dados da conta.")


@router.delete("/{account_id}", status_code=204)
async def delete_service_account(account_id: str):
    """
    Deleta uma conta de serviço.
    - ATENÇÃO: Esta ação não deleta o secret no Secret Manager, apenas o
      documento no Firestore para evitar perda de dados acidental. A limpeza
      de secrets órfãos deve ser um processo administrativo separado.
    """
    logging.info(f"Recebida requisição para deletar a conta ID: {account_id}")
    
    try:
        account_ref = db.collection('service_accounts').document(account_id)
        if not account_ref.get().exists:
            raise HTTPException(status_code=404, detail="Conta de serviço não encontrada.")
        
        account_ref.delete()
        logging.info(f"Conta de serviço com ID {account_id} deletada do Firestore.")
        
        return None # Retorno vazio para status 204
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Erro ao deletar conta de serviço {account_id}: {e}")
        raise HTTPException(status_code=500, detail="Erro ao deletar a conta de serviço.")