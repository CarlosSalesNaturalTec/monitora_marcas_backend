# backend/schemas/analytics_schemas.py
from pydantic import BaseModel
from typing import List, Optional

class DataPoint(BaseModel):
    """Representa um único ponto de dados em uma série temporal."""
    date: str
    value: int

class CombinedViewResponse(BaseModel):
    """Schema de resposta para o gráfico de correlação."""
    mentions_over_time: List[DataPoint]
    trends_over_time: List[DataPoint]

class KpiResponse(BaseModel):
    """Schema de resposta para os KPIs do dashboard principal."""
    total_mentions: int
    average_sentiment: float