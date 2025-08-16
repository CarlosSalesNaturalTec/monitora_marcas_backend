from pydantic import BaseModel, EmailStr, constr
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=6)
    role: str

    def __init__(self, **data):
        super().__init__(**data)
        if self.role not in ["ADM", "OPERADOR"]:
            raise ValueError("Permissão (role) inválida. Use 'ADM' ou 'OPERADOR'.")

class UserPasswordChange(BaseModel):
    email: EmailStr
    new_password: constr(min_length=6)

class UserDelete(BaseModel):
    email: EmailStr
    
class UserResponse(BaseModel):
    uid: str
    email: str
    role: Optional[str] = None
