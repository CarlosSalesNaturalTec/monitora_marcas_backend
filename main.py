from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import users

# --- FastAPI App Initialization ---

app = FastAPI(
    title="API do Social Listening Platform",
    description="Backend para o sistema de monitoramento de marcas.",
    version="0.3.0",
)

origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---

app.include_router(users.router)

# --- Root Endpoint ---

@app.get("/")
def read_root():
    return {"message": "Backend do Social Listening Platform está no ar!"}
