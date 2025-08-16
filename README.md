# social-listening-platform

**Nota sobre o Ambiente de Desenvolvimento**

Este projeto está sendo desenvolvido em um ambiente **Windows**. Todos os comandos de terminal executados através do Gemini CLI devem ser compatíveis com o Command Prompt (CMD).

## Arquitetura do Sistema 

### / Stack de Tecnologia

Este documento detalha a arquitetura da plataforma de Social Listening.

- **Frontend:** Next.js (React/TypeScript) com Tailwind CSS e shadcn/ui.
- **Backend:** FastAPI (Python).
- **Autenticação e Banco de Dados:** Firebase (Auth e Firestore).
- **Gerenciamento de Permissões (Admin)** O sistema utiliza **Custom Claims** do Firebase para controle de acesso baseado em função (RBAC).
- Para que um usuário tenha privilégios administrativos (ex: editar as configurações da plataforma na página `/profile`), ele **deve** possuir a claim `{'role': 'ADM'}`.
---

### 1. Frontend (Next.js)

O frontend é uma aplicação web moderna e reativa construída com Next.js.

- **Framework**: [Next.js](https://nextjs.org/) (React)
- **Linguagem**: TypeScript
- **UI/Estilização**:
  - [Tailwind CSS](https://tailwindcss.com/): Framework CSS utility-first.
  - [shadcn/ui](https://ui.shadcn.com/): Componentes de UI reutilizáveis.
- **Gerenciamento de Estado do Servidor**:
  - [TanStack Query](https://tanstack.com/query): Para caching, revalidação automática e otimização de requisições à API.
- **Gráficos e Dashboards**:
  - A confirmar entre: `Recharts`, `ECharts`, ou `ApexCharts`.
- **Comunicação com API**:
  - [Axios](https://axios-http.com/): Cliente HTTP para realizar chamadas ao backend FastAPI.
- **Autenticação (Client-Side)**:
  - [Firebase Authentication](https://firebase.google.com/docs/auth): Gerencia o fluxo de login/cadastro de usuários. Após o login, o ID Token do Firebase é obtido para autenticar requisições na API.
- **Deployment**:
  - A aplicação é containerizada usando Docker (vide `frontend/Dockerfile`) para ser hospedada no Google Cloud Run.

---

### 2. Backend (FastAPI)

O backend é uma API RESTful de alta performance construída com FastAPI.

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Linguagem**: Python
- **Servidor ASGI**: [Uvicorn](https://www.uvicorn.org/)
- **Autenticação (Server-Side)**:
  - O endpoint `GET /users/me` e outros endpoints protegidos utilizam uma dependência (`get_current_user`) que valida o **Firebase ID Token**.
  - O token deve ser enviado pelo frontend no cabeçalho `Authorization: Bearer <idToken>`.
  - A validação é feita usando o SDK `firebase-admin` (`auth.verify_id_token`), conforme implementado em `backend/auth.py`.
- **Banco de Dados**:
  - [Firestore](https://firebase.google.com/docs/firestore): A integração é realizada através da biblioteca `google-cloud-firestore`.
- **Inicialização**:
  - O SDK do Firebase Admin é inicializado no módulo `backend/firebase_admin_init.py`, utilizando as credenciais fornecidas pela variável de ambiente `GOOGLE_APPLICATION_CREDENTIALS`.
- **CORS (Cross-Origin Resource Sharing)**:
  - Configurado no `backend/main.py` para permitir requisições do frontend (ex: `http://localhost:3000` em desenvolvimento).
- **Deployment**:
  - Projetado para rodar em um container Docker separado, preferencialmente no Google Cloud Run.

---

### 3. Fluxo de Autenticação (Integração Front-Back)

1.  **Login no Frontend**: O usuário realiza o login na aplicação Next.js através da interface do Firebase Auth.
2.  **Obtenção do Token**: Após o sucesso no login, o SDK cliente do Firebase retorna um `idToken`.
3.  **Requisição para a API**: O frontend armazena este `idToken` e o anexa em um cabeçalho `Authorization` (`Bearer <idToken>`) em todas as chamadas `axios` para os endpoints protegidos do backend.
4.  **Validação no Backend**: A API FastAPI recebe a requisição. A dependência de segurança extrai o token e usa o `firebase-admin` para verificar sua autenticidade e validade.
5.  **Acesso aos Dados**: Se o token for válido, o endpoint é executado e os dados são retornados. Caso contrário, uma exceção `HTTPException` (status 401) é lançada.

---

### 4. Gerenciamento de Permissões com Custom Claims

Para controlar o acesso a funcionalidades específicas, como painéis administrativos, a plataforma utiliza **Custom Claims** do Firebase Authentication. Isso permite atribuir papéis (como `ADM`) a usuários específicos, implementando um controle de acesso baseado em função (RBAC).

#### 4.1. Definição dos Claims (Backend)

Custom claims são definidos no backend usando o SDK `firebase-admin`, pois é uma operação privilegiada que não deve ser exposta ao cliente. Um script de administração ou um endpoint de API protegido pode ser usado para atribuir um papel a um usuário.

**Exemplo de script para definir um usuário como ADM:**
```python
# Em um script como backend/create_admin_user.py
from firebase_admin import auth

# UID do usuário que será tornado administrador
user_uid = "UID_DO_USUARIO_A_SER_ADM" 

# Define o custom claim 'role' como 'ADM'
auth.set_custom_user_claims(user_uid, {'role': 'ADM'})

print(f"Usuário {user_uid} agora é um administrador.")
```

#### 4.2. Validação de Rotas Protegidas (Backend)

Endpoints da API que executam operações sensíveis devem ser protegidos para aceitar apenas usuários com o papel `ADM`. Isso é feito criando uma nova dependência no FastAPI que verifica o `role` presente nos claims do token.

**Exemplo de dependência para rotas de ADM:**
```python
# Em backend/auth.py
from fastapi import Depends, HTTPException, status
from firebase_admin import auth

# ... (código existente)

async def get_current_admin_user(decoded_token: dict = Depends(get_current_user)):
    """
    Valida o token e verifica se o usuário tem o papel 'ADM'.
    """
    if decoded_token.get("role") != "ADM":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado. Requer privilégios de administrador."
        )
    return decoded_token
```

#### 4.3. Controle de Acesso na Interface (Frontend)

No frontend, a aplicação lê os claims do token do usuário logado para exibir ou ocultar componentes da interface, como links de navegação para painéis de administração ou botões de ação.

1.  **Obter Claims**: O SDK cliente do Firebase permite forçar a atualização do token para obter os claims mais recentes.
2.  **Renderização Condicional**: O código React/Next.js usa os claims para decidir o que renderizar.

**Exemplo de verificação de claims no Frontend:**
```typescript
// Em um componente ou hook do React
import { useEffect, useState } from 'react';
import { useAuth } from '@/context/AuthContext'; // Exemplo de uso de um Auth Context

const AdminButton = () => {
  const { user } = useAuth();
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    if (user) {
      user.getIdTokenResult(true) // true força a atualização do token
        .then((idTokenResult) => {
          if (idTokenResult.claims.role === 'ADM') {
            setIsAdmin(true);
          }
        });
    }
  }, [user]);

  if (!isAdmin) {
    return null; // Não renderiza o botão se não for ADM
  }

  return <button>Painel do Administrador</button>;
};
```

---

### 5. Funcionalidades da Interface (Frontend)

- **Cadastro e Login de Usuários**: Acesso seguro à plataforma.
- **Sistema/Configurações (rota `/profile`)**: Página para o gerenciamento centralizado dos termos de pesquisa de toda a plataforma.
  - Permite o CRUD (Criar, Ler, Atualizar, Deletar) de termos principais, sinônimos e termos a excluir.
  - A interface é dividida em abas para "Marca" e "Concorrentes".
  - O acesso para edição é restrito a usuários com a permissão `ADM`. Usuários não-administradores visualizam os termos em modo somente leitura.

---

### 6. Estratégia de Deploy (Google Cloud Run)

Esta seção detalha os passos para realizar o deploy das aplicações de frontend e backend no Google Cloud Run.

#### 6.1. Backend (FastAPI)

O deploy do backend é realizado em dois passos principais:

1.  **Construir a Imagem Docker:**
    O código é enviado para o Google Cloud Build para criar a imagem do contêiner. O `PROJECT_ID` do Google Cloud deve ser substituído no comando.
    ```bash
    gcloud builds submit --tag gcr.io/[PROJECT_ID]/social-listening-backend ./backend
    ```

2.  **Implantar no Cloud Run:**
    A imagem construída é implantada como um serviço no Cloud Run. É crucial especificar a porta em que a aplicação FastAPI roda (8000).
    ```bash
    gcloud run deploy social-listening-backend --image gcr.io/[PROJECT_ID]/social-listening-backend --platform managed --region us-central1 --allow-unauthenticated --port 8000
    ```

#### 6.2. Frontend (Next.js)

O deploy do frontend requer a passagem de variáveis de ambiente para o processo de build do Next.js.

1.  **Modificar o `Dockerfile`:**
    O `Dockerfile` do frontend é modificado para aceitar argumentos de build (`ARG`) e criar um arquivo `.env.local` com as variáveis de ambiente do Firebase antes da compilação.

2.  **Criar `cloudbuild.yaml`:**
    Um arquivo `frontend/cloudbuild.yaml` é usado para orquestrar a compilação, passando as substituições como argumentos de build para o Docker.

3.  **Construir a Imagem com Substituições:**
    O build é executado usando o `cloudbuild.yaml`. As variáveis de ambiente (prefixadas com `_`) são passadas como substituições.
    ```bash
    gcloud builds submit ./frontend --config ./frontend/cloudbuild.yaml --substitutions=_NEXT_PUBLIC_FIREBASE_API_KEY="...",_NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN="..."
    ```

4.  **Implantar no Cloud Run:**
    A imagem final é implantada no Cloud Run.
    ```bash
    gcloud run deploy social-listening-frontend --image gcr.io/[PROJECT_ID]/social-listening-frontend --platform managed --region us-central1 --allow-unauthenticated
    ```
---

### BackEnd - Executando Localmente

Para executar o servidor backend localmente, siga estes passos a partir do diretório raiz do projeto:

1.  **Navegue até o diretório do backend:**
    ```bash
    cd backend
    ```

2.  **Crie e ative um ambiente virtual:**
    ```bash
    # Criar o ambiente virtual
    python -m venv venv

    # Ativar no Windows
    .\venv\Scripts\activate

    # Ativar no macOS/Linux
    source venv/bin/activate
    ```

3.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure as variáveis de ambiente:**
    - Crie uma cópia do arquivo `.env.example` e renomeie para `.env`.
    - Neste novo arquivo `.env`, defina a variável `GOOGLE_APPLICATION_CREDENTIALS` com o caminho para o seu arquivo de credenciais JSON do Firebase.
    - **Importante:** A conta de serviço (Service Account) associada a este arquivo de credencial **deve** ter a permissão (role) `Usuário do Cloud Datastore` no Google Cloud (IAM) para que o backend consiga acessar o Firestore.
    ```
    GOOGLE_APPLICATION_CREDENTIALS="caminho/para/seu/arquivo.json"
    ```

5.  **Execute o servidor:**
    O servidor irá recarregar automaticamente após qualquer alteração no código.
    ```bash
    uvicorn main:app --reload
    ```

O servidor estará disponível em [http://127.0.0.1:8000](http://127.0.0.1:8000).

### FrontEnd - Executando Localmente 

Primeiro, execute o servidor de desenvolvimento:

```bash
npm run dev
# ou
yarn dev
# ou
pnpm dev
# ou
bun dev
```

Abra [http://localhost:3000](http://localhost:3000) no seu navegador para ver o resultado.

Você pode começar a editar a página modificando `app/page.tsx`. A página é atualizada automaticamente conforme você edita o arquivo.

Este projeto usa [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) para otimizar e carregar automaticamente a [Geist](https://vercel.com/font), uma nova família de fontes da Vercel.
