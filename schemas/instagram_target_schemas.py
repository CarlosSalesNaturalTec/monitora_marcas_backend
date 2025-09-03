# /backend/schemas/instagram_target_schemas.py
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

# --- Monitored Profiles ---

class MonitoredProfileBase(BaseModel):
    username: str = Field(..., description="Nome de usuário do perfil no Instagram a ser monitorado.")
    type: Literal['parlamentar', 'concorrente', 'midia'] = Field(..., description="Tipo de perfil para categorização.")
    is_active: bool = Field(True, description="Flag para ativar ou desativar o monitoramento deste perfil.")

class MonitoredProfileCreate(MonitoredProfileBase):
    pass

class MonitoredProfile(MonitoredProfileBase):
    id: str = Field(..., description="ID do documento no Firestore (geralmente o próprio username).")
    last_scanned_at: Optional[datetime] = Field(None, description="Timestamp do último escaneamento completo do perfil.")
    
    class Config:
        orm_mode = True
        
class ProfileStatusUpdate(BaseModel):
    is_active: bool

# --- Monitored Hashtags ---

class MonitoredHashtagBase(BaseModel):
    hashtag: str = Field(..., description="Hashtag a ser monitorada (sem o '#').")
    is_active: bool = Field(True, description="Flag para ativar ou desativar o monitoramento desta hashtag.")

class MonitoredHashtagCreate(MonitoredHashtagBase):
    pass

class MonitoredHashtag(MonitoredHashtagBase):
    id: str = Field(..., description="ID do documento no Firestore (a própria hashtag).")
    last_scanned_at: Optional[datetime] = Field(None, description="Timestamp do último escaneamento da hashtag.")

    class Config:
        orm_mode = True

class HashtagStatusUpdate(BaseModel):
    is_active: bool
