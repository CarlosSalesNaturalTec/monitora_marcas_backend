from fastapi import APIRouter, Depends, HTTPException, status
import requests
import os
from typing import List, Dict, Any
from datetime import datetime
import hashlib
from google.api_core.exceptions import FailedPrecondition
from firebase_admin import firestore

from schemas.term_schemas import SearchTerms, TermGroup
from schemas.monitor_schemas import MonitorResultItem, MonitorRun, MonitorData, LatestMonitorData
from auth import get_current_user
from firebase_admin_init import db
from routers.terms import get_search_terms, _build_query_string

router = APIRouter()

# --- Helper Functions ---

def _perform_paginated_google_search(query: str) -> List[Dict[str, Any]]:
    """
    Executa a busca paginada na API do Google CSE, até um máximo de 10 páginas.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    
    if not api_key or not cse_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="As credenciais da API do Google (API Key e CSE ID) não estão configuradas."
        )
        
    if not query.strip():
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    all_items = []
    
    # O Google CSE permite até 100 resultados, 10 por página.
    # O parâmetro 'start' indica o índice do primeiro resultado (1, 11, 21, ...).
    for page in range(10):
        start_index = 1 + page * 10
        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "num": 10,
            "start": start_index,
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            search_results = response.json()
            
            items = search_results.get("items", [])
            if not items:
                # Interrompe a paginação se não houver mais resultados
                break
            
            all_items.extend(items)

        except requests.exceptions.RequestException as e:
            # Em caso de erro em uma das páginas, podemos decidir parar ou continuar.
            # Por simplicidade, paramos e lançamos uma exceção.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Erro ao comunicar com a API do Google na página {page + 1}: {e}"
            )
            
    return all_items

def _save_monitor_data(run_metadata: MonitorRun, results: List[MonitorResultItem]) -> str:
    """
    Salva os metadados da execução e os resultados da busca no Firestore.
    """
    try:
        # 1. Salva os metadados da execução para obter um ID
        run_ref = db.collection("monitor_runs").document()
        run_metadata.id = run_ref.id
        run_ref.set(run_metadata.dict())

        # 2. Salva cada resultado individualmente, usando o hash do link como ID do documento
        batch = db.batch()
        results_collection_ref = db.collection("monitor_results")
        
        for item_data in results:
            doc_id = item_data.generate_id()
            doc_ref = results_collection_ref.document(doc_id)
            
            # Adiciona o ID da execução (run) ao resultado antes de salvar
            result_with_run_id = item_data.dict()
            result_with_run_id["run_id"] = run_ref.id
            
            batch.set(doc_ref, result_with_run_id)
        
        batch.commit()
        
        return run_ref.id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar dados de monitoramento no Firestore: {e}"
        )

# --- API Endpoints ---

@router.post("/monitor/run", response_model=Dict[str, MonitorData], tags=["Monitor"])
def run_and_save_monitoring(current_user: dict = Depends(get_current_user)):
    """
    Inicia uma nova execução de monitoramento para 'brand' e 'competitors'.
    Busca os termos, realiza a pesquisa paginada no Google e salva os resultados no Firestore.
    """
    # 1. Obter os termos de pesquisa mais recentes
    search_terms: SearchTerms = get_search_terms(current_user)
    
    response_data = {}

    for group_name in ["brand", "competitors"]:
        term_group: TermGroup = getattr(search_terms, group_name)
        query_string = _build_query_string(term_group)
        
        if not query_string.strip():
            continue

        # 2. Realizar a busca paginada
        search_results_raw = _perform_paginated_google_search(query_string)
        
        # 3. Mapear os resultados para o schema Pydantic
        monitor_results = [
            MonitorResultItem(
                link=item.get("link", ""),
                displayLink=item.get("displayLink", ""),
                title=item.get("title", ""),
                snippet=item.get("snippet", ""),
                htmlSnippet=item.get("htmlSnippet", ""),
                pagemap=item.get("pagemap", {})
            )
            for item in search_results_raw if item.get("link")
        ]
        
        # 4. Criar os metadados da execução
        run_metadata = MonitorRun(
            search_terms_query=query_string,
            search_group=group_name,
            total_results_found=len(monitor_results)
        )
        
        # 5. Salvar tudo no Firestore
        run_id = _save_monitor_data(run_metadata, monitor_results)
        run_metadata.id = run_id # Adiciona o ID gerado ao objeto de metadados
        
        # 6. Montar a resposta
        response_data[group_name] = MonitorData(
            run_metadata=run_metadata,
            results=monitor_results
        )
        
    return response_data

@router.get("/monitor/latest", response_model=LatestMonitorData, tags=["Monitor"])
def get_latest_monitor_data(current_user: dict = Depends(get_current_user)):
    """
    Busca a última execução de monitoramento para 'brand' e 'competitors' e seus resultados.
    """
    latest_data = LatestMonitorData()

    for group_name in ["brand", "competitors"]:
        try:
            # 1. Encontra a última execução para o grupo especificado
            runs_query = db.collection("monitor_runs") \
                .where("search_group", "==", group_name) \
                .order_by("collected_at", direction=firestore.Query.DESCENDING) \
                .limit(1)
            
            run_docs = list(runs_query.stream())
            
            if not run_docs:
                continue

            latest_run_doc = run_docs[0]
            run_data = latest_run_doc.to_dict()
            run_data['id'] = latest_run_doc.id  # Garante que o ID do documento seja a fonte da verdade
            latest_run_data = MonitorRun(**run_data)
            
            # 2. Busca os resultados associados a essa execução
            results_query = db.collection("monitor_results") \
                .where("run_id", "==", latest_run_doc.id)
            
            result_docs = results_query.stream()
            
            results = [MonitorResultItem(**doc.to_dict()) for doc in result_docs]
            
            # 3. Monta o objeto de dados
            monitor_data = MonitorData(run_metadata=latest_run_data, results=results)
            setattr(latest_data, group_name, monitor_data)

        except FailedPrecondition as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=(
                    "Erro de pré-condição no Firestore. "
                    "Isso geralmente indica que um índice composto necessário não foi criado. "
                    "Verifique os logs do Firebase para o link de criação do índice. "
                    f"Detalhe do erro: {e}"
                )
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao buscar últimos dados para '{group_name}': {e}"
            )
            
    return latest_data
