from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore_v1.base_document import DocumentSnapshot
import requests
import os
from typing import List

from schemas.term_schemas import SearchTerms, PreviewResult, TermGroup
from auth import get_current_user, get_current_admin_user
from firebase_admin_init import db

router = APIRouter()

COLLECTION_NAME = "platform_config"
DOCUMENT_ID = "search_terms"

# --- Helper Function for Google Search ---

def _build_query_string(term_group: TermGroup) -> str:
    """Constrói a string de busca a partir de um grupo de termos."""
    main_and_synonyms = term_group.main_terms + term_group.synonyms
    
    # Une termos principais e sinônimos com "OR"
    query_parts = []
    if main_and_synonyms:
        or_part = " OR ".join(f'"{term}"' for term in main_and_synonyms)
        query_parts.append(f"({or_part})")
        
    # Adiciona termos de exclusão com "-"
    for term in term_group.excluded_terms:
        query_parts.append(f'-"{term}"')

    print(" ".join(query_parts))    

    return " ".join(query_parts)

def _perform_google_search(query: str) -> List[str]:
    """Executa a busca na API do Google CSE e retorna uma lista de URLs."""
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")
    
    if not api_key or not cse_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="As credenciais da API do Google (API Key e CSE ID) não estão configuradas no servidor."
        )
        
    if not query.strip():
        return []

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cse_id,
        "q": query,
        "sort": "date",  # Ordena por data
        "dateRestrict": "d1",  # Restringe a resultados dos últimos 1 dia
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        search_results = response.json()

        print(response.json())  # Log para depuração
        
        items = search_results.get("items", [])
        return [item.get("link", "") for item in items if "link" in item]
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Erro ao comunicar com a API do Google: {e}"
        )

# --- API Endpoints ---

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

@router.post("/terms/preview", response_model=PreviewResult)
def get_search_preview(
    terms: SearchTerms,
    current_admin_user: dict = Depends(get_current_admin_user)
):
    """
    Executa uma busca de preview com os termos fornecidos e retorna os resultados.
    Acessível apenas para administradores.
    """
    brand_query = _build_query_string(terms.brand)
    competitor_query = _build_query_string(terms.competitors)
    
    brand_urls = _perform_google_search(brand_query)
    competitor_urls = _perform_google_search(competitor_query)
    
    return PreviewResult(
        brand_results=brand_urls,
        competitor_results=competitor_urls
    )
