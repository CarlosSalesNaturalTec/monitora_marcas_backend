from fastapi import APIRouter, Depends, HTTPException, Query
from google.cloud import firestore
from typing import List
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import logging

from schemas.analytics_schemas import (
    SentimentSummary, SentimentOverTimePoint, EntityCloud, Entity, ActiveSource,
    ShareOfVoicePoint, SentimentComparisonItem
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()

def get_db():
    return firestore.Client()

@router.get("/sentiment_summary", response_model=List[SentimentSummary])
def get_sentiment_summary(
    search_group: str = Query(..., description="Grupo de busca (ex: 'marca' ou 'concorrente')"),
    days: int = Query(7, description="Período em dias para a análise"),
    db: firestore.Client = Depends(get_db)
):
    """
    Retorna um resumo da contagem de sentimentos para um determinado grupo de busca.
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

        sentiment_counts = Counter()
        for doc in docs:
            data = doc.to_dict()
            # Verificação de segurança para garantir que a estrutura de dados exista
            analysis = data.get('google_nlp_analysis')
            if analysis and isinstance(analysis, dict):
                sentiment = analysis.get('sentiment', 'neutro')
                sentiment_counts[sentiment] += 1

        return [{"name": sentiment, "value": count} for sentiment, count in sentiment_counts.items()]

    except Exception as e:
        logger.error(f"Erro em get_sentiment_summary: {e}", exc_info=True)
        # Se for um erro de índice do Firestore, a exceção terá detalhes específicos.
        # A mensagem de erro no log do backend é crucial.
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {e}")


@router.get("/sentiment_over_time", response_model=List[SentimentOverTimePoint])
def get_sentiment_over_time(
    search_group: str = Query(..., description="Grupo de busca (ex: 'marca' ou 'concorrente')"),
    days: int = Query(30, description="Período em dias para a análise"),
    db: firestore.Client = Depends(get_db)
):
    """
    Retorna a evolução do sentimento ao longo do tempo para um grupo de busca.
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

        daily_sentiment = defaultdict(lambda: Counter())

        for doc in docs:
            data = doc.to_dict()
            publish_date_obj = data.get('publish_date')
            analysis = data.get('google_nlp_analysis')

            # Apenas processa se os dados essenciais existirem
            if publish_date_obj and analysis and isinstance(analysis, dict):
                publish_date_str = publish_date_obj.strftime('%Y-%m-%d')
                sentiment = analysis.get('sentiment', 'neutro')
                daily_sentiment[publish_date_str][sentiment] += 1

        results = []
        date_range = [start_date + timedelta(days=x) for x in range(days + 1)]
        
        for day in date_range:
            date_str = day.strftime('%Y-%m-%d')
            counts = daily_sentiment.get(date_str, Counter())
            results.append(
                SentimentOverTimePoint(
                    date=date_str,
                    positivo=counts.get('positivo', 0),
                    negativo=counts.get('negativo', 0),
                    neutro=counts.get('neutro', 0)
                )
            )
        
        return sorted(results, key=lambda x: x.date)

    except Exception as e:
        logger.error(f"Erro em get_sentiment_over_time: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {e}")


@router.get("/entity_cloud", response_model=EntityCloud)
def get_entity_cloud(
    search_group: str = Query(..., description="Grupo de busca (ex: 'marca' ou 'concorrente')"),
    days: int = Query(7, description="Período em dias para a análise"),
    db: firestore.Client = Depends(get_db)
):
    """
    Retorna as entidades mais comuns para sentimentos positivos e negativos.
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

        positive_entities = Counter()
        negative_entities = Counter()

        for doc in docs:
            data = doc.to_dict()
            analysis = data.get('google_nlp_analysis')
            
            if analysis and isinstance(analysis, dict):
                sentiment = analysis.get('sentiment')
                entities = analysis.get('entities', [])
                
                if not isinstance(entities, list):
                    continue # Pula se 'entities' não for uma lista

                if sentiment == 'positivo':
                    positive_entities.update(entities)
                elif sentiment == 'negativo':
                    negative_entities.update(entities)

        top_positive = [{"text": text, "value": count} for text, count in positive_entities.most_common(50)]
        top_negative = [{"text": text, "value": count} for text, count in negative_entities.most_common(50)]

        return EntityCloud(positive=top_positive, negative=top_negative)

    except Exception as e:
        logger.error(f"Erro em get_entity_cloud: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {e}")


@router.get("/active_sources", response_model=List[ActiveSource])
def get_active_sources(
    search_group: str = Query(..., description="Grupo de busca (ex: 'marca' ou 'concorrente')"),
    days: int = Query(7, description="Período em dias para a análise"),
    db: firestore.Client = Depends(get_db)
):
    """
    Retorna um ranking das fontes (veículos) mais ativas.
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

        source_counts = Counter()
        for doc in docs:
            data = doc.to_dict()
            source = data.get('displayLink')
            if source:
                source_counts[source] += 1
        
        sorted_sources = sorted(source_counts.items(), key=lambda item: item[1], reverse=True)

        return [{"source": source, "mentions": count} for source, count in sorted_sources[:20]]

    except Exception as e:
        logger.error(f"Erro em get_active_sources: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {e}")

@router.get("/share_of_voice", response_model=List[ShareOfVoicePoint])
def get_share_of_voice(
    days: int = Query(30, description="Período em dias para a análise"),
    db: firestore.Client = Depends(get_db)
):
    """
    Retorna a contagem diária de menções para 'brand' vs 'competitors'.
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        query = db.collection('monitor_results') \
                  .where('publish_date', '>=', start_date) \
                  .where('publish_date', '<=', end_date) \
                  .where('status', '==', 'nlp_ok')
        
        docs = query.stream()

        daily_counts = defaultdict(lambda: Counter())
        for doc in docs:
            data = doc.to_dict()
            publish_date_obj = data.get('publish_date')
            search_group = data.get('search_group')
            if publish_date_obj and search_group in ['brand', 'competitors']:
                date_str = publish_date_obj.strftime('%Y-%m-%d')
                daily_counts[date_str][search_group] += 1

        results = []
        date_range = [start_date + timedelta(days=x) for x in range(days + 1)]
        for day in date_range:
            date_str = day.strftime('%Y-%m-%d')
            counts = daily_counts.get(date_str, Counter())
            results.append(ShareOfVoicePoint(
                date=date_str,
                brand=counts.get('brand', 0),
                competitors=counts.get('competitors', 0)
            ))
        
        return sorted(results, key=lambda x: x.date)

    except Exception as e:
        logger.error(f"Erro em get_share_of_voice: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {e}")

@router.get("/sentiment_comparison", response_model=List[SentimentComparisonItem])
def get_sentiment_comparison(
    days: int = Query(7, description="Período em dias para a análise"),
    db: firestore.Client = Depends(get_db)
):
    """
    Compara a contagem de sentimentos entre 'brand' e 'competitors'.
    """
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        query = db.collection('monitor_results') \
                  .where('publish_date', '>=', start_date) \
                  .where('publish_date', '<=', end_date) \
                  .where('status', '==', 'nlp_ok')

        docs = query.stream()

        sentiment_by_group = defaultdict(lambda: Counter())
        for doc in docs:
            data = doc.to_dict()
            search_group = data.get('search_group')
            analysis = data.get('google_nlp_analysis')
            if search_group in ['brand', 'competitors'] and analysis and isinstance(analysis, dict):
                sentiment = analysis.get('sentiment', 'neutro')
                sentiment_by_group[search_group][sentiment] += 1
        
        results = [
            SentimentComparisonItem(
                name='Marca',
                positivo=sentiment_by_group['brand'].get('positivo', 0),
                negativo=sentiment_by_group['brand'].get('negativo', 0),
                neutro=sentiment_by_group['brand'].get('neutro', 0)
            ),
            SentimentComparisonItem(
                name='Concorrentes',
                positivo=sentiment_by_group['competitors'].get('positivo', 0),
                negativo=sentiment_by_group['competitors'].get('negativo', 0),
                neutro=sentiment_by_group['competitors'].get('neutro', 0)
            )
        ]
        return results

    except Exception as e:
        logger.error(f"Erro em get_sentiment_comparison: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ocorreu um erro interno no servidor: {e}")