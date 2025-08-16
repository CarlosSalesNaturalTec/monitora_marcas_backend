from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore_v1.base_document import DocumentSnapshot

from schemas.term_schemas import SearchTerms
from auth import get_current_user, get_current_admin_user
from firebase_admin_init import db

router = APIRouter()

COLLECTION_NAME = "platform_config"
DOCUMENT_ID = "search_terms"

@router.get("/terms", response_model=SearchTerms)
def get_search_terms(current_user: dict = Depends(get_current_user)):
    """
    Endpoint para buscar os termos de pesquisa da plataforma.
    Acessível para qualquer usuário autenticado.
    """
    try:
        doc_ref = db.collection(COLLECTION_NAME).document(DOCUMENT_ID)
        doc: DocumentSnapshot = doc_ref.get()

        if doc.exists:
            return SearchTerms(**doc.to_dict())
        
        # Se o documento não existir, retorna um objeto vazio
        return SearchTerms()
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar os termos no Firestore: {e}",
        )

@router.post("/terms", response_model=SearchTerms)
def save_search_terms(
    terms: SearchTerms,
    current_admin_user: dict = Depends(get_current_admin_user)
):
    """
    Endpoint para criar ou atualizar os termos de pesquisa da plataforma.
    Acessível apenas para usuários administradores.
    """
    try:
        doc_ref = db.collection(COLLECTION_NAME).document(DOCUMENT_ID)
        doc_ref.set(terms.dict())
        
        # Retorna os dados que acabaram de ser salvos
        return terms

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao salvar os termos no Firestore: {e}",
        )
