from fastapi import APIRouter, Depends, HTTPException, status
from firebase_admin import auth

from auth import get_current_user, get_current_admin_user
from schemas.user_schemas import UserCreate, UserPasswordChange, UserDelete, UserResponse

router = APIRouter()

@router.get("/users/me", response_model=UserResponse)
def read_current_user(current_user: dict = Depends(get_current_user)):
    """
    Retorna as informações do usuário logado, incluindo seu custom claim 'role'.
    """
    uid = current_user.get("uid")
    try:
        user_record = auth.get_user(uid)
        role = user_record.custom_claims.get("role") if user_record.custom_claims else None
        return UserResponse(uid=uid, email=user_record.email, role=role)
    except auth.UserNotFoundError:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

# --- Admin User Management Endpoints ---

@router.post("/admin/create-user", response_model=UserResponse, status_code=status.HTTP_201_CREATED, tags=["Admin"])
def create_user_endpoint(user_data: UserCreate, admin_user: dict = Depends(get_current_admin_user)):
    """
    Cria um novo usuário com email, senha e permissão (role).
    (Acesso restrito a administradores)
    """
    try:
        new_user = auth.create_user(
            email=user_data.email,
            password=user_data.password
        )
        auth.set_custom_user_claims(new_user.uid, {'role': user_data.role})
        
        return UserResponse(
            uid=new_user.uid,
            email=new_user.email,
            role=user_data.role
        )
    except auth.EmailAlreadyExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"O email '{user_data.email}' já está em uso."
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao criar usuário: {e}"
        )

@router.post("/admin/change-password", status_code=status.HTTP_200_OK, tags=["Admin"])
def change_password_endpoint(request: UserPasswordChange, admin_user: dict = Depends(get_current_admin_user)):
    """
    Altera a senha de um usuário existente.
    (Acesso restrito a administradores)
    """
    try:
        user = auth.get_user_by_email(request.email)
        auth.update_user(user.uid, password=request.new_password)
        return {"message": f"Senha do usuário {request.email} alterada com sucesso."}
    except auth.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuário com email '{request.email}' não encontrado."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao alterar a senha: {e}"
        )

@router.post("/admin/delete-user", status_code=status.HTTP_200_OK, tags=["Admin"])
def delete_user_endpoint(request: UserDelete, admin_user: dict = Depends(get_current_admin_user)):
    """
    Exclui um usuário com base no email.
    (Acesso restrito a administradores)
    """
    try:
        user = auth.get_user_by_email(request.email)
        auth.delete_user(user.uid)
        return {"message": f"Usuário {request.email} excluído com sucesso."}
    except auth.UserNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuário com email '{request.email}' não encontrado."
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao excluir usuário: {e}"
        )
