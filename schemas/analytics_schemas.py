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
