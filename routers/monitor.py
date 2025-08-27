from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
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
    RunSummary, RequestLog, UnifiedMonitorResult, HistoricalStatusResponse,
    UpdateHistoricalStartDateRequest, SystemStatus
)
from auth import get_current_user, get_current_admin_user
from firebase_admin_init import db
from routers.terms import get_search_terms, _build_query_string

router = APIRouter()

# --- Constantes ---
QUOTA_COLLECTION = "daily_quotas"
MAX_DAILY_REQUESTS = 100
SYSTEM_STATUS_DOC = "system_status"
PLATFORM_CONFIG_COL = "platform_config"

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
        doc_ref = db.collection(PLATFORM_CONFIG_COL).document("search_terms")
        doc = doc_ref.get()
        if doc.exists:
            return SearchTerms(**doc.to_dict())
        return SearchTerms()
    except Exception as e:
        print(f"CRITICAL: Erro ao buscar os termos de pesquisa: {e}")
        return SearchTerms()

def _log_request(run_id: str, search_group: str, page: int, results_count: int, new_urls_saved: int, search_type: str, date_for_log: Optional[date] = None):
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
            search_type=search_type
        )
        
        log_ref.set(log_data.dict())
    except Exception as e:
        print(f"Error logging request for run_id {run_id}: {e}")

def _get_historical_run_status() -> Tuple[Optional[str], Optional[date], Optional[date]]:
    """
    Busca o status da coleta histórica para determinar se pode ser continuada.
    
    Returns: 
        Tuple[Optional[str], Optional[date], Optional[date]]: 
        (ID do documento interrompido, data da interrupção, data de início original).
    """
    try:
        interrupt_query = db.collection("monitor_runs") \
            .where("search_type", "==", "historico") \
            .where("last_interruption_date", "!=", None) \
            .order_by("last_interruption_date", direction=firestore.Query.DESCENDING) \
            .limit(1)
        
        interrupt_docs = list(interrupt_query.stream())
        
        if interrupt_docs:
            doc = interrupt_docs[0]
            last_interrupt_doc = doc.to_dict()
            
            interruption_dt = last_interrupt_doc.get("last_interruption_date")
            original_start = last_interrupt_doc.get("historical_run_start_date")

            # Converte o tipo da data se necessário
            if isinstance(original_start, str):
                original_start = date.fromisoformat(original_start)
            elif isinstance(original_start, datetime):
                original_start = original_start.date()

            if interruption_dt and original_start:
                return doc.id, interruption_dt.date(), original_start

        return None, None, None
    except Exception as e:
        print(f"WARN: Não foi possível buscar o status da coleta histórica: {e}")
        return None, None, None

# --- Gerenciamento de Status do Sistema ---

def _update_system_status(is_running: bool, task: Optional[str] = None, message: Optional[str] = None):
    """Atualiza o documento de status do sistema no Firestore."""
    status_ref = db.collection(PLATFORM_CONFIG_COL).document(SYSTEM_STATUS_DOC)
    status_data = {
        "is_monitoring_running": is_running,
        "current_task": task if is_running else None,
        "message": message
    }
    if is_running:
        status_data["task_start_time"] = datetime.utcnow()
    else:
        status_data["last_completion_time"] = datetime.utcnow()
    
    final_data = {k: v for k, v in status_data.items() if v is not None}
    status_ref.set(final_data, merge=True)


# --- Tarefas de Background ---

