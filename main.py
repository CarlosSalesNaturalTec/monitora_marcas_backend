from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

from routers import users, terms, monitor, system_logs, analytics, trends, service_accounts, instagram_targets, dashboard_instagram

# --- FastAPI App Initialization ---

app = FastAPI(
    title="API do Social listening Platform",
    description="Backend para o sistema de monitoramento de marcas.",
    version="0.3.0",
)

origins = [
    "http://localhost:3000",
    "https://social-listening-frontend-270453017143.us-central1.run.app",
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
app.include_router(terms.router)
app.include_router(monitor.router)
app.include_router(system_logs.router)
app.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
app.include_router(trends.router, tags=["Trends"])
app.include_router(service_accounts.router)
app.include_router(instagram_targets.router)
app.include_router(dashboard_instagram.router)


# --- Root Endpoint ---

@app.get("/")
def read_root():
    return {"message": "Backend do Social Listening Platform está no ar!"}
