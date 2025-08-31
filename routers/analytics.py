# backend/routers/analytics.py
from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud import firestore
from typing import List, Optional
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import logging
import asyncio
import math

from schemas.analytics_schemas import (
    CombinedViewResponse,
    KpiResponse,
    DataPoint,
    Entity,
    Mention,
    MentionsResponse
)

# Configuração básica de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def get_db():
    """Função de dependência para obter a instância do Firestore Client."""
    return firestore.Client()

async def get_mentions_over_time(db: firestore.Client, search_group: str, start_date: datetime, end_date: datetime) -> List[DataPoint]:
    """Busca e agrega o volume de menções diárias."""
    query = db.collection('monitor_results') \
              .where('search_group', '==', search_group) \
              .where('publish_date', '>=', start_date) \
              .where('publish_date', '<=', end_date) \
              .where('status', '==', 'nlp_ok')
    
    docs = query.stream()
    
    daily_counts = defaultdict(int)
    for doc in docs:
        data = doc.to_dict()
        publish_date = data.get('publish_date')
        if publish_date:
            daily_counts[publish_date.strftime('%Y-%m-%d')] += 1
            
    # Preenche os dias sem menções com zero
    date_range = [start_date + timedelta(days=x) for x in range((end_date - start_date).days + 1)]
    results = []
    for day in date_range:
        date_str = day.strftime('%Y-%m-%d')
        results.append(DataPoint(date=date_str, value=daily_counts.get(date_str, 0)))
        
    return sorted(results, key=lambda x: x.date)

async def get_trends_over_time(db: firestore.Client, search_group: str, start_date: datetime, end_date: datetime) -> List[DataPoint]:
    """Busca e formata os dados de interesse de busca do Google Trends."""
    # Primeiro, busca os termos associados ao search_group
    terms_doc_ref = db.collection('search_terms').document('user_defined_terms')
    terms_doc = terms_doc_ref.get()
    if not terms_doc.exists:
        logger.warning(f"Documento de termos 'user_defined_terms' não encontrado.")
        return []
        
    terms_data = terms_doc.to_dict()
    # O search_group 'brand' corresponde a 'marca' e 'competitors' a 'concorrentes' no documento
    group_key = 'brand' if search_group == 'brand' else 'competitors'
    main_terms = terms_data.get(group_key, {}).get('main_terms', [])
    
    if not main_terms:
        logger.info(f"Nenhum termo principal encontrado para o grupo '{search_group}'.")
        return []

    # Por simplicidade, vamos usar o primeiro termo principal para a busca de trends.
    # Uma implementação mais avançada poderia agregar ou selecionar o mais relevante.
    target_term = main_terms[0]

    query = db.collection('google_trends_data') \
              .where('term', '==', target_term) \
              .where('type', '==', 'interest_over_time') \
              .order_by('created_at', direction=firestore.Query.DESCENDING) \
              .limit(1)

    docs = list(query.stream())
    
    if not docs:
        logger.info(f"Nenhum dado de Google Trends encontrado para o termo '{target_term}'.")
        return []
        
    trends_data = docs[0].to_dict().get('data', [])
    
    # Filtra os dados para o período solicitado e formata a resposta
    results = []
    for item in trends_data:
        # A data no Firestore pode ser string ou datetime
        item_date_str = item.get('date', '')
        if isinstance(item_date_str, datetime):
            item_date = item_date_str
        else:
            try:
                item_date = datetime.fromisoformat(item_date_str.replace('Z', '+00:00'))
            except (ValueError, TypeError):
                continue

        if start_date <= item_date <= end_date:
            results.append(DataPoint(date=item_date.strftime('%Y-%m-%d'), value=item.get('value', 0)))
            
    return sorted(results, key=lambda x: x.date)


