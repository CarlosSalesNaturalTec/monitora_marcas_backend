# Documentação do Módulo Backend

Este documento detalha a arquitetura, funcionalidades e interações do backend da Plataforma de Social Listening.

## 1. Detalhes Técnicos

O backend é uma API RESTful robusta que serve como o núcleo da plataforma.

- **Framework Principal:** [FastAPI](https://fastapi.tiangolo.com/), um framework web de alta performance para Python 3.8+.
- **Servidor ASGI:** [Uvicorn](https://www.uvicorn.org/) é usado como o servidor que executa a aplicação FastAPI.
- **Validação de Dados:** [Pydantic](https://pydantic-docs.helpmanual.io/) é utilizado extensivamente para definir schemas de dados, garantindo a validação, serialização e documentação automática da API.
- **Autenticação e Autorização:** A segurança é implementada através da validação de **Firebase ID Tokens**. Todas as rotas protegidas esperam um header `Authorization: Bearer <idToken>`. O RBAC (Role-Based Access Control) é gerenciado via **Custom Claims** do Firebase.
- **Banco de Dados:** [Google Firestore](https://firebase.google.com/docs/firestore) é o banco de dados NoSQL utilizado, acessado através do SDK `firebase-admin`.
- **Dependências:** Gerenciadas através do arquivo `requirements.txt`.

## 2. Instruções de Uso e Implantação

### 2.1. Configuração do Ambiente Local

1.  **Credenciais de Serviço do Firebase:**
    -   Coloque o arquivo JSON da sua Service Account do Firebase dentro da pasta `config/`. O arquivo `firebase_admin_init.py` espera encontrá-lo nesse diretório.
    -   **Importante:** Este arquivo é sensível e não deve ser commitado no repositório. O `.gitignore` já está configurado para ignorá-lo.

2.  **Variáveis de Ambiente:**
    -   Copie o arquivo `.env.example` para um novo arquivo chamado `.env`.
    -   Preencha a variável `GOOGLE_APPLICATION_CREDENTIALS` com o caminho para o seu arquivo de Service Account.

    ```bash
    # .env
    GOOGLE_APPLICATION_CREDENTIALS=./config/your-service-account-file.json
    ```

3.  **Instalação de Dependências (em um ambiente virtual):
    ```bash
    # Navegue até a pasta do backend
    cd backend

    # Crie e ative o ambiente virtual
    python -m venv venv
    .\venv\Scripts\activate  # Windows
    # source venv/bin/activate # Linux/macOS

    # Instale as dependências
    pip install -r requirements.txt
    ```

4.  **Execução:**
    ```bash
    uvicorn main:app --reload
    ```
    A API estará disponível em `http://127.0.0.1:8000` e a documentação interativa (Swagger UI) em `http://127.0.0.1:8000/docs`.

### 2.2. Implantação (Deploy) no Google Cloud Run

O deploy é feito containerizando a aplicação com Docker e publicando-a no Google Cloud Run.

1.  **Comando de Deploy:**
    -   O comando a seguir utiliza o Google Cloud Build para criar a imagem Docker e, em seguida, a implanta no Cloud Run.

    ```bash
    # Substitua [PROJECT_ID] pelo ID do seu projeto no GCP
    gcloud builds submit --tag gcr.io/[PROJECT_ID]/social-listening-backend ./backend

    gcloud run deploy social-listening-backend \
      --image gcr.io/[PROJECT_ID]/social-listening-backend \
      --platform managed \
      --region us-central1 \
      --allow-unauthenticated \
      --port 8000
    ```

## 3. Relação com Outros Módulos

O backend é o orquestrador central da plataforma.

### 3.1. Frontend (Next.js)

-   O backend serve como a única fonte de verdade e lógica de negócio para o frontend.
-   Ele expõe todos os endpoints necessários para o frontend gerenciar usuários, termos, iniciar coletas e visualizar dados.
-   A autenticação do frontend é validada aqui, garantindo que apenas usuários autorizados possam acessar os recursos.

### 3.2. Firebase (Auth e Firestore)

-   **Firebase Admin SDK:** É a principal ferramenta de interação com os serviços do Firebase.
-   **Authentication:**
    -   Valida os ID Tokens recebidos do frontend.
    -   Gerencia usuários (criação, deleção).
    -   Atribui e lê Custom Claims (ex: `{'role': 'ADM'}`) para implementar o RBAC.
-   **Firestore:** O backend é o único módulo com permissão de escrita direta no Firestore. Ele gerencia as seguintes coleções:

| Coleção | Rota Principal | Descrição |
| :--- | :--- | :--- |
| **users** | `/users`, `/admin` | Armazena informações adicionais dos usuários, como a `role`. |
| **search_terms** | `/terms` | Documento único (`singleton`) que armazena os termos de busca da marca e concorrentes. |
| **monitor_runs** | `/monitor` | Registra os metadados de cada execução de coleta (relevante, histórica, contínua). |
| **monitor_results** | `/monitor` | Armazena cada URL/resultado individual encontrado. O ID do documento é um hash da URL para evitar duplicatas. |
| **monitor_logs** | `/monitor` | Log de cada requisição feita à API do Google CSE. |
| **daily_quotas** | `/monitor` | Documento que controla o uso da cota diária de requisições. |
| **system_logs** | `/monitor` | Registra o início, fim e status das tarefas agendadas (Scraper, NLP). |
| **system_status** | `/monitor` | Documento único que armazena o estado atual do sistema (ex: "executando scraper"). |
| **trends_terms** | `/trends` | Armazena os termos-chave para monitoramento no Google Trends. |
| **google_trends_data** | `/analytics` | Armazena os dados históricos e de interesse de busca coletados pelo módulo `search_google_trends`. |

### 3.3. Módulos Externos (Scraper, NLP, etc.)

-   O backend **não** chama diretamente os outros serviços (como Scraper ou NLP).
-   A interação é assíncrona e orquestrada via **Google Cloud Scheduler** e **Firestore**.
    1.  O backend (via rota `/monitor`) coleta URLs e as salva no Firestore com status `pending`.
    2.  Um Cloud Scheduler aciona o serviço **Scraper**, que lê os documentos `pending`, processa-os e atualiza seu status para `scraper_ok` ou `scraper_failed`.
    3.  Outro Cloud Scheduler aciona o serviço de **NLP**, que lê os documentos `scraper_ok`, realiza a análise e atualiza o status para `nlp_ok` ou `nlp_failed`.
-   O backend expõe rotas (`/monitor/scraper-stats`, `/monitor/nlp-stats`) para que o frontend possa consultar o progresso desses processos assíncronos.

### 3.4. Módulo de Analytics

-   O backend expõe endpoints específicos para alimentar os dashboards do frontend. Estes endpoints consomem os dados pré-processados das coleções `monitor_results` e `google_trends_data` para fornecer insights agregados.

| Rota Principal | Método | Descrição |
| :--- | :--- | :--- |
| `/analytics/combined_view` | `GET` | Retorna dados combinados de menções e interesse de busca (Google Trends) para o gráfico de correlação. |
| `/analytics/kpis` | `GET` | Calcula e retorna os Key Performance Indicators (KPIs), como volume total de menções e sentimento médio. |
| `/analytics/entities_cloud` | `GET` | Agrega e retorna as entidades mais mencionadas para a nuvem de palavras. |
| `/analytics/mentions` | `GET` | Retorna uma lista paginada de menções, com filtro opcional por entidade. |
