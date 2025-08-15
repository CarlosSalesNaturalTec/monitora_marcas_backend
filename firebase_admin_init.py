import firebase_admin
from firebase_admin import credentials
from dotenv import load_dotenv
import os

load_dotenv() # Carrega as variáveis de ambiente do arquivo .env

def initialize_firebase_admin():
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK inicializado com sucesso.")
    else:
        print("A variável de ambiente GOOGLE_APPLICATION_CREDENTIALS não está definida.")
        # Em um ambiente de produção como o Cloud Run, a inicialização pode ocorrer automaticamente.
        # Se a variável não estiver definida, o SDK tentará usar as credenciais do ambiente.
        firebase_admin.initialize_app()
        print("Tentando inicialização automática do Firebase Admin SDK.")

# Inicializa o SDK quando este módulo é importado
initialize_firebase_admin()