def _task_run_continuous_monitoring():
    """Tarefa de background para a coleta contínua."""
    try:
        _update_system_status(True, "Coleta Contínua", "Coleta de dados em andamento.")
        
        api_key = os.getenv("GOOGLE_API_KEY")
        cse_id = os.getenv("GOOGLE_CSE_ID")
        if not api_key or not cse_id:
            raise Exception("Credenciais da API do Google não configuradas.")

        search_terms = _get_platform_search_terms()
        session = _create_session_with_retries()
        
        for group_name in ["brand", "competitors"]:
            term_group: TermGroup = getattr(search_terms, group_name)
            query_string = _build_query_string(term_group)
            if not query_string.strip():
                continue

            run_ref = db.collection("monitor_runs").document()
            run_id = run_ref.id
            total_new_urls_for_group = 0
            
            # Cria o registro da run com status "in_progress"
            today = date.today()
            start_of_day = datetime.combine(today, datetime.min.time())
            run_metadata = MonitorRun(
                id=run_id,
                search_terms_query=query_string,
                search_group=group_name,
                search_type="continuo",
                total_results_found=0, # Será atualizado no final
                range_start=start_of_day,
                range_end=start_of_day
            )
            run_ref.set(run_metadata.dict())

            for page in range(10):
                if _get_remaining_quota() <= 0:
                    break
                # ... (lógica de busca e salvamento idêntica à original)
                start_index = 1 + page * 10
                url = "https://www.googleapis.com/customsearch/v1"
                params = {"key": api_key, "cx": cse_id, "q": query_string, "num": 10, "start": start_index, "dateRestrict": "d1"}
                response = session.get(url, params=params, timeout=(3.05, 10))
                _increment_quota(1)
                response.raise_for_status()
                search_results = response.json()
                items_raw = search_results.get("items", [])
                if not items_raw:
                    _log_request(run_id, group_name, page + 1, 0, 0, search_type="continuo")
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
                _log_request(run_id, group_name, page + 1, len(items_raw), new_urls_saved_count, search_type="continuo")

            # Atualiza a run com o total e o status "completed"
            run_ref.update({
                "total_results_found": total_new_urls_for_group,
                "status": "completed"
            })
            
    except Exception as e:
        print(f"ERRO na tarefa de coleta contínua: {e}")
        _update_system_status(False, "Coleta Contínua", f"Falha na coleta contínua: {e}")
    finally:
        _update_system_status(False, "Coleta Contínua", "Coleta contínua finalizada.")


def _task_run_initial_monitoring(start_date_iso: str):
    """Tarefa de background para a coleta inicial (relevante + histórica)."""
    try:
        _update_system_status(True, "Coleta Inicial", "Coleta de dados em andamento.")
        search_terms = _get_platform_search_terms()
        session = _create_session_with_retries()
        
        # Etapa 1: Coleta Relevante
        for group_name in ["brand", "competitors"]:
            # ... (lógica idêntica à original, mas salvando runs com status)
            remaining_quota = _get_remaining_quota()
            if remaining_quota == 0: break
            pages_to_fetch = min(10, remaining_quota)
            term_group: TermGroup = getattr(search_terms, group_name)
            query_string = _build_query_string(term_group)
            if not query_string.strip(): continue
            
            run_ref = db.collection("monitor_runs").document()
            search_results_raw, requests_made = _perform_paginated_google_search(session, query_string, pages_to_fetch, run_ref.id, group_name, "relevante")
            _increment_quota(requests_made)
            monitor_results = [MonitorResultItem(**item) for item in search_results_raw if item.get("link")]
            
            run_metadata = MonitorRun(
                search_terms_query=query_string,
                search_group=group_name,
                search_type="relevante",
                total_results_found=len(monitor_results)
            )
            saved_run_id = _save_monitor_data(run_metadata, monitor_results, run_id=run_ref.id)
            db.collection("monitor_runs").document(saved_run_id).update({"status": "completed"})

        # Etapa 2: Coleta Histórica
        start_date = date.fromisoformat(start_date_iso)
        end_date = date.today() - timedelta(days=1)
        
        if start_date <= end_date:
            current_date = end_date
            last_saved_run_id = None
            interrupted = False
            while current_date >= start_date and not interrupted:
                for group_name in ["brand", "competitors"]:
                    # ... (lógica idêntica à original, mas salvando runs com status)
                    remaining_quota = _get_remaining_quota()
                    if remaining_quota == 0:
                        interrupted = True
                        break
                    pages_to_fetch = min(10, remaining_quota)
                    term_group: TermGroup = getattr(search_terms, group_name)
                    query_string = _build_query_string(term_group)
                    date_range = {"start": current_date, "end": current_date}
                    
                    run_ref = db.collection("monitor_runs").document()
                    search_results_raw = []
                    if query_string.strip():
                        search_results_raw, requests_made = _perform_paginated_google_search(session, query_string, pages_to_fetch, run_ref.id, group_name, "historico", date_range)
                        _increment_quota(requests_made)
                    
                    monitor_results = [MonitorResultItem(**item) for item in search_results_raw if item.get("link")]
                    start_of_current_date = datetime.combine(current_date, datetime.min.time())
                    run_metadata = MonitorRun(
                        search_terms_query=query_string, search_group=group_name, search_type="historico",
                        total_results_found=len(monitor_results), range_start=start_of_current_date,
                        range_end=start_of_current_date, historical_run_start_date=start_date
                    )
                    saved_run_id = _save_monitor_data(run_metadata, monitor_results, run_id=run_ref.id)
                    db.collection("monitor_runs").document(saved_run_id).update({"status": "completed"})
                    last_saved_run_id = saved_run_id

                if not interrupted:
                    current_date -= timedelta(days=1)

            if interrupted and last_saved_run_id:
                interruption_datetime = datetime.combine(current_date, datetime.min.time())
                db.collection("monitor_runs").document(last_saved_run_id).update({"last_interruption_date": interruption_datetime})

    except Exception as e:
        print(f"ERRO na tarefa de coleta inicial: {e}")
        _update_system_status(False, "Coleta Inicial", f"Falha na coleta inicial: {e}")
    finally:
        _update_system_status(False, "Coleta Inicial", "Coleta inicial finalizada.")


