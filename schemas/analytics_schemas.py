# backend/schemas/analytics_schemas.py
from pydantic import BaseModel, Field
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

# --- Schemas para a Aba 3: Inteligência de Google Trends ---

class RisingQueryItem(BaseModel):
    """Representa um item na resposta de 'rising queries'."""
    query: str = Field(..., description="O termo de busca em ascensão.")
    value: int = Field(..., description="O percentual de crescimento.")
    formatted_value: str = Field(..., description="Valor formatado do crescimento, ex: '+1,850%' ou 'Breakout'.")

class RisingQueriesResponse(BaseModel):
    """Schema de resposta para o endpoint de buscas em ascensão."""
    queries: List[RisingQueryItem]

class TrendsDataPoint(BaseModel):
    """Ponto de dados específico para a comparação de trends."""
    date: str
    value: int

class TrendsComparisonItem(BaseModel):
    """Representa a série temporal de interesse para um único termo."""
    term: str
    data: List[TrendsDataPoint]

class TrendsComparisonResponse(BaseModel):
    """Schema de resposta para o endpoint de comparação de interesse de busca."""
    comparison_data: List[TrendsComparisonItem]

# --- Schemas para a Aba 4: Análise de Sentimento ---

class SentimentDistributionItem(BaseModel):
    """Representa uma fatia no gráfico de distribuição de sentimento."""
    sentiment: str = Field(..., description="Categoria do sentimento (e.g., 'positivo', 'negativo', 'neutro').")
    count: int = Field(..., description="Número de menções com este sentimento.")

class SentimentDistributionResponse(BaseModel):
    """Schema de resposta para o endpoint de distribuição de sentimento."""
    distribution: List[SentimentDistributionItem]

class SentimentOverTimeDataPoint(BaseModel):
    """Contagem de sentimentos para um dia específico."""
    positive: int
    negative: int
    neutral: int

class SentimentOverTimeItem(BaseModel):
    """Representa a evolução do sentimento para um único dia."""
    date: str
    sentiments: SentimentOverTimeDataPoint

class SentimentOverTimeResponse(BaseModel):
    """Schema de resposta para o endpoint de evolução do sentimento no tempo."""
    over_time_data: List[SentimentOverTimeItem]
