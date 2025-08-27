from pydantic import BaseModel
from datetime import datetime

# --- Schema for System Logs ---
class SystemLog(BaseModel):
    task: str
    start_time: datetime
    end_time: datetime
    processed_count: int
    status: str