def _task_run_scheduled_historical():
    """Tarefa de background para a coleta histórica agendada."""
    try:
        _update_system_status(True, "Coleta Histórica Agendada", "Coleta de dados em andamento.")
        search_terms = _get_platform_search_terms()
        session = _create_session_with_retries()
        interrupt_doc_id, last_interruption, original_start_date = _get_historical_run_status()

        if not (interrupt_doc_id and last_interruption and original_start_date):
            # ... (lógica de recuperação idêntica à original)
            oldest_run_query = db.collection("monitor_runs").where("search_type", "==", "historico").order_by("range_start", direction=firestore.Query.ASCENDING).limit(1)
            oldest_run_docs = list(oldest_run_query.stream())
            if not oldest_run_docs:
                _update_system_status(False, "Coleta Histórica Agendada", "Nenhuma coleta histórica para continuar.")
                return
            oldest_run_data = oldest_run_docs[0].to_dict()
            oldest_processed_dt = oldest_run_data.get("range_start")
            original_start_val = oldest_run_data.get("historical_run_start_date")
            if not oldest_processed_dt or not original_start_val:
                _update_system_status(False, "Coleta Histórica Agendada", "Dados de estado inválidos.")
                return
            oldest_processed_date = oldest_processed_dt.date()
            original_start_date = date.fromisoformat(original_start_val) if isinstance(original_start_val, str) else (original_start_val.date() if isinstance(original_start_val, datetime) else original_start_val)
            if oldest_processed_date > original_start_date:
                last_interruption = oldest_processed_date - timedelta(days=1)
            else:
                _update_system_status(False, "Coleta Histórica Agendada", "Coleta histórica concluída.")
                return

        if interrupt_doc_id:
            db.collection("monitor_runs").document(interrupt_doc_id).update({"last_interruption_date": None})

        end_date = last_interruption
        start_date = original_start_date
        if start_date > end_date:
            _update_system_status(False, "Coleta Histórica Agendada", "Coleta histórica já está atualizada.")
            return

        current_date = end_date
        last_saved_run_id = None
        interrupted = False
        while current_date >= start_date and not interrupted:
            for group_name in ["brand", "competitors"]:
                # ... (lógica idêntica à original, mas salvando runs com status)
                remaining_quota = _get_remaining_quota()
                if remaining_quota == 0:
                    interrupted = True
                    break
                pages_to_fetch = min(10, remaining_quota)
                term_group: TermGroup = getattr(search_terms, group_name)
                query_string = _build_query_string(term_group)
                date_range = {"start": current_date, "end": current_date}
                
                run_ref = db.collection("monitor_runs").document()
                search_results_raw = []
                if query_string.strip():
                    search_results_raw, requests_made = _perform_paginated_google_search(session, query_string, pages_to_fetch, run_ref.id, group_name, "historico", date_range)
                    _increment_quota(requests_made)
                
                monitor_results = [MonitorResultItem(**item) for item in search_results_raw if item.get("link")]
                start_of_current_date = datetime.combine(current_date, datetime.min.time())
                run_metadata = MonitorRun(
                    search_terms_query=query_string, search_group=group_name, search_type="historico",
                    total_results_found=len(monitor_results), range_start=start_of_current_date,
                    range_end=start_of_current_date, historical_run_start_date=original_start_date
                )
                saved_run_id = _save_monitor_data(run_metadata, monitor_results, run_id=run_ref.id)
                db.collection("monitor_runs").document(saved_run_id).update({"status": "completed"})
                last_saved_run_id = saved_run_id

            if not interrupted:
                current_date -= timedelta(days=1)

        if interrupted and last_saved_run_id:
            interruption_datetime = datetime.combine(current_date, datetime.min.time())
            db.collection("monitor_runs").document(last_saved_run_id).update({"last_interruption_date": interruption_datetime})

    except Exception as e:
        print(f"ERRO na tarefa de coleta histórica agendada: {e}")
        _update_system_status(False, "Coleta Histórica Agendada", f"Falha na coleta: {e}")
    finally:
        _update_system_status(False, "Coleta Histórica Agendada", "Coleta histórica agendada finalizada.")


