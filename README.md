# 📌 Documentação — Plataforma de Social Listening

## 1. Arquitetura Geral

A plataforma é composta por dois grandes módulos:

- **Frontend:** Next.js (React/TypeScript)  
- **Backend:** FastAPI (Python)  
- **Autenticação e Banco de Dados:** Firebase (Auth e Firestore)  
- **Hospagem:** Google Cloud Run (containers Docker para frontend e backend)

Controle de acesso é feito por **Custom Claims do Firebase Authentication**, permitindo RBAC (role-based access control).

---

## 2. Frontend

- **Framework:** [Next.js](https://nextjs.org/) (React + TypeScript)  
- **Estilização:**  
  - [Tailwind CSS](https://tailwindcss.com/)  
  - [shadcn/ui](https://ui.shadcn.com/)  
- **Gerenciamento de Estado do Servidor:** [TanStack Query](https://tanstack.com/query)  
- **Comunicação com API:** [Axios](https://axios-http.com/)  
- **Autenticação (lado do cliente):** [Firebase Authentication](https://firebase.google.com/docs/auth)  
- **Gráficos/Dashboards:** decisão pendente → `Recharts`, `ECharts` ou `ApexCharts`  
- **Deployment:** Container Docker publicado no Google Cloud Run  
- **Execução local:**  
  ```bash
  npm run dev
  # ou yarn dev / pnpm dev / bun dev
  ```
  Disponível em `http://localhost:3000`.

---

## 3. Backend

- **Framework:** [FastAPI](https://fastapi.tiangolo.com/)  
- **Servidor ASGI:** [Uvicorn](https://www.uvicorn.org/)  
- **Autenticação:**  
  - Validação de **Firebase ID Tokens** via `firebase-admin`  
  - Headers `Authorization: Bearer <idToken>` obrigatórios  
- **Banco de Dados:** [Firestore](https://firebase.google.com/docs/firestore) via `google-cloud-firestore`  
- **CORS:** configurado para aceitar requisições do frontend  
- **Deployment:** Container Docker publicado no Google Cloud Run  
- **Execução local:**  
  ```bash
  cd backend
  python -m venv venv
  .\venv\Scripts\activate   # Windows
  pip install -r requirements.txt
  uvicorn main:app --reload
  ```
  Disponível em `http://127.0.0.1:8000`.

---

## 4. Fluxo de Autenticação (Front ↔ Back)

1. Usuário faz login no **Firebase Auth** (Frontend).  
2. SDK retorna `idToken`.  
3. Token é enviado em cada requisição ao Backend (`Authorization: Bearer <idToken>`).  
4. Backend valida token com `firebase-admin`.  
5. Se válido → rota autorizada; senão → `HTTP 401`.

---

## 5. Gerenciamento de Permissões (RBAC)

- Implementado com **Custom Claims** no Firebase Authentication.  
- Papéis como `ADM` são atribuídos no backend com `auth.set_custom_user_claims(uid, {'role': 'ADM'})`.  
- Validação ocorre tanto no **backend** (dependência em rotas protegidas) quanto no **frontend** (renderização condicional).  

---

## 6. Estratégia de Deploy (Google Cloud Run)

### Backend
```bash
gcloud builds submit --tag gcr.io/[PROJECT_ID]/social-listening-backend ./backend
gcloud run deploy social-listening-backend   --image gcr.io/[PROJECT_ID]/social-listening-backend   --platform managed --region us-central1   --allow-unauthenticated --port 8000
```

### Frontend
- `Dockerfile` configurado para aceitar variáveis do Firebase no build.  
- Uso de `cloudbuild.yaml` para passar substituições.  
```bash
gcloud builds submit ./frontend --config ./frontend/cloudbuild.yaml   --substitutions=_NEXT_PUBLIC_FIREBASE_API_KEY="..."
gcloud run deploy social-listening-frontend   --image gcr.io/[PROJECT_ID]/social-listening-frontend   --platform managed --region us-central1 --allow-unauthenticated
```

---

## 7. Observações Importantes

- Ambiente de desenvolvimento é **Windows**
- Claims de usuários só devem ser atribuídos no **backend**, nunca no frontend.  
- Para acessar Firestore, a Service Account configurada no backend deve ter a role **Cloud Datastore User**.


## 8. Funções do Sistema

- **Sistema/Usuários (rota `/users`)**: Página para controle de usuários que possuem acesso ao sistema e suas respectivas permissões. 
  - Permite o cadastro de novos usuários com especificação de nível de permissão.
  - Permite alteração de senha a partir da informação do email do usuário e a nova senha.
  - Permite a exclusão de usuários cadastrados a partir da informação do email a ser excluido.

- **Sistema/Termos de Pesquisa (rota `/terms`)**: Página para o gerenciamento centralizado dos termos de pesquisa de toda a plataforma.
  - Permite o CRUD (Criar, Ler, Atualizar, Deletar) de termos principais, sinônimos e termos a excluir.
  - A interface é dividida em abas para "Marca" e "Concorrentes".
  - O acesso para edição é restrito a usuários com a permissão `ADM`. Usuários não-administradores visualizam os termos em modo somente leitura.
  - Inclui uma aba de **Preview** que utiliza a API do Google CSE para testar os termos configurados em tempo real, retornando uma lista de URLs e snippets de HTML correspondentes.

- **Sistema/Buscas (rota `/monitor`)**: Ferramenta para executar buscas ativas com os termos configurados e analisar os resultados. O fluxo foi unificado para simplificar o processo e garantir a cobertura completa dos dados.
  - **Estrutura de Dados no Firestore**:
    - `monitor_runs`: Coleção que armazena os metadados de cada execução (o quê, quando, como foi buscado).
    - `monitor_results`: Armazena cada resultado individual (URL, snippet) encontrado, com um ID baseado no hash da URL para evitar duplicatas.
    - `monitor_logs`: Registra cada requisição individual feita à API do Google.
    - `daily_quotas`: Controla o uso da cota diária de 100 requisições.
  - **Coleta Inicial (Endpoint: `POST /monitor/run`)**:
    - Ponto de partida do monitoramento, acionado manualmente pelo administrador. O usuário fornece uma **data de início** para a busca histórica.
    - O processo é executado em duas etapas sequenciais:
      1.  **Busca Relevante**: O sistema primeiro realiza uma busca pelos dados mais recentes para popular a plataforma com informações atuais.
      2.  **Início da Busca Histórica**: Imediatamente após, o sistema começa a busca retroativa, dia a dia, partindo de "ontem" e avançando para o passado.
    - Ao final, mesmo que a cota não seja atingida, ele **sempre** define um marcador de interrupção (`last_interruption_date`) para garantir que o processo agendado continue de onde parou.
  - **Coleta Contínua Agendada (Endpoint: `POST /monitor/run/continuous`)**:
    - Projetado para ser acionado por um serviço de agendamento (ex: Google Cloud Scheduler) uma ou mais vezes ao dia.
    - Garante que o sistema continue capturando menções das últimas 24 horas, mantendo os dados sempre atualizados.
  - **Coleta Histórica Agendada (Endpoint: `POST /monitor/run/historical-scheduled`)**:
    - Também acionado por um scheduler (idealmente uma vez ao dia, após a renovação da cota).
    - Este endpoint possui uma lógica robusta de recuperação:
      1.  Primeiro, ele procura por um marcador de interrupção (`last_interruption_date`) deixado pela execução anterior.
      2.  Se não encontrar, ele verifica qual foi o dia mais antigo já processado na coleção `monitor_runs`.
      3.  Se a data mais antiga for posterior à data de início configurada, ele assume a continuação a partir do dia anterior, garantindo que a coleta não pare por falhas inesperadas.
  - **Gerenciamento e Status**:
    - **Status da Coleta (`GET /monitor/historical-status`)**: Fornece o estado atual da busca histórica (em andamento, pausada ou concluída).
    - **Detalhes da Execução (`GET /monitor/run/{run_id}`)**: Retorna os metadados completos de uma execução específica, usado para detalhamento na interface.
    - **Atualização da Data Histórica (`POST /monitor/update-historical-start-date`)**: Ferramenta administrativa para alterar a data de início da busca histórica ou para "resetar" o processo, forçando a retomada da coleta pelo scheduler.
    - **Limpeza de Dados (`DELETE /monitor/all-data`)**: Endpoint para administradores que apaga todos os dados de monitoramento, permitindo um recomeço do zero.
  - **Controle de Cota e Duplicatas**:
    - Um contador global limita o total de requisições à API do Google a 100 por dia.
    - O sistema utiliza um hash da URL como ID do documento no Firestore para evitar o armazenamento de links duplicados.
