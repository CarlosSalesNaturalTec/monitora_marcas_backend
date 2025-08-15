from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import List, Optional
from firebase_admin import auth

from auth import get_current_user, get_current_admin_user

# --- Pydantic Models ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: str  # "ADM" ou "OPERADOR"

class UserUpdate(BaseModel):
    role: str # "ADM" ou "OPERADOR"

class UserResponse(BaseModel):
    uid: str
    email: str
    role: Optional[str] = None
    disabled: bool

# --- FastAPI App Initialization ---

app = FastAPI(
    title="API do Social Listening Platform",
    description="Backend para o sistema de monitoramento de marcas.",
    version="0.1.0",
)

origins = [
    "http://localhost:3000",
    "https://social-listening-frontend-270453017143.us-central1.run.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Public and General Endpoints ---

@app.get("/")
def read_root():
    return {"message": "Backend do Social Listening Platform está no ar!"}

@app.get("/users/me")
def read_current_user(current_user: dict = Depends(get_current_user)):
    """
    Retorna as informações do usuário logado, incluindo seu custom claim 'role'.
    """
    uid = current_user.get("uid")
    user_record = auth.get_user(uid)
    role = user_record.custom_claims.get("role") if user_record.custom_claims else None
    
    return {
        "uid": uid,
        "email": current_user.get("email"),
        "role": role
    }

# --- User Management Endpoints (Admin Only) ---

@app.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user_data: UserCreate, admin_user: dict = Depends(get_current_admin_user)):
    """
    Cria um novo usuário no Firebase Authentication e define sua permissão (role).
    (Acesso restrito a administradores)
    """
    if user_data.role not in ["ADM", "OPERADOR"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permissão (role) inválida. Use 'ADM' ou 'OPERADOR'."
        )
    try:
        new_user = auth.create_user(
            email=user_data.email,
            password=user_data.password
        )
        auth.set_custom_user_claims(new_user.uid, {'role': user_data.role})
        
        return UserResponse(
            uid=new_user.uid,
            email=new_user.email,
            role=user_data.role,
            disabled=new_user.disabled
        )
    except auth.EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"O email '{user_data.email}' já está em uso."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar usuário: {e}"
        )

@app.get("/users", response_model=List[UserResponse])
def list_users(admin_user: dict = Depends(get_current_admin_user)):
    """
    Lista todos os usuários do Firebase Authentication.
    (Acesso restrito a administradores)
    """
    users = []
    try:
        for user_record in auth.list_users().iterate_all():
            role = user_record.custom_claims.get("role") if user_record.custom_claims else None
            users.append(UserResponse(
                uid=user_record.uid,
                email=user_record.email,
                role=role,
                disabled=user_record.disabled
            ))
        return users
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao listar usuários: {e}"
        )

@app.put("/users/{uid}", response_model=UserResponse)
def update_user_role(uid: str, user_data: UserUpdate, admin_user: dict = Depends(get_current_admin_user)):
    """
    Atualiza a permissão (role) de um usuário específico.
    (Acesso restrito a administradores)
    """
    if user_data.role not in ["ADM", "OPERADOR"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Permissão (role) inválida. Use 'ADM' ou 'OPERADOR'."
        )
    try:
        auth.set_custom_user_claims(uid, {'role': user_data.role})
        updated_user = auth.get_user(uid)
        return UserResponse(
            uid=updated_user.uid,
            email=updated_user.email,
            role=updated_user.custom_claims.get("role"),
            disabled=updated_user.disabled
        )
    except auth.UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao atualizar usuário: {e}")

@app.delete("/users/{uid}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(uid: str, admin_user: dict = Depends(get_current_admin_user)):
    """
    Exclui um usuário do Firebase Authentication.
    (Acesso restrito a administradores)
    """
    try:
        auth.delete_user(uid)
        return
    except auth.UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao excluir usuário: {e}")