# --- Continuous Monitoring Endpoint ---

@router.post("/monitor/run/continuous", status_code=status.HTTP_202_ACCEPTED, tags=["Monitor"])
def run_continuous_monitoring(background_tasks: BackgroundTasks):
    """
    Inicia uma execução de monitoramento contínuo (últimas 24h) em segundo plano.
    Projetado para ser acionado por um scheduler (ex: Google Cloud Scheduler).
    """
    background_tasks.add_task(_task_run_continuous_monitoring)
    return {"message": "Coleta contínua iniciada em segundo plano."}

# --- Auxiliar de Busca do Google ---

def _perform_paginated_google_search(
    session: requests.Session,
    query: str, 
    pages_to_fetch: int,
    run_id: str,
    search_group: str,
    search_type: str,
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
                date_for_log=current_day_for_log,
                search_type=search_type
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
    run_ref = db.collection("monitor_runs").document(run_id) if run_id else db.collection("monitor_runs").document()
    try:
        run_metadata.id = run_ref.id
        
        run_dict = run_metadata.dict()
        if 'historical_run_start_date' in run_dict and isinstance(run_dict['historical_run_start_date'], date):
            run_dict['historical_run_start_date'] = run_dict['historical_run_start_date'].isoformat()

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
        run_ref.update({"status": "failed"})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar os dados de monitoramento no Firestore: {e}"
        )

# --- Endpoints da API ---

@router.post("/monitor/run", response_model=Dict[str, str], tags=["Monitor"], status_code=status.HTTP_202_ACCEPTED)
def run_initial_monitoring(
    request: HistoricalRunRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user)
):
    """
    Inicia a primeira execução de monitoramento em segundo plano.
    """
    status_doc = db.collection(PLATFORM_CONFIG_COL).document(SYSTEM_STATUS_DOC).get()
    if status_doc.exists and status_doc.to_dict().get("is_monitoring_running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Uma tarefa de monitoramento já está em andamento."
        )

    has_data = next(db.collection("monitor_runs").limit(1).stream(), None)
    if has_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A coleta de dados já foi iniciada. Para recomeçar, todos os dados devem ser limpos."
        )

    background_tasks.add_task(_task_run_initial_monitoring, request.start_date.isoformat())
    
    return {"message": "A coleta de dados inicial foi iniciada em segundo plano."}


