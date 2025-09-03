# /backend/routers/instagram_targets.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
import logging

from schemas.instagram_target_schemas import (
    MonitoredProfile, MonitoredProfileCreate, ProfileStatusUpdate,
    MonitoredHashtag, MonitoredHashtagCreate, HashtagStatusUpdate
)
from auth import get_current_user
from firebase_admin import firestore

router = APIRouter(
    prefix="/instagram/targets",
    tags=["Instagram Targets"],
    dependencies=[Depends(get_current_user)]
)

db = firestore.client()

# --- CRUD for Monitored Profiles ---

@router.post("/profiles", response_model=MonitoredProfile, status_code=status.HTTP_201_CREATED)
async def create_monitored_profile(profile: MonitoredProfileCreate):
    """
    Adiciona um novo perfil do Instagram para ser monitorado.
    O username do perfil é usado como ID do documento para evitar duplicatas.
    """
    profile_ref = db.collection('monitored_profiles').document(profile.username)
    if profile_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"O perfil '{profile.username}' já está sendo monitorado."
        )
    
    profile_data = profile.dict()
    profile_data['last_scanned_at'] = None # Inicia como nulo
    
    try:
        profile_ref.set(profile_data)
        logging.info(f"Novo perfil monitorado adicionado: {profile.username}")
        
        # Retorna o objeto completo, incluindo o ID
        created_profile = profile_data.copy()
        created_profile['id'] = profile.username
        return MonitoredProfile(**created_profile)
    except Exception as e:
        logging.error(f"Erro ao criar perfil monitorado '{profile.username}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erro interno ao salvar o perfil."
        )

@router.get("/profiles", response_model=List[MonitoredProfile])
async def get_all_monitored_profiles():
    """
    Lista todos os perfis do Instagram configurados para monitoramento.
    """
    try:
        profiles_ref = db.collection('monitored_profiles').order_by('username')
        profiles = []
        for doc in profiles_ref.stream():
            profile_data = doc.to_dict()
            profile_data['id'] = doc.id
            profiles.append(MonitoredProfile(**profile_data))
        return profiles
    except Exception as e:
        logging.error(f"Erro ao buscar perfis monitorados: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar perfis.")

@router.put("/profiles/{profile_username}/status", response_model=MonitoredProfile)
async def update_profile_status(profile_username: str, status_update: ProfileStatusUpdate):
    """
    Ativa ou desativa o monitoramento de um perfil específico.
    """
    profile_ref = db.collection('monitored_profiles').document(profile_username)
    if not profile_ref.get().exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil não encontrado.")
    
    try:
        profile_ref.update({"is_active": status_update.is_active})
        updated_doc = profile_ref.get()
        updated_data = updated_doc.to_dict()
        updated_data['id'] = updated_doc.id
        return MonitoredProfile(**updated_data)
    except Exception as e:
        logging.error(f"Erro ao atualizar status do perfil '{profile_username}': {e}")
        raise HTTPException(status_code=500, detail="Erro ao atualizar o status do perfil.")

@router.delete("/profiles/{profile_username}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitored_profile(profile_username: str):
    """
    Remove um perfil da lista de monitoramento.
    """
    profile_ref = db.collection('monitored_profiles').document(profile_username)
    if not profile_ref.get().exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil não encontrado.")
    
    try:
        profile_ref.delete()
        logging.info(f"Perfil '{profile_username}' removido do monitoramento.")
        return None
    except Exception as e:
        logging.error(f"Erro ao deletar perfil '{profile_username}': {e}")
        raise HTTPException(status_code=500, detail="Erro ao remover o perfil.")

# --- CRUD for Monitored Hashtags ---

@router.post("/hashtags", response_model=MonitoredHashtag, status_code=status.HTTP_201_CREATED)
async def create_monitored_hashtag(hashtag: MonitoredHashtagCreate):
    """
    Adiciona uma nova hashtag para ser monitorada.
    A hashtag (sem '#') é usada como ID do documento.
    """
    hashtag_clean = hashtag.hashtag.lstrip('#')
    hashtag_ref = db.collection('monitored_hashtags').document(hashtag_clean)
    if hashtag_ref.get().exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A hashtag '{hashtag_clean}' já está sendo monitorada."
        )
    
    hashtag_data = hashtag.dict()
    hashtag_data['hashtag'] = hashtag_clean # Garante que está sem '#'
    hashtag_data['last_scanned_at'] = None
    
    try:
        hashtag_ref.set(hashtag_data)
        logging.info(f"Nova hashtag monitorada adicionada: {hashtag_clean}")
        
        created_hashtag = hashtag_data.copy()
        created_hashtag['id'] = hashtag_clean
        return MonitoredHashtag(**created_hashtag)
    except Exception as e:
        logging.error(f"Erro ao criar hashtag monitorada '{hashtag_clean}': {e}")
        raise HTTPException(status_code=500, detail="Erro interno ao salvar a hashtag.")

@router.get("/hashtags", response_model=List[MonitoredHashtag])
async def get_all_monitored_hashtags():
    """
    Lista todas as hashtags configuradas para monitoramento.
    """
    try:
        hashtags_ref = db.collection('monitored_hashtags').order_by('hashtag')
        hashtags = []
        for doc in hashtags_ref.stream():
            hashtag_data = doc.to_dict()
            hashtag_data['id'] = doc.id
            hashtags.append(MonitoredHashtag(**hashtag_data))
        return hashtags
    except Exception as e:
        logging.error(f"Erro ao buscar hashtags monitoradas: {e}")
        raise HTTPException(status_code=500, detail="Erro ao buscar hashtags.")

@router.put("/hashtags/{hashtag_name}/status", response_model=MonitoredHashtag)
async def update_hashtag_status(hashtag_name: str, status_update: HashtagStatusUpdate):
    """
    Ativa ou desativa o monitoramento de uma hashtag específica.
    """
    hashtag_ref = db.collection('monitored_hashtags').document(hashtag_name)
    if not hashtag_ref.get().exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hashtag não encontrada.")
    
    try:
        hashtag_ref.update({"is_active": status_update.is_active})
        updated_doc = hashtag_ref.get()
        updated_data = updated_doc.to_dict()
        updated_data['id'] = updated_doc.id
        return MonitoredHashtag(**updated_data)
    except Exception as e:
        logging.error(f"Erro ao atualizar status da hashtag '{hashtag_name}': {e}")
        raise HTTPException(status_code=500, detail="Erro ao atualizar o status da hashtag.")

@router.delete("/hashtags/{hashtag_name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_monitored_hashtag(hashtag_name: str):
    """
    Remove uma hashtag da lista de monitoramento.
    """
    hashtag_ref = db.collection('monitored_hashtags').document(hashtag_name)
    if not hashtag_ref.get().exists:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hashtag não encontrada.")
    
    try:
        hashtag_ref.delete()
        logging.info(f"Hashtag '{hashtag_name}' removida do monitoramento.")
        return None
    except Exception as e:
        logging.error(f"Erro ao deletar hashtag '{hashtag_name}': {e}")
        raise HTTPException(status_code=500, detail="Erro ao remover a hashtag.")
