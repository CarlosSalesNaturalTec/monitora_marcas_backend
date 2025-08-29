from pydantic import BaseModel
from typing import List, Dict

class SentimentSummary(BaseModel):
    name: str
    value: int

class SentimentOverTimePoint(BaseModel):
    date: str
    positivo: int
    negativo: int
    neutro: int

class Entity(BaseModel):
    text: str
    value: int

class EntityCloud(BaseModel):
    positive: List[Entity]
    negative: List[Entity]

class ActiveSource(BaseModel):
    source: str
    mentions: int

class ShareOfVoicePoint(BaseModel):
    date: str
    brand: int
    competitors: int

class SentimentComparisonItem(BaseModel):
    name: str
    positivo: int
    negativo: int
    neutro: int