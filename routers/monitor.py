from fastapi import APIRouter, Depends, HTTPException, status
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from typing import List, Dict, Any, Tuple, Optional
from datetime import datetime, date, timedelta
import hashlib
from google.api_core.exceptions import FailedPrecondition
from firebase_admin import firestore

from schemas.term_schemas import SearchTerms, TermGroup
from schemas.monitor_schemas import (
    MonitorResultItem, MonitorRun, MonitorData, LatestMonitorData, 
    HistoricalRunRequest, HistoricalMonitorData, MonitorLog, MonitorSummary, 
    RunSummary, RequestLog, UnifiedMonitorResult
)
from auth import get_current_user, get_current_admin_user
from firebase_admin_init import db
from routers.terms import get_search_terms, _build_query_string

router = APIRouter()

# --- Constantes ---
QUOTA_COLLECTION = "daily_quotas"
MAX_DAILY_REQUESTS = 100

# --- Configuração de Sessão com Retry ---

def _create_session_with_retries() -> requests.Session:
    """Cria uma sessão de requests com política de retry para robustez."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

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

# --- Helpers ---

def _get_platform_search_terms() -> SearchTerms:
    """Busca os termos de pesquisa da plataforma diretamente do Firestore."""
    try:
        doc_ref = db.collection("platform_config").document("search_terms")
        doc = doc_ref.get()
        if doc.exists:
            return SearchTerms(**doc.to_dict())
        return SearchTerms()
    except Exception as e:
        print(f"CRITICAL: Erro ao buscar os termos de pesquisa: {e}")
        return SearchTerms()

def _log_request(run_id: str, search_group: str, page: int, results_count: int, new_urls_saved: int, date_for_log: Optional[date] = None):
    """Salva um log de uma única requisição da API do Google."""
    try:
        log_ref = db.collection("monitor_logs").document()
        
        log_date = date_for_log if date_for_log else date.today()
        start_of_day = datetime.combine(log_date, datetime.min.time())

        log_data = MonitorLog(
            run_id=run_id,
            search_group=search_group,
            page=page,
            results_count=results_count,
            new_urls_saved=new_urls_saved,
            range_start=start_of_day,
            range_end=start_of_day,
        )
        
        log_ref.set(log_data.dict())
    except Exception as e:
        print(f"Error logging request for run_id {run_id}: {e}")

# --- Continuous Monitoring Endpoint ---

@router.post("/monitor/run/continuous", status_code=status.HTTP_200_OK, tags=["Monitor"])
def run_continuous_monitoring():
    """
    Inicia uma execução de monitoramento contínuo (últimas 24h).
    Projetado para ser acionado por um scheduler (ex: Google Cloud Scheduler).
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    
    if not api_key or not cse_id:
        print("CRITICAL: As credenciais da API do Google não estão configuradas.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Credenciais da API do Google não configuradas."
        )

    search_terms = _get_platform_search_terms()
    total_new_urls_all_groups = 0
    session = _create_session_with_retries()
    
    for group_name in ["brand", "competitors"]:
        term_group: TermGroup = getattr(search_terms, group_name)
        query_string = _build_query_string(term_group)

        if not query_string.strip():
            continue

        run_id = db.collection("monitor_runs").document().id
        total_new_urls_for_group = 0
        
        for page in range(10): # Paginação até 10 páginas
            if _get_remaining_quota() <= 0:
                print("INFO: Cota diária de requisições atingida.")
                break

            start_index = 1 + page * 10
            
            try:
                url = "https://www.googleapis.com/customsearch/v1"
                params = {
                    "key": api_key, "cx": cse_id, "q": query_string,
                    "num": 10, "start": start_index, "dateRestrict": "d1"
                }
                response = session.get(url, params=params, timeout=(3.05, 10))
                _increment_quota(1)
                response.raise_for_status()
                search_results = response.json()
                
                items_raw = search_results.get("items", [])
                
                if not items_raw:
                    _log_request(run_id, group_name, page + 1, 0, 0)
                    break

                results_page = [MonitorResultItem(**item) for item in items_raw if item.get("link")]
                doc_refs = [db.collection("monitor_results").document(item.generate_id()) for item in results_page]
                
                existing_docs = db.get_all(doc_refs)
                existing_ids = {doc.id for doc in existing_docs if doc.exists}

                new_items_to_save = [item for item in results_page if item.generate_id() not in existing_ids]

                if new_items_to_save:
                    batch = db.batch()
                    for item in new_items_to_save:
                        doc_ref = db.collection("monitor_results").document(item.generate_id())
                        item_dict = item.dict()
                        item_dict["run_id"] = run_id
                        item_dict["search_group"] = group_name
                        batch.set(doc_ref, item_dict)
                    batch.commit()
                
                new_urls_saved_count = len(new_items_to_save)
                total_new_urls_for_group += new_urls_saved_count
                
                _log_request(run_id, group_name, page + 1, len(items_raw), new_urls_saved_count)

            except requests.exceptions.RequestException as e:
                print(f"ERROR: Falha na requisição para o Google (página {page + 1}, grupo {group_name}): {e}")
                break

        today = date.today()
        start_of_day = datetime.combine(today, datetime.min.time())
        run_metadata = MonitorRun(
            id=run_id,
            search_terms_query=query_string,
            search_group=group_name,
            search_type="continuo",
            total_results_found=total_new_urls_for_group,
            range_start=start_of_day,
            range_end=start_of_day
        )
        
        db.collection("monitor_runs").document(run_id).set(run_metadata.dict())
        total_new_urls_all_groups += total_new_urls_for_group

    return {"message": f"Coleta contínua concluída. Total de {total_new_urls_all_groups} novas URLs salvas."}

