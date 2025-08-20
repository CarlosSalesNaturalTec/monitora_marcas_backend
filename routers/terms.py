from fastapi import APIRouter, Depends, HTTPException, status
from google.cloud.firestore_v1.base_document import DocumentSnapshot
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import os
from typing import List

from schemas.term_schemas import SearchTerms, PreviewResult, TermGroup
from auth import get_current_user, get_current_admin_user
from firebase_admin_init import db

router = APIRouter()

COLLECTION_NAME = "platform_config"
DOCUMENT_ID = "search_terms"

# --- Helper Functions ---

def _create_session_with_retries() -> requests.Session:
    """Cria uma sessão de requests com política de retry para robustez."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def _build_query_string(term_group: TermGroup) -> str:
    """Constrói a string de busca a partir de um grupo de termos."""
    main_and_synonyms = term_group.main_terms + term_group.synonyms
    
    query_parts = []
    if main_and_synonyms:
        or_part = " OR ".join(f'"{term}"' for term in main_and_synonyms)
        query_parts.append(f"({or_part})")
        
    for term in term_group.excluded_terms:
        query_parts.append(f'-"{term}"')

    return " ".join(query_parts)

def _perform_google_search(query: str) -> List[dict]:
    """Executa a busca na API do Google CSE e retorna uma lista de dicionários com link e htmlSnippet."""
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
        "key": api_key, "cx": cse_id, "q": query, "num": 10
    }
    
    try:
        session = _create_session_with_retries()
        response = session.get(url, params=params, timeout=(3.05, 10))
        response.raise_for_status()
        search_results = response.json()
        
        items = search_results.get("items", [])
        return [
            {"link": item.get("link", ""), "htmlSnippet": item.get("htmlSnippet", "")}
            for item in items if "link" in item
        ]
        
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