@router.get("/combined_view", response_model=CombinedViewResponse)
async def get_combined_view(
    search_group: str = Query("brand", description="Grupo de busca ('brand' ou 'competitors')"),
    days: int = Query(30, description="Período em dias para a análise"),
    db: firestore.Client = Depends(get_db)
):
    """
    Endpoint para o Gráfico de Correlação: Menções & Interesse de Busca.
    Combina dados de menções da plataforma com dados de interesse do Google Trends.
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Executa as duas buscas de dados em paralelo
        mentions_task = get_mentions_over_time(db, search_group, start_date, end_date)
        trends_task = get_trends_over_time(db, search_group, start_date, end_date)
        
        mentions_results, trends_results = await asyncio.gather(mentions_task, trends_task)

        return CombinedViewResponse(
            mentions_over_time=mentions_results,
            trends_over_time=trends_results
        )
  
    except Exception as e:
        logger.error(f"Erro em get_combined_view: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {e}")


@router.get("/kpis", response_model=KpiResponse)
def get_kpis(
    search_group: str = Query("brand", description="Grupo de busca ('brand' ou 'competitors')"),
    days: int = Query(7, description="Período em dias para a análise"),
    db: firestore.Client = Depends(get_db)
):
    """
    Endpoint para os KPIs (Key Performance Indicators) do Dashboard Principal.
    Calcula o volume total de menções e o sentimento médio no período.
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        query = db.collection('monitor_results') \
                  .where('search_group', '==', search_group) \
                  .where('publish_date', '>=', start_date) \
                  .where('publish_date', '<=', end_date) \
                  .where('status', '==', 'nlp_ok')

        docs = list(query.stream())

        total_mentions = len(docs)
        total_sentiment_score = 0
        
        if total_mentions == 0:
            return KpiResponse(total_mentions=0, average_sentiment=0.0)

        for doc in docs:
            data = doc.to_dict()
            analysis = data.get('google_nlp_analysis')
            if analysis and isinstance(analysis, dict):
                # O score de sentimento varia de -1.0 (negativo) a 1.0 (positivo)
                total_sentiment_score += analysis.get('score', 0.0)
        
        average_sentiment = total_sentiment_score / total_mentions if total_mentions > 0 else 0.0

        return KpiResponse(
            total_mentions=total_mentions,
            average_sentiment=round(average_sentiment, 2)
        )

    except Exception as e:
        logger.error(f"Erro em get_kpis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {e}")


@router.get("/entities_cloud", response_model=List[Entity])
def get_entities_cloud(
    search_group: str = Query("brand", description="Grupo de busca ('brand' ou 'competitors')"),
    days: int = Query(7, description="Período em dias para a análise"),
    db: firestore.Client = Depends(get_db)
):
    """
    Endpoint para a Nuvem de Entidades.
    Agrega e retorna as entidades mais mencionadas no período.
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        query = db.collection('monitor_results') \
                  .where('search_group', '==', search_group) \
                  .where('publish_date', '>=', start_date) \
                  .where('publish_date', '<=', end_date) \
                  .where('status', '==', 'nlp_ok')

        docs = query.stream()
        entity_counts = Counter()

        for doc in docs:
            data = doc.to_dict()
            analysis = data.get('google_nlp_analysis')
            if analysis and isinstance(analysis, dict):
                entities = analysis.get('entities', [])
                # Garante que as entidades sejam strings antes de contá-las
                entity_counts.update([str(e) for e in entities if e])

        # Retorna as 50 entidades mais comuns
        most_common_entities = entity_counts.most_common(50)
        
        return [Entity(text=text, value=count) for text, count in most_common_entities]

    except Exception as e:
        logger.error(f"Erro em get_entities_cloud: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {e}")


@router.get("/mentions", response_model=MentionsResponse)
def get_mentions(
    search_group: str = Query("brand", description="Grupo de busca ('brand' ou 'competitors')"),
    days: int = Query(7, description="Período em dias para a análise"),
    page: int = Query(1, description="Número da página"),
    page_size: int = Query(10, description="Itens por página"),
    entity: Optional[str] = Query(None, description="Filtra menções por uma entidade específica"),
    db: firestore.Client = Depends(get_db)
):
    """
    Endpoint para a Tabela de Menções.
    Retorna uma lista paginada de menções, com filtro opcional por entidade.
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        query = db.collection('monitor_results') \
                  .where('search_group', '==', search_group) \
                  .where('publish_date', '>=', start_date) \
                  .where('publish_date', '<=', end_date) \
                  .where('status', '==', 'nlp_ok')

        # Adiciona o filtro de entidade se for fornecido
        if entity:
            query = query.where('google_nlp_analysis.entities', 'array_contains', entity)

        # A paginação em queries complexas no Firestore é desafiadora.
        # A abordagem mais simples e eficaz para volumes de dados moderados é
        # buscar os documentos e paginar na memória.
        docs = list(query.stream())

        # Ordena os resultados pela data de publicação, mais recentes primeiro
        docs_sorted = sorted(docs, key=lambda doc: doc.to_dict().get('publish_date', datetime.min), reverse=True)
        
        total_items = len(docs_sorted)
        total_pages = math.ceil(total_items / page_size)
        
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        paginated_docs = docs_sorted[start_index:end_index]

        mentions_list = []
        for doc in paginated_docs:
            data = doc.to_dict()
            analysis = data.get('google_nlp_analysis', {})
            
            mention_data = {
                "link": data.get("link", ""),
                "title": data.get("title", ""),
                "snippet": data.get("snippet", ""),
                "publish_date": data.get("publish_date"),
                "sentiment": analysis.get("sentiment", "neutro"),
                "sentiment_score": analysis.get("score", 0.0)
            }
            mentions_list.append(Mention(**mention_data))

        return MentionsResponse(total_pages=total_pages, mentions=mentions_list)

    except Exception as e:
        logger.error(f"Erro em get_mentions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {e}")