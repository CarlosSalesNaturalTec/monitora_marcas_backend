# Agendamento de consulta de dados contínuos com Cloud Scheduler
* Idempotência: Desenvolva seus serviços de destino de forma que múltiplas execuções da mesma tarefa não causem resultados indesejados. O Cloud Scheduler garante a entrega "pelo menos uma vez", o que significa que, em raras ocasiões, uma tarefa pode ser executada mais de uma vez.
* Monitoramento e Logs: Fique de olho nos logs do Cloud Scheduler no Cloud Logging para verificar o status de execução dos seus jobs e diagnosticar possíveis falhas.
* Gerenciamento de Erros: Configure as políticas de repetição de acordo com a necessidade da sua aplicação. Para tarefas críticas, um número maior de tentativas pode ser apropriado.

================

- Adicionar na tab resumo e logs as buscas realizadas (monitor_runs) nos dois ultimos dias acima do log das requisições. 
- Adicionar ao log de requisições , tipo de execução: relevante, histórico ou continuo, origem
- Na tab dados exibir os apenas os últimos 200 registros
- manter endpoint de continuaçõ de busca de dados históricos (/monitor/run/historical-scheduled) para efeito de posterior extensão do prazo histórico limite.
- remover limite de requisições de busca do google cse. previnir bloqueio por requisições contínuas.
