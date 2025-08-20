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
    range_start: Optional[datetime] = None
    range_end: Optional[datetime] = None
    last_interruption_date: Optional[datetime] = None

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

class MonitorSummary(BaseModel):
    """Agrega todos os dados de resumo e logs para o dashboard."""
    total_runs: int
    total_requests: int
    total_results_saved: int
    runs_by_type: dict[str, int]
    results_by_group: dict[str, int]
    latest_runs: List[RunSummary] = Field(default_factory=list)
    latest_logs: List[RequestLog] = Field(default_factory=list)
