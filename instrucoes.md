ok - 1 - Implementar endpoint para dados continuios
ok - 2 - Melhorar Consulta de dados históricos
3 - Implementar endpoint para Dados Históricos - continuação
4 - Unificar pesquisas : agora e histórico
5 - Criar resumo 
6 - Agendamento de consulta de dados contínuos com Cloud Scheduler

# Implementar endpoint para dados continuios

Mantendo as funcionalidades já existentes no sistema, vamos dar continuidade ao módulo de Monitoramento com a construção de um endpoint para pesquisas de dados contínuos. 

* Este endpoint será acionado via Google Cloud Scheduler duas vezes ao dia.

* As pesquisas geradas por este endpoint devem ser feitas em duas seções: uma utilizando os termos da marca, e outra, os termos do concorrente. 

* Utilizar o parâmetro dateRestrict=d1. 

* Dependendo da quantidade de resultados disponíveis realizar paginação até o máximo de 10 páginas/requisições. 

* A cada requisição realizada incrementar o contador global de reqisições diárias que tem estabelecido o limite total de 100 requisições no dia.

* Ao gerar as querys, separar todos os termos principais e sinônimos com o operador OR e envolver o conjunto final de termos entre parênteses. Preceder com hífen os termos excludentes.

* Armazenar no banco firestore na Coleção de controle (monitor_runs): termos da busca, se a busca refere-se à marca ou ao concorrente, tipo=contínuo, quantidade_resultados, data e hora da coleta,  range_inicio e range_fim que devem ser iguais.

* Verificar se Urls obtidas já foram cadastradas anteriorente utilizando o ID do documento/hash da URL de modo a evitar duplicidades de cadastro.

* Para as novas URLs, armazenar em um banco firestore os seguintes dados: ID da Coleta, link, displayLink, title, pagemap, snippet e htmlsnippet. Use hash da URL como ID do documento para evitar duplicidades futuras.

* Criar no firestore um log de todas as requisições realizadas contendo os dados: data e hora da requisição, Id da coleta, marca ou concorrente, página, range_inicio e range_fim, quantidade de resultados obtidos, quantidade de urls novas salvas no banco.




# 2 - Melhorar Consulta de dados históricos

Verificar se pode melhorar os seguintes itens:

1 - Timeout/backoff ausentes nas chamadas à API do Google. requests.get() não define timeout nem política de retry/backoff exponencial. Qualquer latência ou falha intermitente pode travar a execução ou gerar 503 recorrentes.

2 - Consulta "histórica" não registra dias sem resultados. Nos dias em que a busca retorna 0 itens, nada é salvo. Isso gera "buracos" na linha do tempo e dificulta auditoria/relatórios. Pode ser interessante salvar um MonitorRun com total_results_found=0.

3 - Em todas as consultas Falta de parâmetros úteis do CSE. Você não envia hl/gl/lr (idioma/país). Isso pode aumentar duplicatas/ruído e resultados fora do seu alvo (BR/pt-BR)

4 - Adicionar, nas consultas de dados Relevantes e Dados históricos, log detalhado de cada requisição no Firestore para fins de auditoria e depuração, semelhante ao implementado na consulta de dados continuos.



# 3 - Implementar endpoint para Dados Históricos - continuação
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



# 4 - Unificar pesquisas : agora e histórico

Unificar as pesquisas em um único botão. 
Ao clicar neste botão o sistema deverá realizar de maneira sequencial as duas etapas da pesquisa: Dados do Agora e Dados Históricos.
1 - Realizar a pesquisa de Dados do Agora (Relevante).
2 - Ao concluir, iniciar a pesquisa por Dados do Passado (Histórico).
3 - No decorrer da pesquisa, exibir na tela informações sobre o seu andamento: Dados do Agora ou Históricos, pesquisa de termos da Marca ou do Concorrente, data range , quantidade de resultados encontrados, página atual, quantidade total de requisições realizadas, etc.

# 5 - Criar resumo do Coleta realizada até o momento
Criar resumo com:  data, tipo de contulta realizada (relevante, histórica ou recorrente), quantidade de resultados encontrados para marca e concorrente

# 6 - Agendamento de consulta de dados contínuos com Cloud Scheduler

Autenticação
Endpoints públicos → chamada direta, sem autenticação.
Endpoints privados no GCP → usa OIDC com uma Service Account.
Exemplo: chamar um serviço no Cloud Run sem expô-lo publicamente.
IAP (Identity-Aware Proxy) → também suportado, usando OIDC com Client ID do IAP.

===
