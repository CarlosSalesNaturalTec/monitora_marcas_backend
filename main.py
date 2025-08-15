from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from auth import get_current_user

app = FastAPI(
    title="API do Social Listening Platform",
    description="Backend para o sistema de monitoramento de marcas.",
    version="0.1.0",
)

# Configuração do CORS
origins = [
    "http://localhost:3000", # A origem do seu frontend Next.js
    "https://social-listening-frontend-270453017143.us-central1.run.app" # URL de produção do frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permite todos os métodos (GET, POST, etc.)
    allow_headers=["*"], # Permite todos os cabeçalhos
)


@app.get("/")
def read_root():
    """Endpoint público de boas-vindas."""
    return {"message": "Backend do Social Listening Platform está no ar!"}


@app.get("/users/me")
def read_current_user(current_user: dict = Depends(get_current_user)):
    """
    Endpoint protegido que retorna as informações do usuário logado.

    Para acessar, o frontend deve enviar um cabeçalho:
    Authorization: Bearer <seu_firebase_id_token>
    """
    return {"uid": current_user.get("uid"), "email": current_user.get("email")}