# --- Auxiliar de Busca do Google ---

def _perform_paginated_google_search(
    session: requests.Session,
    query: str, 
    pages_to_fetch: int,
    run_id: str,
    search_group: str,
    date_range: Optional[Dict[str, date]] = None
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Executa uma busca paginada na API do Google CSE, registra cada requisição
    e retorna os resultados junto com o número de requisições feitas.
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
            "key": api_key, "cx": cse_id, "q": query,
            "num": 10, "start": start_index
        }
        
        current_day_for_log = date_range.get("start") if date_range else None

        if date_range and date_range.get("start") and date_range.get("end"):
            start_str = date_range["start"].strftime("%Y%m%d")
            end_str = date_range["end"].strftime("%Y%m%d")
            params["sort"] = f"date:r:{start_str}:{end_str}"
        
        try:
            response = session.get(url, params=params, timeout=(3.05, 10))
            requests_made += 1
            response.raise_for_status()
            search_results = response.json()
            
            items = search_results.get("items", [])
            
            _log_request(
                run_id=run_id,
                search_group=search_group,
                page=page + 1,
                results_count=len(items),
                new_urls_saved=len(items),
                date_for_log=current_day_for_log
            )

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

def _save_monitor_data(run_metadata: MonitorRun, results: List[MonitorResultItem], run_id: Optional[str] = None) -> str:
    """Salva os metadados da execução e os resultados da busca no Firestore."""
    try:
        run_ref = db.collection("monitor_runs").document(run_id) if run_id else db.collection("monitor_runs").document()
        run_metadata.id = run_ref.id
        
        run_dict = run_metadata.dict()
        run_ref.set(run_dict)

        if results:
            batch = db.batch()
            results_collection_ref = db.collection("monitor_results")
            
            for item_data in results:
                doc_id = item_data.generate_id()
                doc_ref = results_collection_ref.document(doc_id)
                
                result_with_run_id = item_data.dict()
                result_with_run_id["run_id"] = run_ref.id
                result_with_run_id["search_group"] = run_metadata.search_group
                batch.set(doc_ref, result_with_run_id)
            
            batch.commit()
        
        return run_ref.id
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar os dados de monitoramento no Firestore: {e}"
        )

# --- Endpoints da API ---