@router.post("/monitor/run/historical-scheduled", status_code=status.HTTP_202_ACCEPTED, tags=["Monitor"])
def run_scheduled_historical_monitoring(background_tasks: BackgroundTasks):
    """
    Continua a execução da coleta de dados históricos em segundo plano.
    """
    background_tasks.add_task(_task_run_scheduled_historical)
    return {"message": "Coleta histórica agendada iniciada em segundo plano."}


@router.get("/monitor/system-status", response_model=SystemStatus, tags=["Monitor"])
def get_system_status(current_user: dict = Depends(get_current_user)):
    """Retorna o status atual do sistema de monitoramento."""
    try:
        doc_ref = db.collection(PLATFORM_CONFIG_COL).document(SYSTEM_STATUS_DOC)
        doc = doc_ref.get()
        if doc.exists:
            return SystemStatus(**doc.to_dict())
        return SystemStatus() # Retorna o padrão se não existir
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar status: {e}")


@router.get("/monitor/historical-status", response_model=HistoricalStatusResponse, tags=["Monitor"])
def get_historical_collection_status(current_user: dict = Depends(get_current_user)):
    """
    Verifica o status da coleta de dados históricos.
    """
    # 1. Check for an active interruption (means it's paused mid-day)
    _, last_interruption, original_start_from_interrupt = _get_historical_run_status()

    if last_interruption and original_start_from_interrupt:
        last_processed = last_interruption + timedelta(days=1)
        return HistoricalStatusResponse(
            is_running=True,
            last_processed_date=last_processed,
            original_start_date=original_start_from_interrupt,
            message=f"Busca histórica em andamento, pausada por limite de requisições. O sistema continuará a busca a partir de {last_interruption.strftime('%d/%m/%Y')}."
        )

    # 2. If no interruption, check the overall progress
    # Find the earliest date processed by a historical run
    oldest_run_query = db.collection("monitor_runs") \
        .where("search_type", "==", "historico") \
        .order_by("range_start", direction=firestore.Query.ASCENDING) \
        .limit(1)
    
    oldest_run_docs = list(oldest_run_query.stream())

    if not oldest_run_docs:
        # No historical runs found at all
        return HistoricalStatusResponse(message="A coleta de dados históricos ainda não foi iniciada.")

    # We have historical runs, let's check their status
    oldest_run_data = oldest_run_docs[0].to_dict()
    
    oldest_processed_date_dt = oldest_run_data.get("range_start")
    if not oldest_processed_date_dt:
         return HistoricalStatusResponse(message="Erro: registro histórico encontrado sem data de início.")

    oldest_processed_date = oldest_processed_date_dt.date()

    original_start_date_val = oldest_run_data.get("historical_run_start_date")
    if not original_start_date_val:
        return HistoricalStatusResponse(message="Erro: registro histórico encontrado sem data de início original.")

    if isinstance(original_start_date_val, str):
        original_start_date = date.fromisoformat(original_start_date_val)
    elif isinstance(original_start_date_val, datetime):
        original_start_date = original_start_date_val.date()
    else:
        original_start_date = original_start_date_val

    # 3. Compare the oldest processed date with the target start date
    if oldest_processed_date <= original_start_date:
        # We've reached the target date, so it's complete
        return HistoricalStatusResponse(
            is_running=False,
            last_processed_date=oldest_processed_date,
            original_start_date=original_start_date,
            message="A busca por dados históricos foi concluída."
        )
    else:
        # It's still running, waiting for the next scheduled execution
        return HistoricalStatusResponse(
            is_running=True,
            last_processed_date=oldest_processed_date,
            original_start_date=original_start_date,
            message=f"Busca histórica em andamento. O processo é executado diariamente até atingir a data limite. Último dia processado: {oldest_processed_date.strftime('%d/%m/%Y')}."
        )



