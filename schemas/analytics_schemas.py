# backend/schemas/analytics_schemas.py
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

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

class Entity(BaseModel):
    """Representa uma única entidade na nuvem de palavras."""
    text: str
    value: int

class Mention(BaseModel):
    """Representa uma única menção para a tabela de menções."""
    link: str
    title: str
    snippet: str
    publish_date: datetime
    sentiment: str
    sentiment_score: float

class MentionsResponse(BaseModel):
    """Schema de resposta para a lista paginada de menções."""
    total_pages: int
    mentions: List[Mention]
