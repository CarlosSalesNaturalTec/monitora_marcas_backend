ok - 1 - Implementar endpoint para dados continuios
ok - 2 - Melhorar Consulta de dados históricos
ok - 3 - Criar resumo 
ok - 4 - Unificar pesquisas : agora e histórico.
ok - 5 - Unificar a tela/tab : dados relevante + histórico + continuos
ok - 6 - Implementar endpoint para Dados Históricos - continuação
7 - subir servidor
8 - botar pra rodar
9 - Agendamento de consulta de dados contínuos com Cloud Scheduler

# 9 - Agendamento de consulta de dados contínuos com Cloud Scheduler

Autenticação
Endpoints públicos → chamada direta, sem autenticação.
Endpoints privados no GCP → usa OIDC com uma Service Account.
Exemplo: chamar um serviço no Cloud Run sem expô-lo publicamente.
IAP (Identity-Aware Proxy) → também suportado, usando OIDC com Client ID do IAP.
