ok - 1 - Implementar endpoint para dados continuios
ok - 2 - Melhorar Consulta de dados históricos
ok - 3 - Criar resumo 
ok - 4 - Unificar pesquisas : agora e histórico.
ok - 5 - Unificar a tela/tab : dados relevante + histórico + continuos
6 - Implementar endpoint para Dados Históricos - continuação
7 - Agendamento de consulta de dados contínuos com Cloud Scheduler
8 - subir servidor
9 - botar pra rodar

# 6 - Implementar endpoint para Dados Históricos - continuação
===================

A busca por dados históricos deve seguir esta ordem:  
No frontEnd O usuário informa a data limite do passado. Exemplo: 01/01/2025.
O usuário pressiona botão no frontend para iniciar a coleta de dados, caso o banco esteja vazio.
O backend inicia a coleta, inicialmente pelos dados relevantes.
Ao concluir a busca pelos dados relevantes, inicia a busca pelos dados históricos partindo de um dia anterior à busca de dados relevantes. 
Ao concluir este dia, passa para o dia imediatamente anterior e assim segue até alcançar a data limite informada ou atingir o limite de requisições diárias estabelecido. 
Diariamente será executada uma Schedule que acionará um endpoint que verifica se a busca por dados históricos foi concluida.
Caso não tenha atingido a data limite estabelecida pelo usuário, continuar a busca de dados históricos usando a mesma ordem citada anteriormente e assim segue até alcançar a data limite informada ou atingir o limite de requisições diárias estabelecido. 
 
@backend/routers/ @backend/schemas/ @backend/firebase_admin_init.py @backend/main.py



# 7 - Agendamento de consulta de dados contínuos com Cloud Scheduler

Autenticação
Endpoints públicos → chamada direta, sem autenticação.
Endpoints privados no GCP → usa OIDC com uma Service Account.
Exemplo: chamar um serviço no Cloud Run sem expô-lo publicamente.
IAP (Identity-Aware Proxy) → também suportado, usando OIDC com Client ID do IAP.
