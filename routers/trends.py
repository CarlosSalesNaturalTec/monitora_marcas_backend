from fastapi import APIRouter, HTTPException, Depends
from typing import List

from schemas.trends_schemas import TrendTerm, TrendTermCreate
from firebase_admin_init import db  # Importa a instância db diretamente
from auth import get_current_user

router = APIRouter()

# Dependência para exigir usuário administrador
async def get_admin_user(user: dict = Depends(get_current_user)):
    if not user.get("role") == "ADM":
        raise HTTPException(status_code=403, detail="Acesso de administrador necessário")
    return user

@router.post("/trends/terms", response_model=TrendTerm, status_code=201, dependencies=[Depends(get_admin_user)])
def create_trend_term(term: TrendTermCreate):
    """
    Cria um novo termo do Google Trends para monitorar.
    Requer privilégios de administrador.
    """
    term_data = term.dict()
    
    # Verifica se o termo já existe para evitar duplicatas
    docs = db.collection('trends_terms').where('term', '==', term_data['term']).limit(1).stream()
    if len(list(docs)) > 0:
        raise HTTPException(status_code=409, detail="O termo já existe")

    update_time, term_ref = db.collection('trends_terms').add(term_data)
    new_term_doc = term_ref.get()
    
    if new_term_doc.exists:
        return TrendTerm(id=new_term_doc.id, **new_term_doc.to_dict())
    else:
        raise HTTPException(status_code=500, detail="Falha ao criar o termo no banco de dados.")


@router.get("/trends/terms", response_model=List[TrendTerm], dependencies=[Depends(get_current_user)])
def get_all_trend_terms():
    """
    Recupera todos os termos monitorados do Google Trends.
    Requer usuário autenticado.
    """
    terms_ref = db.collection('trends_terms').order_by('term').stream()
    terms_list = [TrendTerm(id=doc.id, **doc.to_dict()) for doc in terms_ref]
    return terms_list

@router.delete("/trends/terms/{term_id}", status_code=204, dependencies=[Depends(get_admin_user)])
def delete_trend_term(term_id: str):
    """
    Deleta um termo do Google Trends pelo seu ID.
    Requer privilégios de administrador.
    """
    term_ref = db.collection('trends_terms').document(term_id)
    if not term_ref.get().exists:
        raise HTTPException(status_code=404, detail="Termo não encontrado")
    
    term_ref.delete()
    return {}
