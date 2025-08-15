from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from firebase_admin import auth

# Importa o módulo para garantir que o SDK seja inicializado
import firebase_admin_init

reusable_bearer = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(reusable_bearer)):
    """
    Dependência do FastAPI para verificar o token do Firebase ID.

    Extrai o token do cabeçalho de autorização, verifica-o e retorna
    o payload do usuário decodificado. Lança HTTPException em caso de erro.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token não fornecido",
        )
    
    try:
        # O token é o que vem depois de "Bearer "
        id_token = credentials.credentials
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except auth.InvalidIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de ID inválido",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro interno na verificação do token: {e}",
        )
