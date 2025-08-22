ok - 1 - Implementar endpoint para dados continuios
ok - 2 - Melhorar Consulta de dados históricos
ok - 3 - Criar resumo 
ok - 4 - Unificar pesquisas : agora e histórico.
ok - 5 - Unificar a tela/tab : dados relevante + histórico + continuos
ok - 6 - Implementar endpoint para Dados Históricos - continuação
ok - 7 - subir servidor
ok - 8 - botar pra rodar
ok - 9 - Cloud Scheduler para Dados do dia (Todos os dias as 12hs e as 23hs)
ok - 10 - Cloud Scheduler para Dados históricos  (Todos os dias as 23:30hs)

# Agendamento de consulta de dados contínuos com Cloud Scheduler

Com base na documentação e na análise do código, as duas rotas projetadas para serem acionadas por um serviço de agendamento (como o Google Cloud Scheduler) são:

   1. `POST /monitor/run/continuous`
       * Função: Coleta Contínua.
       * O que faz: Realiza uma busca por menções das últimas 24 horas (dateRestrict: "d1").
       * Frequência Ideal: Deve ser agendada para rodar uma ou mais vezes ao dia (por exemplo, a cada 12 ou 24 horas) para garantir que o sistema se mantenha sempre atualizado com os dados mais recentes.
       * Frequencia : 0 12,23 * * *   (Todos os dias as 12hs e as 23hs)

   2. `POST /monitor/run/historical-scheduled`
       * Função: Continuação da Coleta Histórica.
       * O que faz: Verifica se a coleta de dados do passado foi interrompida (geralmente por falta de cota) e, em caso afirmativo, a retoma do ponto onde parou, buscando dados de mais um dia retroativamente.
       * Frequência Ideal: Deve ser agendada para rodar uma vez ao dia (por exemplo, logo após a meia-noite, quando a cota da API do Google é renovada). Isso garante que, a cada dia, o sistema avance um passo a mais
         na busca por dados históricos até que a data de início original seja alcançada.
       * Frequencia : 30 23 * * *   (Todos os dias as 23:30hs)



Idempotência: Desenvolva seus serviços de destino de forma que múltiplas execuções da mesma tarefa não causem resultados indesejados. O Cloud Scheduler garante a entrega "pelo menos uma vez", o que significa que, em raras ocasiões, uma tarefa pode ser executada mais de uma vez.


Monitoramento e Logs: Fique de olho nos logs do Cloud Scheduler no Cloud Logging para verificar o status de execução dos seus jobs e diagnosticar possíveis falhas.

Gerenciamento de Erros: Configure as políticas de repetição de acordo com a necessidade da sua aplicação. Para tarefas críticas, um número maior de tentativas pode ser apropriado.





