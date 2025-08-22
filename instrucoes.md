# Agendamento de consulta de dados contínuos com Cloud Scheduler
* Idempotência: Desenvolva seus serviços de destino de forma que múltiplas execuções da mesma tarefa não causem resultados indesejados. O Cloud Scheduler garante a entrega "pelo menos uma vez", o que significa que, em raras ocasiões, uma tarefa pode ser executada mais de uma vez.
* Monitoramento e Logs: Fique de olho nos logs do Cloud Scheduler no Cloud Logging para verificar o status de execução dos seus jobs e diagnosticar possíveis falhas.
* Gerenciamento de Erros: Configure as políticas de repetição de acordo com a necessidade da sua aplicação. Para tarefas críticas, um número maior de tentativas pode ser apropriado.

================

ok - Implementar endpoint para dados continuios
ok - Melhorar Consulta de dados históricos
ok - Criar resumo 
ok - Unificar pesquisas : agora e histórico.
ok - Unificar a tela/tab : dados relevante + histórico + continuos
ok - Implementar endpoint para Dados Históricos - continuação
ok - subir servidor
ok - botar pra rodar
ok - Cloud Scheduler para Dados do dia (Todos os dias as 12hs e as 23hs)
ok - Cloud Scheduler para Dados históricos  (Todos os dias as 23:30hs)

- Nas buscas realizadas pelo Google CSE , adicionar o campo **origem="google_cse"** em **monitor_results**
- remover limite de requisições de busca do google cse. previnir bloqueio por requisições contínuas. tarefa em segundo plano. salva no banco de dados que está em andamento e libera front. front exibe mensagem que coleta histórica está em andamento.
- Adicionar na tab resumo e logs as buscas realizadas (monitor_runs) nos dois ultimos dias acima do log das requisições. 
- Adicionar ao log de requisições , tipo de execução: relevante, histórico ou continuo, origem
- Na tab dados exibir os apenas os últimos 200 registros
- manter endpoint de continuaçõ de busca de dados históricos (/monitor/run/historical-scheduled) para efeito de posterior extensão do prazo histórico limite.

# Origens de informações
* - Web em geral (Google CSE)
* - Youtube
* - Instagran
* - Facebook
* - Grupos do Whatsapp
* - Tik tok
* - Kwaii
* - Linkedin
* - Twitter

# ARQUITETURA DA SOLUÇÃO 
* - Define termos (marca e concorrentes)
* - Define data histórica limite
* - Inicia buscas. Tarefa em segundo plano. salva no banco de dados que está em andamento e libera front. front exibe mensagem que coleta histórica está em andamento.

* - **SEARCH** - for origem in origens
  * - Pesquisa urls mais relevantes
  * - Pesquisa urls mais relevantes no período histórico definido. 
  * - Salva urls em banco de dados **monitor_results** indicando a origem
  * - Pesquisa diariamente por urls novas (schedule às 12:00hs e 23:30hs)

* - **SCRAPPER** - for url in urls
  * - Pesquisa agendadas por urls não scrapeadas (schedule às 13:00hs e 00:30hs) 
  * - Analisa a relevância. Estabelecendo linha de corte
  * - conforme origem e displayLink-dominio, direciona para o respectivo micro-serviço de scraping 
  * - Se conseguiu realizar o scraping salva na coleção articles_scraped e marca url como scrapeada em monitor_results
  * - Se não conseguiu realizar o scraping marca status como  **unscraped** 

* - **NLP** - for article in articles_scraped
  * - Pesquisa diariamente por artigos não analisados (schedule às 14:00hs e 01:30hs)
  * - Análise de sentimento
  * - Extração de entidades
  * - Análise de contexto
  * - Salvar na coleção articles_nlp
  * - Se não conseguiu realizar o NLP marca status como  **unprocessed** 

* - **ANALYTICS** 
  * - Dashboard
  * - Monitoramento de requisições
  * - Monitoramento de scrapers
  * - Monitoramento de NLP
  * - Monitoramento de erros

* - **AGENT MODE** - Modo reativo
  * - Alertas via WhatsApp
  * - Publicações semi-automáticas em redes sociais

* - **SEMÂNTICA** - Busca semântica
  * - Embeddings / Banco vetorial
  * - Consulta via WhatsApp


# Tela Monitoramento Geral
  * - Status geral monitoramento
    * - for origem in origens (cards)
      * - Status dados relevantes: concluído, em andamento.
      * - Status dados históricos: concluído, em andamento.
      * - Status dados continuos: data-hora da última busca.
      * - Status agendamentos (search, scrapper, nlp  )
      * - Erros 
        * - unscraped, unprocessed
        * - Erros de execução / excessões 
        * - Erros agendamentos (schedules)

  * - Resumo e Logs / Dados
      
  * - Coletas/Controles
    * - Data inicio dados históricos. 
    * - Botões iniciar e parar coleta
    * - Alterar data inicio dados históricos
  