@router.post("/monitor/run", response_model=Dict[str, str], tags=["Monitor"])
def run_and_save_monitoring(
    request: HistoricalRunRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Inicia uma nova execução de monitoramento completa, executando a coleta 
    'relevante' (agora) e depois a 'histórica' a partir da data fornecida.
    A 'start_date' é obrigatória.
    """
    search_terms: SearchTerms = get_search_terms(current_user)
    session = _create_session_with_retries()
    
    # --- Etapa 1: Coleta de Dados Relevantes (do Agora) ---
    for group_name in ["brand", "competitors"]:
        remaining_quota = _get_remaining_quota()
        if remaining_quota == 0:
            break
        pages_to_fetch = min(10, remaining_quota)
        term_group: TermGroup = getattr(search_terms, group_name)
        query_string = _build_query_string(term_group)
        if not query_string.strip():
            continue
        run_id = db.collection("monitor_runs").document().id
        search_results_raw, requests_made = _perform_paginated_google_search(
            session, query_string, pages_to_fetch, run_id, group_name
        )
        _increment_quota(requests_made)
        monitor_results = [MonitorResultItem(**item) for item in search_results_raw if item.get("link")]
        run_metadata = MonitorRun(
            search_terms_query=query_string,
            search_group=group_name,
            search_type="relevante",
            total_results_found=len(monitor_results)
        )
        _save_monitor_data(run_metadata, monitor_results, run_id=run_id)

    # --- Etapa 2: Coleta de Dados Históricos ---
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

    while current_date <= end_date and not interrupted:
        for group_name in ["brand", "competitors"]:
            remaining_quota = _get_remaining_quota()
            if remaining_quota == 0:
                interrupted = True
                break
            pages_to_fetch = min(10, remaining_quota)
            term_group: TermGroup = getattr(search_terms, group_name)
            query_string = _build_query_string(term_group)
            date_range = {"start": current_date, "end": current_date}
            run_id = db.collection("monitor_runs").document().id
            search_results_raw = []
            if query_string.strip():
                search_results_raw, requests_made = _perform_paginated_google_search(
                    session, query_string, pages_to_fetch, run_id, group_name, date_range
                )
                _increment_quota(requests_made)
            monitor_results = [MonitorResultItem(**item) for item in search_results_raw if item.get("link")]
            start_of_current_date = datetime.combine(current_date, datetime.min.time())
            run_metadata = MonitorRun(
                search_terms_query=query_string,
                search_group=group_name,
                search_type="historico",
                total_results_found=len(monitor_results),
                range_start=start_of_current_date,
                range_end=start_of_current_date
            )
            _save_monitor_data(run_metadata, monitor_results, run_id=run_id)
            last_saved_run_id = run_id
        if not interrupted:
            current_date += timedelta(days=1)

    if interrupted and last_saved_run_id:
        interruption_datetime = datetime.combine(current_date, datetime.min.time())
        db.collection("monitor_runs").document(last_saved_run_id).update({"last_interruption_date": interruption_datetime})
        return {"message": f"Coleta concluída parcialmente. Limite de requisições atingido. Você pode continuar a partir de {current_date.isoformat()} mais tarde."}

    return {"message": "Coleta completa (relevante e histórica) concluída com sucesso."}


@router.get("/monitor/summary", response_model=MonitorSummary, tags=["Monitor"])
def get_monitor_summary(current_user: dict = Depends(get_current_user)):
    """
    Busca um resumo agregado e os logs recentes das atividades de monitoramento.
    Calcula as estatísticas iterando sobre os resultados para garantir consistência.
    """
    try:
        # 1. Fetch all runs and create a map for efficient lookup
        runs_ref = db.collection("monitor_runs").stream()
        all_runs = []
        runs_map = {}
        for doc in runs_ref:
            run_data = doc.to_dict()
            run_data['id'] = doc.id
            run = MonitorRun(**run_data)
            all_runs.append(run)
            runs_map[doc.id] = run

        # 2. Fetch recent logs
        logs_ref = db.collection("monitor_logs").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(100).stream()
        recent_logs = [MonitorLog(**doc.to_dict()) for doc in logs_ref]

        # 3. Calculate stats by iterating through results for accuracy
        results_ref = db.collection("monitor_results").stream()
        total_results_saved = 0
        results_by_group = {"brand": 0, "competitors": 0}
        for result_doc in results_ref:
            run_id = result_doc.get("run_id")
            run_info = runs_map.get(run_id)
            
            # This check handles orphaned results, making the count consistent
            if run_info:
                total_results_saved += 1
                if run_info.search_group in results_by_group:
                    results_by_group[run_info.search_group] += 1
        
        # 4. Get other stats
        total_runs = len(all_runs)
        total_requests = db.collection("monitor_logs").count().get()[0][0].value
        runs_by_type = {"relevante": 0, "historico": 0, "continuo": 0}
        for run in all_runs:
            if run.search_type in runs_by_type:
                runs_by_type[run.search_type] += 1

        # 5. Prepare latest runs and logs for the response
        all_runs.sort(key=lambda r: r.collected_at, reverse=True)
        latest_runs_data = all_runs[:50]

        latest_runs_summary = [
            RunSummary(
                id=run.id,
                search_group=run.search_group,
                search_type=run.search_type,
                collected_at=run.collected_at,
                total_results_found=run.total_results_found,
                search_terms_query=run.search_terms_query,
                range_start=run.range_start
            ) for run in latest_runs_data
        ]

        latest_logs_summary = [
            RequestLog(
                run_id=log.run_id,
                search_group=log.search_group,
                page=log.page,
                results_count=log.results_count,
                timestamp=log.timestamp
            ) for log in recent_logs
        ]

        return MonitorSummary(
            total_runs=total_runs,
            total_requests=total_requests,
            total_results_saved=total_results_saved,
            runs_by_type=runs_by_type,
            results_by_group=results_by_group,
            latest_runs=latest_runs_summary,
            latest_logs=latest_logs_summary,
        )

    except Exception as e:
        print(f"Error fetching monitor summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar o resumo do monitoramento: {e}"
        )


@router.get("/monitor/all-results", response_model=List[UnifiedMonitorResult], tags=["Monitor"])
def get_all_monitor_results(current_user: dict = Depends(get_current_user)):
    """
    Busca todos os resultados de monitoramento, unificando-os com os metadados
    de suas respectivas execuções (runs) para uma exibição consolidada.
    """
    try:
        # 1. Buscar todas as execuções e mapeá-las por ID
        runs_ref = db.collection("monitor_runs").stream()
        runs_map = {doc.id: MonitorRun(**doc.to_dict()) for doc in runs_ref}

        # 2. Buscar todos os resultados
        results_ref = db.collection("monitor_results").stream()
        
        unified_results = []
        for result_doc in results_ref:
            result_data = result_doc.to_dict()
            run_id = result_data.get("run_id")
            
            run_info = runs_map.get(run_id)
            if not run_info:
                continue # Pula resultados órfãos

            # Combina os dados do resultado com os da execução
            unified_item = UnifiedMonitorResult(
                link=result_data.get("link", ""),
                displayLink=result_data.get("displayLink", ""),
                title=result_data.get("title", ""),
                snippet=result_data.get("snippet", ""),
                htmlSnippet=result_data.get("htmlSnippet", ""),
                search_type=run_info.search_type,
                search_group=run_info.search_group,
                collected_at=run_info.collected_at,
                range_start=run_info.range_start,
                range_end=run_info.range_end
            )
            unified_results.append(unified_item)
            
        # Ordena os resultados pela data do evento (range_start para histórico/contínuo, collected_at para relevante), do mais novo para o mais antigo
        unified_results.sort(key=lambda x: x.range_start if x.range_start else x.collected_at, reverse=True)
        
        return unified_results

    except Exception as e:
        print(f"Error fetching all monitor results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar todos os resultados do monitoramento: {e}"
        )


def _delete_collection_in_batches(collection_ref, batch_size: int) -> int:
    """Exclui todos os documentos de uma coleção em lotes."""
    total_deleted = 0
    while True:
        docs = list(collection_ref.limit(batch_size).stream())
        if not docs:
            break

        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        
        batch.commit()
        
        total_deleted += len(docs)
    
    return total_deleted

@router.delete("/monitor/all-data", status_code=status.HTTP_200_OK, tags=["Monitor"])
def delete_all_monitor_data(current_user: dict = Depends(get_current_admin_user)):
    """
    Exclui TODOS os dados de monitoramento do Firestore, incluindo execuções,
    resultados, logs e cotas.
    Use com extremo cuidado.
    (Acesso restrito a administradores)
    """
    collections_to_delete = [
        "monitor_runs",
        "monitor_results",
        "monitor_logs",
        QUOTA_COLLECTION
    ]
    
    total_docs_deleted = 0
    
    for collection_name in collections_to_delete:
        try:
            collection_ref = db.collection(collection_name)
            deleted_count = _delete_collection_in_batches(collection_ref, 200)
            print(f"Successfully deleted {deleted_count} documents from '{collection_name}'.")
            total_docs_deleted += deleted_count
        except Exception as e:
            print(f"Error deleting collection '{collection_name}': {e}")
            # Continua para a próxima coleção mesmo em caso de erro
            continue

    return {"message": f"Limpeza completa concluída. Total de {total_docs_deleted} documentos removidos."}
