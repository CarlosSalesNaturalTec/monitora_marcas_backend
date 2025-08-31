from pydantic import BaseModel
from typing import Optional

class TrendTermBase(BaseModel):
    term: str
    is_active: bool = True

class TrendTermCreate(TrendTermBase):
    pass

class TrendTerm(TrendTermBase):
    id: str

    class Config:
        from_attributes = True
