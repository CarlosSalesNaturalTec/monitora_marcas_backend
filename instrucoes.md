ok - 1 - Implementar endpoint para dados continuios
ok - 2 - Melhorar Consulta de dados históricos
ok - 3 - Criar resumo 
ok - 4 - Unificar pesquisas : agora e histórico.
ok - 5 - Unificar a tela/tab : dados relevante + histórico + continuos
5 - Implementar endpoint para Dados Históricos - continuação
6 - Agendamento de consulta de dados contínuos com Cloud Scheduler
7 - subir servidor
8 - botar pra rodar

# 5 - Implementar endpoint para Dados Históricos - continuação
===================

Mantendo as funcionalidades já existentes no sistema, vamos dar continuidade ao módulo de Monitoramento com a construção de um endpoint para pesquisas de dados históricos faltantes. 

* Este endpoint será acionado via Google Cloud Scheduler duas vezes ao dia.

* As pesquisas geradas por este endpoint devem ser feitas em duas seções: uma utilizando os termos da marca, e outra, os termos do concorrente. 


Caso tenha dados históricos , dar continuidade

ATENÇÃO! na etapa 03 - que envolve o processo diário de coleta, verificar se ainda faltam dados históricos:
* Caso o período histórico já tenha sido totalmente coletado, não fazer nada relatico a histórico. Caso não tenha sido realizada totalmente a coleta dos dados históricos devido a diferença entre o período histórico a ser coberto e o limite diário de requisições, permitir que o usuário continue com o processo de busca histórica, a partir da última data realizada.

* 


* Dependendo da quantidade de resultados disponíveis realizar paginação até o máximo de 10 páginas/requisições. 

* A cada requisição realizada incrementar o contador global de reqisições diárias que tem estabelecido o limite total de 100 requisições no dia.

* Ao gerar as querys, separar todos os termos principais e sinônimos com o operador OR e envolver o conjunto final de termos entre parênteses. Preceder com hífen os termos excludentes.

* Armazenar no banco firestore na Coleção de controle (monitor_runs): termos da busca, se a busca refere-se à marca ou ao concorrente, tipo=contínuo, quantidade_resultados, data e hora da coleta.

* Verificar se Urls obtidas já foram cadastradas anteriorente utilizando o ID do documento/hash da URL de modo a evitar duplicidades de cadastro.

* Para as novas URLs, armazenar em um banco firestore os seguintes dados: ID da Coleta, link, displayLink, title, pagemap, snippet e htmlsnippet. Use hash da URL como ID do documento para evitar duplicidades futuras.

==========







# 6 - Agendamento de consulta de dados contínuos com Cloud Scheduler

Autenticação
Endpoints públicos → chamada direta, sem autenticação.
Endpoints privados no GCP → usa OIDC com uma Service Account.
Exemplo: chamar um serviço no Cloud Run sem expô-lo publicamente.
IAP (Identity-Aware Proxy) → também suportado, usando OIDC com Client ID do IAP.