@router.post("/monitor/update-historical-start-date", status_code=status.HTTP_200_OK, tags=["Monitor"])
def update_historical_start_date(
    request: UpdateHistoricalStartDateRequest,
    current_user: dict = Depends(get_current_admin_user)
):
    """
    Atualiza a data de início da busca histórica e reinicia o processo de coleta
    para a nova data. (Acesso restrito a administradores)
    """
    try:
        historical_runs_query = db.collection("monitor_runs").where("search_type", "==", "historico").stream()
        
        run_docs = list(historical_runs_query)
        if not run_docs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nenhuma coleta histórica encontrada para atualizar.")

        # Batch update all historical runs with the new start date
        batch = db.batch()
        latest_run_doc = None
        latest_run_ts = datetime.min.replace(tzinfo=None)

        for doc in run_docs:
            run_data = doc.to_dict()
            # Firestore timestamps can be timezone-aware, ensure comparison is consistent
            collected_at_ts = run_data['collected_at'].replace(tzinfo=None)

            batch.update(doc.reference, {"historical_run_start_date": request.new_start_date.isoformat()})
            
            if collected_at_ts > latest_run_ts:
                latest_run_ts = collected_at_ts
                latest_run_doc = doc

        # Set the latest run to be interrupted to restart the scheduler
        if latest_run_doc:
            # Interruption date should be yesterday to have the scheduler pick it up and search backwards
            interruption_date = datetime.combine(date.today() - timedelta(days=1), datetime.min.time())
            batch.update(latest_run_doc.reference, {"last_interruption_date": interruption_date})

        batch.commit()        
        return {"message": f"Data de início da busca histórica atualizada para {request.new_start_date.isoformat()}. A coleta será reiniciada."}

    except Exception as e:
        print(f"Error updating historical start date: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao atualizar a data de início histórica: {e}"
        )


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
        total_requests_query = db.collection("monitor_logs").count()
        total_requests = total_requests_query.get()[0][0].value

        runs_by_type = {"relevante": 0, "historico": 0, "continuo": 0}
        for run in all_runs:
            if run.search_type in runs_by_type:
                runs_by_type[run.search_type] += 1

        # 5. Find the latest search queries for brand and competitors
        all_runs.sort(key=lambda r: r.collected_at, reverse=True)
        brand_query = None
        competitors_query = None
        for run in all_runs:
            if not brand_query and run.search_group == 'brand' and run.search_terms_query:
                brand_query = run.search_terms_query
            if not competitors_query and run.search_group == 'competitors' and run.search_terms_query:
                competitors_query = run.search_terms_query
            if brand_query and competitors_query:
                break

        # 6. Prepare logs for the response
        latest_logs_summary = []
        for log in recent_logs:
            run_info = runs_map.get(log.run_id)
            if run_info:
                # Fallback for old logs that don't have search_type
                stype = log.search_type if log.search_type else run_info.search_type
                latest_logs_summary.append(
                    RequestLog(
                        run_id=log.run_id,
                        search_group=log.search_group,
                        page=log.page,
                        results_count=log.results_count,
                        timestamp=log.timestamp,
                        search_type=stype,
                        origin=log.origin
                    )
                )

        return MonitorSummary(
            total_runs=total_runs,
            total_requests=total_requests,
            total_results_saved=total_results_saved,
            runs_by_type=runs_by_type,
            results_by_group=results_by_group,
            latest_logs=latest_logs_summary,
            brand_search_query=brand_query,
            competitors_search_query=competitors_query,
        )

    except Exception as e:
        print(f"Error fetching monitor summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar o resumo do monitoramento: {e}"
        )


@router.get("/monitor/run/{run_id}", response_model=MonitorRun, tags=["Monitor"])
def get_monitor_run_details(run_id: str, current_user: dict = Depends(get_current_user)):
    """
    Busca os detalhes de uma única execução de monitoramento pelo seu ID.
    """
    try:
        run_ref = db.collection("monitor_runs").document(run_id)
        run_doc = run_ref.get()

        if not run_doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Execução de monitoramento não encontrada."
            )
        
        run_data = run_doc.to_dict()
        run_data['id'] = run_doc.id
        return MonitorRun(**run_data)

    except Exception as e:
        print(f"Error fetching monitor run details for {run_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar detalhes da execução: {e}"
        )


