from fastapi import APIRouter, Depends, HTTPException, status
import requests
import os
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date, timedelta
import hashlib
from google.api_core.exceptions import FailedPrecondition
from firebase_admin import firestore

from schemas.term_schemas import SearchTerms, TermGroup
from schemas.monitor_schemas import (
    MonitorResultItem, MonitorRun, MonitorData, LatestMonitorData, 
    HistoricalRunRequest, HistoricalMonitorData
)
from auth import get_current_user
from firebase_admin_init import db
from routers.terms import get_search_terms, _build_query_string

router = APIRouter()

# --- Constantes ---
QUOTA_COLLECTION = "daily_quotas"
MAX_DAILY_REQUESTS = 100

# --- Funções Auxiliares de Cota Diária ---

def _get_daily_quota_doc_ref():
    """Retorna a referência para o documento de cota do dia atual."""
    today_str = date.today().isoformat()
    return db.collection(QUOTA_COLLECTION).document(today_str)

def _get_remaining_quota() -> int:
    """Lê a cota de requisições restante para o dia."""
    doc_ref = _get_daily_quota_doc_ref()
    snapshot = doc_ref.get()
    if not snapshot.exists:
        return MAX_DAILY_REQUESTS
    
    count = snapshot.get("count")
    return max(0, MAX_DAILY_REQUESTS - count)

def _increment_quota(requests_made: int):
    """Incrementa a contagem diária de requisições."""
    if requests_made > 0:
        doc_ref = _get_daily_quota_doc_ref()
        doc_ref.set({"count": firestore.Increment(requests_made)}, merge=True)

# --- Auxiliar de Busca do Google ---

def _perform_paginated_google_search(
    query: str, 
    pages_to_fetch: int,
    date_range: Optional[Dict[str, date]] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Executa uma busca paginada na API do Google CSE e retorna os resultados
    junto com o número de requisições feitas.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    
    if not api_key or not cse_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="As credenciais da API do Google (API Key e CSE ID) não estão configuradas."
        )
        
    if not query.strip() or pages_to_fetch <= 0:
        return [], 0

    url = "https://www.googleapis.com/customsearch/v1"
    all_items = []
    requests_made = 0
    
    for page in range(pages_to_fetch):
        start_index = 1 + page * 10
        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "num": 10,
            "start": start_index,
        }
        
        if date_range and date_range.get("start") and date_range.get("end"):
            start_str = date_range["start"].strftime("%Y%m%d")
            end_str = date_range["end"].strftime("%Y%m%d")
            params["sort"] = f"date:r:{start_str}:{end_str}"
        
        try:
            response = requests.get(url, params=params)
            requests_made += 1
            response.raise_for_status()
            search_results = response.json()
            
            items = search_results.get("items", [])
            if not items:
                break
            
            all_items.extend(items)

        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Erro ao se comunicar com a API do Google na página {page + 1}: {e}"
            )
            
    return all_items, requests_made

# --- Auxiliar para Salvar Dados no Firestore ---

def _save_monitor_data(run_metadata: MonitorRun, results: List[MonitorResultItem]) -> str:
    """Salva os metadados da execução e os resultados da busca no Firestore."""
    try:
        run_ref = db.collection("monitor_runs").document()
        run_metadata.id = run_ref.id
        
        # Converte o modelo Pydantic para um dicionário
        run_dict = run_metadata.dict()
        
        # Converte objetos 'date' para 'datetime' antes de salvar
        for key, value in run_dict.items():
            if isinstance(value, date) and not isinstance(value, datetime):
                run_dict[key] = datetime.combine(value, datetime.min.time())

        run_ref.set(run_dict)

        batch = db.batch()
        results_collection_ref = db.collection("monitor_results")
        
        for item_data in results:
            doc_id = item_data.generate_id()
            doc_ref = results_collection_ref.document(doc_id)
            
            result_with_run_id = item_data.dict()
            result_with_run_id["run_id"] = run_ref.id
            batch.set(doc_ref, result_with_run_id)
        
        batch.commit()
        
        return run_ref.id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar os dados de monitoramento no Firestore: {e}"
        )

# --- Endpoints da API ---

