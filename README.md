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

- **Sistema/Monitorar (rota `/monitor`)**: Ferramenta para executar buscas ativas com os termos configurados e analisar os resultados.
  - **Dados do Agora (Busca Relevante)**:
    - Realiza buscas na API do Google CSE para os termos de "Marca" e "Concorrentes".
    - A busca é paginada, coletando até 100 resultados (10 páginas) para obter uma amostragem relevante.
    - Os resultados de cada busca são armazenados no Firestore.
    - A interface exibe os resultados da última coleta realizada.
    - Para evitar coletas duplicadas, o botão para iniciar uma nova busca é desabilitado caso já exista uma coleta.
  - **Dados do Passado (Busca Histórica)**:
    - Permite ao usuário definir uma data de início para uma coleta retroativa.
    - Utiliza uma estratégia de *backfill* recursivo, pesquisando dia a dia desde a data de início até a véspera do dia atual.
    - As buscas são paginadas (até 10 páginas por dia) e utilizam o parâmetro `sort=date` da API do Google.
    - Os resultados são armazenados no Firestore, com metadados que incluem o intervalo de datas da coleta.
  - **Dados Contínuos (Busca Agendada)**:
    - Endpoint: `POST /monitor/run/continuous`
    - Projetado para ser acionado por um serviço de agendamento (ex: Google Cloud Scheduler), executando uma ou mais vezes ao dia.
    - Realiza buscas para "Marca" e "Concorrentes" utilizando o parâmetro `dateRestrict=d1` para obter resultados das últimas 24 horas.
    - Pagina até um máximo de 10 páginas por grupo de termos, respeitando a cota diária de requisições.
    - Verifica duplicatas de URLs antes de salvar novos resultados no Firestore.
    - Cria um log detalhado de cada requisição no Firestore para fins de auditoria e depuração.
  - **Exclusão de Dados (Limpeza Total)**:
    - Endpoint: `DELETE /monitor/all-data`
    - Exclui permanentemente **todos** os dados relacionados ao monitoramento, limpando as coleções `monitor_runs`, `monitor_results`, `monitor_logs` e `daily_quotas`.
    - Esta é uma operação destrutiva e deve ser usada com cuidado, geralmente para reiniciar o ambiente de monitoramento.
    - O acesso é restrito a usuários com a permissão `ADM`.
  - **Controle de Cota**:
    - Implementa um contador global que limita o total de requisições à API do Google a 100 por dia, somando todos os tipos de busca.
    - Caso a cota diária seja atingida, o processo de coleta é interrompido.
  - **Gerenciamento de Duplicatas**:
    - Utiliza um hash da URL como ID do documento no Firestore para evitar o armazenamento de links duplicados em todas as coletas.
