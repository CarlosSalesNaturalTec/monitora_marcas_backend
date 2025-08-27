from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# --- Schema for System Logs ---
class SystemLog(BaseModel):
    task: str
    start_time: datetime
    end_time: Optional[datetime] = None
    processed_count: int
    status: str
    error_message: Optional[str] = None
    message: Optional[str] = None
