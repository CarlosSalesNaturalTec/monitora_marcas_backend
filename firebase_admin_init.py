import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# --- Inicialização do Firebase Admin SDK ---

# Garante que a inicialização ocorra apenas uma vez.
if not firebase_admin._apps:
    # Usa a credencial principal, que agora tem permissão para o Firestore.
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    
    if cred_path:
        # Inicializa usando o arquivo de credenciais (desenvolvimento local)
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        # Permite a inicialização automática em ambientes como o Google Cloud Run
        firebase_admin.initialize_app()

# --- Cliente Firestore ---

# Cria a instância do cliente Firestore a partir do app padrão.
db = firestore.client()