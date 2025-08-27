from pydantic import BaseModel, Field
from typing import List, Optional, Any, Literal
from datetime import datetime, date
import hashlib

class MonitorResultItem(BaseModel):
    link: str
    displayLink: str
    title: str
    snippet: str
    htmlSnippet: str
    pagemap: Optional[dict[str, Any]] = None
    origin: str = "google_cse"
    status: str = "pending"
    
    # Gera um ID baseado no hash do link para evitar duplicatas
    def generate_id(self) -> str:
        return hashlib.sha256(self.link.encode('utf-8')).hexdigest()

class MonitorRun(BaseModel):
    id: Optional[str] = None
    search_terms_query: str
    search_group: str  # 'brand' ou 'competitors'
    search_type: Literal["relevante", "historico", "continuo"] = "relevante"
    total_results_found: int
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["in_progress", "completed", "failed"] = Field(default="in_progress")
    range_start: Optional[datetime] = None
    range_end: Optional[datetime] = None
    last_interruption_date: Optional[datetime] = None
    historical_run_start_date: Optional[date] = None
    origin: str = "google_cse"

class MonitorData(BaseModel):
    run_metadata: MonitorRun
    results: List[MonitorResultItem]

class LatestMonitorData(BaseModel):
    brand: Optional[MonitorData] = None
    competitors: Optional[MonitorData] = None

class HistoricalRunRequest(BaseModel):
    start_date: date

class HistoricalMonitorData(BaseModel):
    brand: List[MonitorData] = Field(default_factory=list)
    competitors: List[MonitorData] = Field(default_factory=list)

class MonitorLog(BaseModel):
    run_id: str
    search_group: str
    page: int
    results_count: int
    new_urls_saved: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    range_start: Optional[datetime] = None
    range_end: Optional[datetime] = None
    search_type: Optional[Literal["relevante", "historico", "continuo"]] = None
    origin: str = "google_cse"


# --- Schemas for Summary View ---

class RunSummary(BaseModel):
    """Resumo de uma única execução de monitoramento."""
    id: str
    search_group: str
    search_type: Literal["relevante", "historico", "continuo"]
    collected_at: datetime
    total_results_found: int
    search_terms_query: str
    range_start: Optional[datetime] = None

class RequestLog(BaseModel):
    """Representa um log de requisição individual."""
    run_id: str
    search_group: str
    page: int
    results_count: int
    timestamp: datetime
    search_type: Literal["relevante", "historico", "continuo"]
    origin: str

class MonitorSummary(BaseModel):
    """Agrega todos os dados de Requisições para o dashboard."""
    total_runs: int
    total_requests: int
    total_results_saved: int
    runs_by_type: dict[str, int]
    results_by_group: dict[str, int]
    latest_logs: List[RequestLog] = Field(default_factory=list)
    brand_search_query: Optional[str] = None
    competitors_search_query: Optional[str] = None

class HistoricalStatusResponse(BaseModel):
    is_running: bool = False
    last_processed_date: Optional[date] = None
    original_start_date: Optional[date] = None
    message: str

class UpdateHistoricalStartDateRequest(BaseModel):
    new_start_date: date

# --- Schemas for Unified Data View ---

class UnifiedMonitorResult(BaseModel):
    """Representa um item de resultado unificado com dados da sua execução."""
    run_id: str # ID da execução que encontrou este resultado
    
    # From MonitorResultItem
    link: str
    displayLink: str
    title: str
    snippet: str
    htmlSnippet: str
    status: str
    
    # From MonitorRun
    search_type: Literal["relevante", "historico", "continuo"]
    search_group: str
    collected_at: datetime
    range_start: Optional[datetime] = None
    range_end: Optional[datetime] = None

# --- Schema for System Status ---

class SystemStatus(BaseModel):
    is_monitoring_running: bool = False
    current_task: Optional[str] = None
    task_start_time: Optional[datetime] = None
    last_completion_time: Optional[datetime] = None
    message: Optional[str] = None
