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

- **Sistema/Configurações (rota `/terms`)**: Página para o gerenciamento centralizado dos termos de pesquisa de toda a plataforma.
  - Permite o CRUD (Criar, Ler, Atualizar, Deletar) de termos principais, sinônimos e termos a excluir.
  - A interface é dividida em abas para "Marca" e "Concorrentes".
  - O acesso para edição é restrito a usuários com a permissão `ADM`. Usuários não-administradores visualizam os termos em modo somente leitura.
  - Inclui uma aba de **Preview** que utiliza a API do Google CSE para testar os termos configurados em tempo real, retornando uma lista de URLs e snippets de HTML correspondentes.

- **Sistema/Monitorar (rota `/monitor`)**: Ferramenta central para a execução e análise das coletas de dados. A interface foi reestruturada para maior clareza e eficiência:
  - **Aba de Resumo e Logs**: Apresenta uma visão geral de todas as atividades de monitoramento. Inclui estatísticas agregadas (total de coletas, requisições, resultados) e tabelas com as últimas coletas realizadas e os logs de requisição mais recentes, permitindo um acompanhamento detalhado do processo.
  - **Aba de Dados**: Exibe uma tabela unificada com **todos** os resultados coletados (relevantes, históricos e contínuos), ordenados do mais recente para o mais antigo. Cada linha mostra a URL, o tipo de coleta, a data do evento e o snippet de texto, fornecendo uma visão consolidada de todas as menções encontradas.
  - **Aba de Coletas**: Centraliza todas as ações de coleta de dados.
    - **Coleta Completa**: Unifica as buscas "do agora" e "histórica". O usuário informa uma data de início, e o sistema executa um processo sequencial: primeiro, busca os resultados mais recentes (relevantes) e, em seguida, preenche os dados históricos desde a data informada. A interface exibe o andamento do processo.
    - **Gerenciamento de Dados**: Permite que administradores limpem todos os dados de monitoramento para reiniciar o ciclo de coletas.
  - **Coleta Contínua (Agendada)**:
    - Endpoint (`POST /monitor/run/continuous`) projetado para ser acionado por um scheduler (ex: Google Cloud Scheduler).
    - Realiza buscas diárias para capturar menções das últimas 24 horas, garantindo que o monitoramento seja constante.
  - **Lógica de Coleta e Armazenamento**:
    - Todas as coletas (relevantes, históricas e contínuas) registram logs detalhados de cada requisição à API do Google.
    - O sistema utiliza um hash da URL como ID do documento no Firestore para evitar duplicatas e garantir a integridade dos dados.
    - O controle de cota diária (100 requisições) é compartilhado entre todos os tipos de coleta para evitar exceder os limites da API.
