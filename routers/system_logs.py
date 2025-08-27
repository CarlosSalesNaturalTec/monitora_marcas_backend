from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from firebase_admin import firestore

from schemas.system_log_schemas import SystemLog
from auth import get_current_user
from firebase_admin_init import db

router = APIRouter()

@router.get("/monitor/system-logs", response_model=List[SystemLog], tags=["Monitor"])
def get_system_logs(current_user: dict = Depends(get_current_user)):
    """
    Busca os logs do sistema da coleção 'system_logs'.
    """
    try:
        logs_ref = db.collection("system_logs").order_by("start_time", direction=firestore.Query.DESCENDING).limit(100)
        docs = logs_ref.stream()
        
        logs = [SystemLog(**doc.to_dict()) for doc in docs]
        return logs
    except Exception as e:
        print(f"Error fetching system logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao buscar os logs do sistema: {e}"
        )
