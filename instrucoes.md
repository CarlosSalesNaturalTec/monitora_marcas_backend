Mantendo as funcionalidades já existentes no sistema, vamos dar continuidade ao módulo de Monitoramento com a construção da Etapa 02 a qual realizará a pesquisa de dados do Passado - Histórico.

* As pesquisas devem ser feitas em duas seções: uma utilizando os termos da marca, e outra, os termos do concorrente. 

* Utilizar nesta etapa o parâmetro sort=date:r:YYYYMMDD:YYYYMMDD de modo a obter dados históricos. Utilizar nesta coleta a estratégia de backfill recursivo, para o período de 01/01/2025 até o dia anterior à pesquisa de dados relevantes - Etapa 01 do monitoramento. A data de inicio do período histórico deve ser informada pelo usuário. 

* Dependendo da quantidade de resultados disponíveis realizar paginação até o máximo de 10 páginas/requisições. 
* Gerar contador para limitar um máximo de 100 requisições no dia. Ajustar o processo da Etapa 01  de busca de dados do agora-relevante, para também incrementar este contador. Estabelecendo um limite total de 100 requisições no dia, entre pesquisas do agora e pesquisas históricas.

* Ao gerar as querys, separar todos os termos principais e sinônimos com o operador OR e envolver o conjunto final de termos entre parênteses. Preceder com hífen os termos excludentes.

* Armazenar no banco firestore na Coleção de controle (monitor_runs): termos da busca, se a busca refere-se à marca ou ao concorrente, tipo=histórico, quantidade_resultados, data da coleta, range_inicio, range_fim.

* Caso a quantidade de resultados disponíveis levando em consideração paginação, e as requisições já realzadas na etapa anterior, necessite de um total de requisições que ultrapasse o limite de 100 requisições diárias, armazenar na coleção de controle a data da última interrupção da coleta de modo que possa ser dado continuidade à pesquisa a partir deste ponto. Esta tarefa de continuar a coleta deve ser realizada por outro processo a ser desenvolvido.

* Verificar se Urls obtidas já foram cadastradas anteriorente utilizando o ID do documento/hash da URL de modo a evitar duplicidades de cadastro.
* Para as novas URLs, armazenar em um banco firestore os seguintes dados: ID da Coleta, link, displayLink, title, pagemap, snippet e htmlsnippet. Use hash da URL como ID do documento para evitar duplicidades futuras.

* Os resultados após obtidos devem ser exibidos em tela, além dos metadados como: quantidade de resultados, data da coleta, range_inicio, range_fim, etc.

* Em caso do usuário sair da tela e retornar à mesma, caso a consulta já tenha sido realizada, exibir os dados já obtidos e inabilitar o usuário de realizar nova coleta histórica.

@frontend/package.json , @frontend\src 
@backend\main.py , backend\firebase_admin_init.py ,  @backend\auth.py , @backend\schemas , @backend\routers.

========================

ATENÇÃO! na etapa 03 - que envolve o processo diário de coleta, verificar se ainda faltam dados históricos:
* Caso o período histórico já tenha sido totalmente coletado, não fazer nada relatico a histórico. Caso não tenha sido realizada totalmente a coleta dos dados históricos devido a diferença entre o período histórico a ser coberto e o limite diário de requisições, permitir que o usuário continue com o processo de busca histórica, a partir da última data realizada.