@router.get("/monitor/all-results", response_model=List[UnifiedMonitorResult], tags=["Monitor"])
def get_all_monitor_results(current_user: dict = Depends(get_current_user)):
    """
    Busca os últimos 200 resultados de monitoramento, unificando-os com os metadados
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
                run_id=run_id,
                link=result_data.get("link", ""),
                displayLink=result_data.get("displayLink", ""),
                title=result_data.get("title", ""),
                snippet=result_data.get("snippet", ""),
                htmlSnippet=result_data.get("htmlSnippet", ""),
                status=result_data.get("status", "pending"),
                search_type=run_info.search_type,
                search_group=run_info.search_group,
                collected_at=run_info.collected_at,
                range_start=run_info.range_start,
                range_end=run_info.range_end
            )
            unified_results.append(unified_item)
            
        # Ordena os resultados pela data do evento (range_start para histórico/contínuo, collected_at para relevante), do mais novo para o mais antigo
        unified_results.sort(key=lambda x: x.range_start if x.range_start else x.collected_at, reverse=True)
        
        return unified_results[:200]

    except Exception as e:
        print(f"Error fetching all monitor results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar todos os resultados do monitoramento: {e}"
        )


@router.get("/monitor/results-by-status/{status}", response_model=List[UnifiedMonitorResult], tags=["Monitor"])
def get_monitor_results_by_status(status: str, current_user: dict = Depends(get_current_user)):
    """
    Busca resultados de monitoramento filtrados por um status específico.
    """
    try:
        # 1. Validar o status para evitar queries indesejadas
        allowed_statuses = ["pending", "reprocess", "scraper_failed", "scraper_skipped", "relevance_failed"]
        if status not in allowed_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Status inválido. Use um dos seguintes: {', '.join(allowed_statuses)}"
            )

        # 2. Buscar todas as execuções e mapeá-las por ID para enriquecimento
        runs_ref = db.collection("monitor_runs").stream()
        runs_map = {doc.id: MonitorRun(**doc.to_dict()) for doc in runs_ref}

        # 3. Buscar resultados filtrando pelo status
        results_ref = db.collection("monitor_results").where("status", "==", status).limit(200).stream()
        
        unified_results = []
        for result_doc in results_ref:
            result_data = result_doc.to_dict()
            run_id = result_data.get("run_id")
            
            run_info = runs_map.get(run_id)
            if not run_info:
                continue # Pula resultados órfãos

            # Combina os dados do resultado com os da execução
            unified_item = UnifiedMonitorResult(
                run_id=run_id,
                link=result_data.get("link", ""),
                displayLink=result_data.get("displayLink", ""),
                title=result_data.get("title", ""),
                snippet=result_data.get("snippet", ""),
                htmlSnippet=result_data.get("htmlSnippet", ""),
                status=result_data.get("status", "pending"),
                search_type=run_info.search_type,
                search_group=run_info.search_group,
                collected_at=run_info.collected_at,
                range_start=run_info.range_start,
                range_end=run_info.range_end
            )
            unified_results.append(unified_item)
            
        # Ordena os resultados pela data do evento
        unified_results.sort(key=lambda x: x.range_start if x.range_start else x.collected_at, reverse=True)
        
        return unified_results

    except Exception as e:
        print(f"Error fetching monitor results by status '{status}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar resultados do monitoramento por status: {e}"
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
        QUOTA_COLLECTION,
        f"{PLATFORM_CONFIG_COL}/{SYSTEM_STATUS_DOC}" # Deleta o documento de status também
    ]
    
    total_docs_deleted = 0
    
    for collection_name in collections_to_delete:
        try:
            if "/" in collection_name: # Trata a exclusão de um documento específico
                db.document(collection_name).delete()
                print(f"Successfully deleted document '{collection_name}'.")
                total_docs_deleted += 1
            else:
                collection_ref = db.collection(collection_name)
                deleted_count = _delete_collection_in_batches(collection_ref, 200)
                print(f"Successfully deleted {deleted_count} documents from '{collection_name}'.")
                total_docs_deleted += deleted_count
        except Exception as e:
            print(f"Error deleting '{collection_name}': {e}")
            continue

    return {"message": f"Limpeza completa concluída. Total de {total_docs_deleted} documentos removidos."}