@router.post("/monitor/run", response_model=Dict[str, MonitorData], tags=["Monitor"])
def run_and_save_monitoring(current_user: dict = Depends(get_current_user)):
    """
    Inicia uma nova execução de monitoramento 'relevante' para 'brand' e 'competitors'.
    Esta é a funcionalidade "Dados do Agora".
    """
    search_terms: SearchTerms = get_search_terms(current_user)
    response_data = {}
    total_requests_made = 0

    for group_name in ["brand", "competitors"]:
        remaining_quota = _get_remaining_quota()
        if remaining_quota == 0:
            break

        pages_to_fetch = min(10, remaining_quota)
        
        term_group: TermGroup = getattr(search_terms, group_name)
        query_string = _build_query_string(term_group)
        
        if not query_string.strip():
            continue

        search_results_raw, requests_made = _perform_paginated_google_search(query_string, pages_to_fetch)
        _increment_quota(requests_made)
        total_requests_made += requests_made
        
        monitor_results = [
            MonitorResultItem(**item) for item in search_results_raw if item.get("link")
        ]
        
        run_metadata = MonitorRun(
            search_terms_query=query_string,
            search_group=group_name,
            search_type="relevante",
            total_results_found=len(monitor_results)
        )
        
        run_id = _save_monitor_data(run_metadata, monitor_results)
        run_metadata.id = run_id
        
        response_data[group_name] = MonitorData(
            run_metadata=run_metadata,
            results=monitor_results
        )
    
    if total_requests_made == 0:
         raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Cota diária de requisições da API do Google excedida. Nenhum novo dado foi coletado."
        )

    return response_data

