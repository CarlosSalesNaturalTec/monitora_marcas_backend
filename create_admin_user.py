# -*- coding: utf-8 -*-
import os
from dotenv import load_dotenv
from firebase_admin import auth
import firebase_admin_init # Garante a inicialização do app

# Carrega variáveis do arquivo .env
load_dotenv()

# --- IMPORTANTE: CONFIGURE ESTAS VARIÁVEIS ---
# Altere para o email e senha que você deseja para o seu administrador.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
# -----------------------------------------

def create_admin_user():
    """
    Cria um usuário no Firebase Authentication e define uma Custom Claim
    para torná-lo um administrador.
    """
    print(f"Tentando criar o usuário administrador: {ADMIN_EMAIL}...")

    try:
        # 1. Criar o usuário
        user = auth.create_user(
            email=ADMIN_EMAIL,
            password=ADMIN_PASSWORD,
            email_verified=True, # Opcional: já marcar como verificado
            disabled=False
        )
        print(f"Usuário criado com sucesso! UID: {user.uid}")

        # 2. Definir a Custom Claim de administrador
        auth.set_custom_user_claims(user.uid, {'role': 'ADM'})
        print(f"Permissão 'ADM' definida com sucesso para o usuário {user.uid}.")
        print("\n---")
        print("✅ Usuário administrador criado e configurado!")
        print("---")

    except auth.EmailAlreadyExistsError:
        print(f"❌ Erro: O email '{ADMIN_EMAIL}' já está em uso.")
        print("Se o usuário já existe e você só quer dar a ele a permissão de ADM,")
        print("você pode fazer isso manualmente no Console do Firebase ou adaptar este script.")
    except Exception as e:
        print(f"❌ Ocorreu um erro inesperado: {e}")

if __name__ == "__main__":
    # Garante que o script encontre o arquivo de credenciais
    # Isso é importante se você executar o script da raiz do projeto
    if os.path.exists('backend/config'):
        os.chdir('backend')
        
    create_admin_user()
