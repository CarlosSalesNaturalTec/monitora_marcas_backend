from fastapi import APIRouter, HTTPException, Depends
from google.cloud import firestore
from google.api_core.exceptions import FailedPrecondition
from datetime import datetime, timedelta
from collections import Counter
import itertools

# Inicialização do cliente Firestore
db = firestore.Client()

router = APIRouter(
    prefix="/dashboard/instagram",
    tags=["Instagram Dashboard"],
)

# --- Aba 1: Pulso do Dia (Visão Geral) ---

@router.get("/kpis-24h")
async def get_kpis_last_24h():
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        posts_ref = db.collection('instagram_posts')
        query = posts_ref.where('post_date_utc', '>=', start_time).where('post_date_utc', '<=', end_time)
        docs = query.stream()
        total_posts = 0
        total_likes = 0
        total_comments = 0
        for doc in docs:
            post_data = doc.to_dict()
            total_posts += 1
            total_likes += post_data.get('likes_count', 0)
            total_comments += post_data.get('comments_count', 0)
        return {"total_posts": total_posts, "total_likes": total_likes, "total_comments": total_comments}
    except FailedPrecondition:
        # Este erro geralmente significa que um índice do Firestore é necessário.
        # Retornar um estado vazio para não quebrar o frontend.
        return {"total_posts": 0, "total_likes": 0, "total_comments": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar KPIs: {str(e)}")

@router.get("/stories-24h")
async def get_stories_last_24h():
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        stories_ref = db.collection('instagram_stories')
        query = stories_ref.where('story_date_utc', '>=', start_time).where('story_date_utc', '<=', end_time).order_by('story_date_utc', direction=firestore.Query.DESCENDING)
        docs = query.stream()
        stories = [{"id": doc.id, "data": doc.to_dict()} for doc in docs]
        return stories
    except FailedPrecondition:
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar stories: {str(e)}")

@router.get("/sentiment-balance-24h")
async def get_sentiment_balance_last_24h():
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        comments_ref = db.collection_group('instagram_comments')
        query = comments_ref.where('comment_date_utc', '>=', start_time).where('comment_date_utc', '<=', end_time)
        docs = query.stream()
        sentiments = {"positive": 0, "negative": 0, "neutral": 0}
        for doc in docs:
            comment_data = doc.to_dict()
            score = comment_data.get('sentiment_score')
            if score is not None:
                if score > 0.25:
                    sentiments["positive"] += 1
                elif score < -0.25:
                    sentiments["negative"] += 1
                else:
                    sentiments["neutral"] += 1
        return sentiments
    except FailedPrecondition:
        return {"positive": 0, "negative": 0, "neutral": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar balanço de sentimento: {str(e)}")

@router.get("/top-terms-24h")
async def get_top_terms_last_24h():
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        all_entities = []
        
        posts_ref = db.collection('instagram_posts')
        posts_query = posts_ref.where('post_date_utc', '>=', start_time).where('post_date_utc', '<=', end_time)
        post_docs = posts_query.stream()
        for doc in post_docs:
            post_data = doc.to_dict()
            entities = post_data.get('entities', [])
            if entities:
                all_entities.extend([entity.get('name') for entity in entities if entity.get('name')])

        comments_ref = db.collection_group('instagram_comments')
        comments_query = comments_ref.where('comment_date_utc', '>=', start_time).where('comment_date_utc', '<=', end_time)
        comment_docs = comments_query.stream()
        for doc in comment_docs:
            comment_data = doc.to_dict()
            entities = comment_data.get('entities', [])
            if entities:
                all_entities.extend([entity.get('name') for entity in entities if entity.get('name')])

        entity_counts = Counter(all_entities)
        word_cloud_data = [{"text": text, "value": value} for text, value in entity_counts.most_common(50)]
        return word_cloud_data
    except FailedPrecondition:
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar top termos: {str(e)}")

@router.get("/alerts-24h")
async def get_alerts_last_24h():
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=1)
        posts_ref = db.collection('instagram_posts')
        
        avg_start_time = end_time - timedelta(days=7)
        avg_query = posts_ref.where('post_date_utc', '>=', avg_start_time).stream()
        engagements = [doc.to_dict().get('likes_count', 0) + doc.to_dict().get('comments_count', 0) for doc in avg_query]
        avg_engagement = sum(engagements) / len(engagements) if engagements else 0

        query_24h = posts_ref.where('post_date_utc', '>=', start_time).stream()
        alerts = []
        for doc in query_24h:
            post_data = doc.to_dict()
            post_id = doc.id
            current_engagement = post_data.get('likes_count', 0) + post_data.get('comments_count', 0)

            if avg_engagement > 0 and current_engagement > (avg_engagement * 3):
                alerts.append({"type": "opportunity", "post_id": post_id, "message": f"Post '{post_id}' viralizou...", "details": post_data})

            comments_count = post_data.get('comments_count', 0)
            if comments_count > 50:
                comments_ref = db.collection(f'instagram_posts/{post_id}/instagram_comments')
                comment_docs = comments_ref.limit(100).stream()
                sentiment_scores = [c.to_dict().get('sentiment_score') for c in comment_docs if c.to_dict().get('sentiment_score') is not None]
                if sentiment_scores:
                    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                    if avg_sentiment < -0.3:
                        alerts.append({"type": "crisis", "post_id": post_id, "message": f"Post '{post_id}' com tom negativo...", "details": post_data})
        return alerts
    except FailedPrecondition:
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar alertas: {str(e)}")

# --- Aba 2: Análise de Desempenho ---

@router.get("/engagement-evolution/{profile_username}")
async def get_engagement_evolution(profile_username: str, days: int = 30):
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        posts_ref = db.collection('instagram_posts')
        query = posts_ref.where('owner_username', '==', profile_username).where('post_date_utc', '>=', start_time).order_by('post_date_utc')
        docs = query.stream()
        
        engagement_by_day = {}
        for doc in docs:
            post = doc.to_dict()
            post_date = post['post_date_utc'].strftime('%Y-%m-%d')
            if post_date not in engagement_by_day:
                engagement_by_day[post_date] = {"likes": 0, "comments": 0}
            engagement_by_day[post_date]["likes"] += post.get('likes_count', 0)
            engagement_by_day[post_date]["comments"] += post.get('comments_count', 0)

        date_range = [start_time + timedelta(days=x) for x in range(days + 1)]
        result = {"labels": [d.strftime('%Y-%m-%d') for d in date_range], "likes_series": [], "comments_series": []}
        for day in date_range:
            day_str = day.strftime('%Y-%m-%d')
            data = engagement_by_day.get(day_str, {"likes": 0, "comments": 0})
            result["likes_series"].append(data["likes"])
            result["comments_series"].append(data["comments"])
        return result
    except FailedPrecondition:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        date_range = [start_time + timedelta(days=x) for x in range(days + 1)]
        return {"labels": [d.strftime('%Y-%m-%d') for d in date_range], "likes_series": [0]*len(date_range), "comments_series": [0]*len(date_range)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar evolução do engajamento: {str(e)}")

@router.get("/performance-by-content-type/{profile_username}")
async def get_performance_by_content_type(profile_username: str):
    try:
        posts_ref = db.collection('instagram_posts')
        query = posts_ref.where('owner_username', '==', profile_username)
        docs = query.stream()
        performance = {}
        for doc in docs:
            post = doc.to_dict()
            content_type = post.get('typename', 'Unknown')
            if content_type not in performance:
                performance[content_type] = {"count": 0, "total_likes": 0, "total_comments": 0}
            performance[content_type]["count"] += 1
            performance[content_type]["total_likes"] += post.get('likes_count', 0)
            performance[content_type]["total_comments"] += post.get('comments_count', 0)
        
        avg_performance = {}
        for content_type, data in performance.items():
            count = data["count"]
            avg_performance[content_type] = {
                "avg_likes": data["total_likes"] / count if count > 0 else 0,
                "avg_comments": data["total_comments"] / count if count > 0 else 0,
                "post_count": count
            }
        return avg_performance
    except FailedPrecondition:
        return {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar performance por tipo de conteúdo: {str(e)}")

@router.get("/posts-ranking/{profile_username}")
async def get_posts_ranking(profile_username: str, sort_by: str = 'likes_count', limit: int = 10):
    try:
        posts_ref = db.collection('instagram_posts')
        query = posts_ref.where('owner_username', '==', profile_username).order_by(sort_by, direction=firestore.Query.DESCENDING).limit(limit)
        docs = query.stream()
        return [{"id": doc.id, "data": doc.to_dict()} for doc in docs]
    except FailedPrecondition:
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar ranking de posts: {str(e)}")

@router.get("/top-commenters/{profile_username}")
async def get_top_commenters(profile_username: str, analysis_type: str = 'supporter', limit: int = 5):
    try:
        posts_ref = db.collection('instagram_posts')
        posts_query = posts_ref.where('owner_username', '==', profile_username).select([]).stream()
        post_ids = [doc.id for doc in posts_query]
        if not post_ids: return []
        
        commenters = Counter()
        for post_id in post_ids:
            comments_ref = db.collection(f'instagram_posts/{post_id}/instagram_comments')
            query = comments_ref.where('sentiment_score', '>', 0.25) if analysis_type == 'supporter' else comments_ref.where('sentiment_score', '<', -0.25)
            docs = query.stream()
            for doc in docs:
                comment = doc.to_dict()
                owner_info = comment.get('owner', {})
                username = owner_info.get('username') if isinstance(owner_info, dict) else None
                if username: commenters[username] += 1
        return [{"username": name, "comment_count": count} for name, count in commenters.most_common(limit)]
    except FailedPrecondition:
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar top commenters: {str(e)}")


@router.get("/commenters-influence/{profile_username}")
async def get_commenters_influence(profile_username: str, limit: int = 50):
    """
    Agrega dados de comentaristas para o mapa de influência, retornando
    a contagem de comentários e a média de seguidores de cada um.
    """
    try:
        posts_ref = db.collection('instagram_posts')
        posts_query = posts_ref.where('owner_username', '==', profile_username).select([]).stream()
        post_ids = [doc.id for doc in posts_query]

        if not post_ids:
            return []

        # Dicionário para agregar os dados: { 'username': {'comments': count, 'followers_list': [...] } }
        commenters_data = {}

        for post_id in post_ids:
            comments_ref = db.collection(f'instagram_posts/{post_id}/instagram_comments')
            docs = comments_ref.stream()
            for doc in docs:
                comment = doc.to_dict()
                owner_info = comment.get('owner', {})
                username = owner_info.get('username') if isinstance(owner_info, dict) else None
                followers = owner_info.get('followers') if isinstance(owner_info, dict) else None

                if username:
                    if username not in commenters_data:
                        commenters_data[username] = {'comments': 0, 'followers_list': []}
                    
                    commenters_data[username]['comments'] += 1
                    if followers is not None:
                        commenters_data[username]['followers_list'].append(followers)
        
        # Processa os dados agregados para calcular a média e formatar a saída
        result = []
        for username, data in commenters_data.items():
            followers_list = data['followers_list']
            avg_followers = sum(followers_list) / len(followers_list) if followers_list else 0
            result.append({
                "user": username,
                "comments": data['comments'],
                "followers": avg_followers
            })
        
        # Ordena por número de comentários para retornar os mais ativos
        result.sort(key=lambda x: x['comments'], reverse=True)

        return result[:limit]

    except Exception:
        # Retorna uma lista vazia em caso de qualquer erro (incluindo índice ausente)
        return []


@router.get("/sentiment-by-post/{profile_username}")
async def get_sentiment_by_post(profile_username: str, limit: int = 10):
    """
    Para os posts mais recentes de um perfil, calcula a distribuição de sentimentos
    dos comentários.
    """
    try:
        posts_ref = db.collection('instagram_posts')
        # Pega os posts mais recentes do perfil
        posts_query = posts_ref.where('owner_username', '==', profile_username).order_by('post_date_utc', direction=firestore.Query.DESCENDING).limit(limit)
        post_docs = posts_query.stream()

        results = []
        for doc in post_docs:
            post_id = doc.id
            post_caption = doc.to_dict().get('caption', f'Post ID: {post_id}')[:50] # Pega os primeiros 50 caracteres da legenda
            
            comments_ref = db.collection(f'instagram_posts/{post_id}/instagram_comments')
            comment_docs = comments_ref.limit(200).stream() # Analisa até 200 comentários por post

            sentiments = Counter()
            for comment_doc in comment_docs:
                score = comment_doc.to_dict().get('sentiment_score')
                if score is not None:
                    if score > 0.25:
                        sentiments['Positivo'] += 1
                    elif score < -0.25:
                        sentiments['Negativo'] += 1
                    else:
                        sentiments['Neutro'] += 1
            
            results.append({
                "post": post_caption,
                "Positivo": sentiments['Positivo'],
                "Negativo": sentiments['Negativo'],
                "Neutro": sentiments['Neutro'],
            })
        
        return results
    except Exception:
        return []


# --- Aba 3: Inteligência Competitiva ---

from typing import List
from fastapi import Query

@router.get("/head-to-head-engagement")
async def get_head_to_head_engagement(profiles: List[str] = Query(...), days: int = 7):
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        posts_ref = db.collection('instagram_posts')
        
        results = {}
        date_range = [start_time + timedelta(days=x) for x in range(days + 1)]
        labels = [d.strftime('%Y-%m-%d') for d in date_range]

        for profile in profiles:
            query = posts_ref.where('owner_username', '==', profile).where('post_date_utc', '>=', start_time).order_by('post_date_utc')
            docs = query.stream()
            engagement_by_day = Counter()
            for doc in docs:
                post = doc.to_dict()
                post_date = post['post_date_utc'].strftime('%Y-%m-%d')
                engagement = post.get('likes_count', 0) + post.get('comments_count', 0)
                engagement_by_day[post_date] += engagement
            series_data = [engagement_by_day.get(day, 0) for day in labels]
            results[profile] = series_data
        return {"labels": labels, "series": results}
    except FailedPrecondition:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        labels = [(start_time + timedelta(days=x)).strftime('%Y-%m-%d') for x in range(days + 1)]
        series = {profile: [0]*len(labels) for profile in profiles}
        return {"labels": labels, "series": series}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados de engajamento comparativo: {str(e)}")

@router.get("/content-strategy-comparison")
async def get_content_strategy_comparison(profiles: List[str] = Query(...)):
    try:
        posts_ref = db.collection('instagram_posts')
        results = {}
        for profile in profiles:
            query = posts_ref.where('owner_username', '==', profile).stream()
            strategy = Counter(doc.to_dict().get('typename', 'Unknown') for doc in query)
            results[profile] = dict(strategy)
        return results
    except FailedPrecondition:
        return {profile: {} for profile in profiles}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao comparar estratégias de conteúdo: {str(e)}")

@router.get("/vulnerability-identification")
async def get_vulnerability_identification(profiles: List[str] = Query(...), limit: int = 10):
    try:
        vulnerabilities = []
        posts_ref = db.collection('instagram_posts')
        for profile in profiles:
            query = posts_ref.where('owner_username', '==', profile).where('comments_count', '>', 50).order_by('comments_count', direction=firestore.Query.DESCENDING).limit(limit * 2)
            docs = query.stream()
            for doc in docs:
                post_data = doc.to_dict()
                post_id = doc.id
                comments_ref = db.collection(f'instagram_posts/{post_id}/instagram_comments')
                comment_docs = comments_ref.limit(100).stream()
                sentiment_scores = [c.to_dict().get('sentiment_score') for c in comment_docs if c.to_dict().get('sentiment_score') is not None]
                if sentiment_scores:
                    avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                    if avg_sentiment < -0.25:
                        vulnerabilities.append({"profile": profile, "post_id": post_id, "avg_sentiment": avg_sentiment, "comments_count": post_data.get('comments_count'), "likes_count": post_data.get('likes_count'), "caption": post_data.get('caption', '')[:200]})
        vulnerabilities.sort(key=lambda x: x['comments_count'] * abs(x['avg_sentiment']), reverse=True)
        return vulnerabilities[:limit]
    except FailedPrecondition:
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao identificar vulnerabilidades: {str(e)}")

# --- Aba 4: Radar de Pautas (Hashtags e Mídia) ---

@router.get("/hashtag-feed/{hashtag}")
async def get_hashtag_feed(hashtag: str, limit: int = 20):
    try:
        posts_ref = db.collection('instagram_posts')
        query = posts_ref.where('monitored_hashtags', 'array-contains', hashtag).order_by('post_date_utc', direction=firestore.Query.DESCENDING).limit(limit)
        docs = query.stream()
        return [{"id": doc.id, "data": doc.to_dict()} for doc in docs]
    except FailedPrecondition:
        return []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar feed da hashtag: {str(e)}")

@router.get("/topic-sentiment-over-time/{hashtag}")
async def get_topic_sentiment_over_time(hashtag: str, days: int = 30):
    # Função super robusta para evitar crashes
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=days)
    labels = [(start_time + timedelta(days=x)).strftime('%Y-%m-%d') for x in range(days + 1)]
    default_response = {"labels": labels, "series": [None]*len(labels)}

    try:
        posts_ref = db.collection('instagram_posts')
        query = posts_ref.where('monitored_hashtags', 'array-contains', hashtag).where('post_date_utc', '>=', start_time).order_by('post_date_utc')
        docs = query.stream()
        
        sentiment_by_day = {}
        for doc in docs:
            post = doc.to_dict()
            post_date_obj = post.get('post_date_utc')

            # Validação do tipo de dado da data
            if isinstance(post_date_obj, datetime):
                post_date = post_date_obj.strftime('%Y-%m-%d')
            else:
                continue # Pula o registro se a data for inválida

            if post_date not in sentiment_by_day:
                sentiment_by_day[post_date] = {"scores": [], "count": 0}
            
            if post.get('sentiment_score') is not None:
                sentiment_by_day[post_date]["scores"].append(post['sentiment_score'])
                sentiment_by_day[post_date]["count"] += 1
        
        series = []
        for day in labels:
            data = sentiment_by_day.get(day)
            if data and data["count"] > 0:
                series.append(sum(data["scores"]) / data["count"])
            else:
                series.append(None)
        
        return {"labels": labels, "series": series}
    except Exception:
        # Captura QUALQUER exceção (índice, tipo de dado, etc.) e retorna a resposta padrão.
        return default_response

@router.get("/topic-influencers/{hashtag}")
async def get_topic_influencers(hashtag: str, limit: int = 10):
    # Função super robusta para evitar crashes
    try:
        posts_ref = db.collection('instagram_posts')
        query = posts_ref.where('monitored_hashtags', 'array-contains', hashtag).order_by('likes_count', direction=firestore.Query.DESCENDING).limit(limit * 2)
        docs = query.stream()
        
        influencers = {}
        for doc in docs:
            post = doc.to_dict()
            username = post.get('owner_username')
            if username:
                engagement = post.get('likes_count', 0) + post.get('comments_count', 0)
                if username not in influencers:
                    influencers[username] = {"total_engagement": 0, "post_count": 0}
                influencers[username]["total_engagement"] += engagement
                influencers[username]["post_count"] += 1
        
        sorted_influencers = sorted(influencers.items(), key=lambda item: item[1]['total_engagement'], reverse=True)
        return dict(sorted_influencers[:limit])
    except Exception:
        # Captura QUALQUER exceção e retorna um dicionário vazio.
        return {}