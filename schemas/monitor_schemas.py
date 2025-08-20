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
    search_type: Literal["relevante", "historico"] = "relevante"
    total_results_found: int
    collected_at: datetime = Field(default_factory=datetime.utcnow)
    range_start: Optional[date] = None
    range_end: Optional[date] = None
    last_interruption_date: Optional[date] = None

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