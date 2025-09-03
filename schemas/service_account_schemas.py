# /backend/schemas/service_account_schemas.py
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class ServiceAccountBase(BaseModel):
    username: str = Field(..., description="Nome de usuário da conta de serviço do Instagram.")
    
class ServiceAccountCreate(ServiceAccountBase):
    pass

class ServiceAccount(ServiceAccountBase):
    id: str = Field(..., description="ID do documento no Firestore.")
    status: str = Field(..., description="Status atual da conta (ex: active, session_expired).")
    secret_manager_path: Optional[str] = Field(None, description="Caminho completo para o secret no Google Secret Manager.")
    last_used_at: Optional[datetime] = Field(None, description="Timestamp do último uso em uma coleta.")
    created_at: datetime = Field(..., description="Timestamp de criação do registro.")

    class Config:
        from_attributes = True

class ServiceAccountList(BaseModel):
    accounts: list[ServiceAccount]