@router.post("/monitor/run/historical", tags=["Monitor"])
def run_historical_monitoring(
    request: HistoricalRunRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Inicia um preenchimento de dados históricos a partir de uma data de início.
    """
    search_terms: SearchTerms = get_search_terms(current_user)
    
    start_date = request.start_date
    end_date = date.today() - timedelta(days=1)
    
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A data de início não pode ser no futuro ou hoje."
        )

    current_date = start_date
    last_saved_run_id = None
    interrupted = False

    while current_date <= end_date:
        if interrupted:
            break

        for group_name in ["brand", "competitors"]:
            remaining_quota = _get_remaining_quota()
            if remaining_quota == 0:
                interrupted = True
                break

            pages_to_fetch = min(10, remaining_quota)
            
            term_group: TermGroup = getattr(search_terms, group_name)
            query_string = _build_query_string(term_group)

            if not query_string.strip():
                continue

            date_range = {"start": current_date, "end": current_date}
            
            search_results_raw, requests_made = _perform_paginated_google_search(
                query_string, pages_to_fetch, date_range
            )
            _increment_quota(requests_made)

            if not search_results_raw:
                continue

            monitor_results = [
                MonitorResultItem(**item) for item in search_results_raw if item.get("link")
            ]
            
            run_metadata = MonitorRun(
                search_terms_query=query_string,
                search_group=group_name,
                search_type="historico",
                total_results_found=len(monitor_results),
                range_start=current_date,
                range_end=current_date
            )
            
            run_id = _save_monitor_data(run_metadata, monitor_results)
            last_saved_run_id = run_id

        if not interrupted:
            current_date += timedelta(days=1)

    if interrupted and last_saved_run_id:
        interruption_datetime = datetime.combine(current_date, datetime.min.time())
        db.collection("monitor_runs").document(last_saved_run_id).update({
            "last_interruption_date": interruption_datetime
        })
        return {"message": f"Coleta histórica parcial concluída. Limite de requisições atingido. Você pode continuar a partir de {current_date.isoformat()} mais tarde."}

    return {"message": "Coleta histórica concluída com sucesso."}


@router.get("/monitor/latest", response_model=LatestMonitorData, tags=["Monitor"])
def get_latest_monitor_data(current_user: dict = Depends(get_current_user)):
    """
    Busca a última execução de monitoramento 'relevante' para 'brand' e 'competitors'.
    """
    latest_data = LatestMonitorData()

    for group_name in ["brand", "competitors"]:
        try:
            runs_query = db.collection("monitor_runs") \
                .where("search_group", "==", group_name) \
                .where("search_type", "==", "relevante") \
                .order_by("collected_at", direction=firestore.Query.DESCENDING) \
                .limit(1)
            
            run_docs = list(runs_query.stream())
            
            if not run_docs:
                continue

            latest_run_doc = run_docs[0]
            run_data = latest_run_doc.to_dict()
            run_data['id'] = latest_run_doc.id
            latest_run_data = MonitorRun(**run_data)
            
            results_query = db.collection("monitor_results").where("run_id", "==", latest_run_doc.id)
            result_docs = results_query.stream()
            results = [MonitorResultItem(**doc.to_dict()) for doc in result_docs]
            
            monitor_data = MonitorData(run_metadata=latest_run_data, results=results)
            setattr(latest_data, group_name, monitor_data)

        except FailedPrecondition as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Um índice do Firestore necessário está faltando. Verifique os logs do Firebase para um link de criação. Erro: {e}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erro ao buscar os últimos dados para '{group_name}': {e}"
            )
            
    return latest_data

@router.get("/monitor/historical", response_model=HistoricalMonitorData, tags=["Monitor"])
def get_historical_monitor_data(current_user: dict = Depends(get_current_user)):
    """
    Busca todas as execuções de monitoramento 'histórico' e seus resultados associados.
    """
    historical_data = HistoricalMonitorData()
    
    try:
        runs_query = db.collection("monitor_runs") \
            .where("search_type", "==", "historico") \
            .order_by("range_start", direction=firestore.Query.ASCENDING)
        
        all_run_docs = list(runs_query.stream())
        
        if not all_run_docs:
            return historical_data

        run_ids = [doc.id for doc in all_run_docs]
        all_results = {}

        for i in range(0, len(run_ids), 30):
            batch_ids = run_ids[i:i + 30]
            results_query = db.collection("monitor_results").where("run_id", "in", batch_ids)
            for doc in results_query.stream():
                result_data = doc.to_dict()
                run_id = result_data.get("run_id")
                if run_id not in all_results:
                    all_results[run_id] = []
                all_results[run_id].append(MonitorResultItem(**result_data))

        for run_doc in all_run_docs:
            run_data_dict = run_doc.to_dict()
            run_data_dict['id'] = run_doc.id
            run_data = MonitorRun(**run_data_dict)
            
            group = run_data.search_group
            results_for_run = all_results.get(run_doc.id, [])
            
            monitor_data = MonitorData(run_metadata=run_data, results=results_for_run)
            
            if group == "brand":
                historical_data.brand.append(monitor_data)
            elif group == "competitors":
                historical_data.competitors.append(monitor_data)

    except FailedPrecondition as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Um índice do Firestore necessário está faltando. Verifique os logs do Firebase para um link de criação. Erro: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar dados históricos: {e}"
        )
            
    return historical_data


@router.delete("/monitor/latest", status_code=status.HTTP_200_OK, tags=["Monitor"])
def delete_latest_monitor_data(current_user: dict = Depends(get_current_user)):
    """
    Encontra e exclui as últimas execuções de monitoramento 'relevante' e seus resultados.
    """
    runs_to_delete = []

    for group_name in ["brand", "competitors"]:
        try:
            runs_query = db.collection("monitor_runs") \
                .where("search_group", "==", group_name) \
                .where("search_type", "==", "relevante") \
                .order_by("collected_at", direction=firestore.Query.DESCENDING) \
                .limit(1)
            
            run_docs = list(runs_query.stream())
            if run_docs:
                runs_to_delete.append(run_docs[0])

        except Exception as e:
            print(f"Não foi possível buscar a última execução para '{group_name}': {e}")
            continue
    
    if not runs_to_delete:
        return {"message": "Nenhuma coleta de dados relevante para excluir."}

    batch = db.batch()
    deleted_count = 0

    for run_doc in runs_to_delete:
        run_id = run_doc.id
        
        results_query = db.collection("monitor_results").where("run_id", "==", run_id)
        result_docs = list(results_query.stream())
        
        for doc in result_docs:
            batch.delete(doc.reference)
        
        batch.delete(run_doc.reference)
        deleted_count += len(result_docs) + 1

    try:
        batch.commit()
        return {"message": f"Coleta de dados excluída com sucesso. {deleted_count} documentos removidos."}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao excluir dados do Firestore: {e}"
        )