# PLANO DE AÇÃO

Objetivo : Construir uma Plataforma de Social Listening capaz de realizar monitoramento de redes sociais e análise de dados de forma automática. As fontes a serem pesquisadas são: Web em geral utilizando Google CSE, Youtube, Instagran, Facebook, Mensagens de Grupos do Whatsapp, Tik tok, Kwaii, Linkedin e Twitter. A plataforma deve possuir um frontend no qual o usuário poderá: definir os parâmetros do sistema, iniciar o processo de coleta de dados, acompanhar o andamento destas coletas e realizar as respectivas análises de social listening. Para cada uma das fontes a serem pesquisadas e scrapeadas deverá ser construída uma respectiva API isolada.  O processo de construção desta plataforma deve ser feito em etapas com a utilização do gemini cli e moderadoração de um humano. O plano de ação geral e o estado de construção da plataforma deve ser armazenado em arquivo json a ser consultado pelo gemini cli durante a criação do código, permitindo que o processo seja continuado mesmo após interrupções. Ambiente de produção: GCP, Cloud Run, Firebase, Storage/Buckets, Cloud Schedules. Ambiente de desenvolvimento Windows. O processo de coleta será inicializado pelo usuário, a partir daí a plataforma deve ser capaz de funcionar de forma automática, disparando coletas e análises diárias com o passar do tempo utilizando cloud schedules. Deve ser considerado o código existente como ponto de partida. Utilizar o mesmo banco de dados criado no módulo de search_google_cse nos demais módulos, compartilhando as suas coleções.

# Módulos/Etapas da plataforma:

* - **FRONTEND** 
* - Etapa inicial de inicio de monitoramento já construída. Disponível na pasta: /frontend . 
* - Usuário Define os termos da busca (marca e concorrentes).
* - Define data histórica inicial para buscas históricas.
* - Inicia etapa de buscas.

* - **SEARCH_GOOGLE_CSE** 
  * - Etapa já construída. Disponível na pasta : /backend .
  * - Pesquisa urls mais relevantes no momento.
  * - Pesquisa urls mais relevantes no período histórico definido. 
  * - Salva urls em banco de dados indicando a fonte=google_cse.
  * - Dispõe de endpoint que realiza pesquisa por urls novas (dateRestrict=d1). Este endpoint deve ser acionado diariamente via Cloud Schedule.

* - **Scraper newspaper3k** 
  * - Criar novo módulo baseado no código disponível em: /temp/api_coletor_scraper.
  * - Criar neste novo módulo um endpoind, para ser acionado via Cloud Scheduler.
  * - Estabeler um filtro inicial para as urls: caso o seu dominio seja youtube, instagram ou facebook devem ser desconsideradas. As mesmas  possuirão scrapers específicos a serem desenvolvidos em etapa posterior. 
  * - Caso passe do filtro anterior, analisar a relevância da url. Estabelecer linha de corte.
  * - Para as urls que passarão da linha de corte por relevância, tentar realizar o scraping. 
  * - Se conseguiu realizar o scraping salva resultado em banco de dados e define o respecivo status como scrapeada para evitar reprocessamento.
  * - Se não conseguiu realizar o scraper registra esta informação no respectivo status inclusive registrando o motivo da não realização.

* - **NLP** 
  * - Criar novo módulo baseado no código disponível em: /temp/api_nlp.
  * - Criar neste novo módulo um endpoind, para ser acionado via Cloud Scheduler.
  * - para cada uma das urls scrapeadas na etapa anterior e que ainda não tenham passado pela análise de sentimentos tentar reaizar:
    * - Análise de sentimento.
    * - Extração de entidades.
    * - Moderação de conteúdo.
  * - Salvar análises em banco de dados.
  * - Se não conseguiu realizar o NLP registra esta informação no respectivo status inclusive registrando o motivo da não realização.

* - **SEMANTIC**.
  * - Criar novo módulo e disponiblizar no mesmo um endpoind, para ser acionado via Cloud Scheduler.
  * - Ao ser acionado realizar o Embeddings dos artigos e suas respectivas análises de NLP. 
  * - Armazenamento em Banco vetorial para posterior consultas vias chats.

* **FRONTEND** 
  * - Adicionar novas features ao módulo de Monitoramento no frontend existente na pasta /frontend.
  * - Criar nova TAB com Status geral do monitoramento.
    * - Card para a fontes de pesquisa: google_cse
      * - Status dados relevantes: concluído ou em andamento.
      * - Status dados históricos: concluído ou em andamento.
      * - Status dados continuos: data-hora da última busca.
      * - Status dos agendamentos (search, Scraper, nlp).
    * - Erros: não processadas por scraper e não analisadas por NLP por motivo de erros.
  * - Manter tab existente de Resumo e Logs / Dados.      
  * - Manter tab existente de Coletas/Controles.
    * - Data inicio dados históricos. 
    * - Botões iniciar e parar coleta.
    * - Alterar data inicio dados históricos.

* - **ANALYTICS** 
  * - Nova funcionalide no módulo de FrontEnd disponível na pasta /frontend.
  * - Dashboard com análises de social listening para a marca e concorrente.
  
* - **SEMANTIC** 
  * - Por meio do Whatsapp permitir consulta aos artigos e análises da plataforma utilizando técnicas de busca semântica. Utilizar @open-wa/wa-automate para acesso ao Whatsapp.

* - **AGENT MODE**
  * - Alertas de crise e outros via WhatsApp utilizando @open-wa/wa-automate.

* - **SEARCH_INSTAGRAM** 
  * - Utilizar Instaloader ou similar.
  * - Criar neste novo módulo um endpoind, para ser acionado via Cloud Scheduler.
  * - Pesquisa por hashtags.
  * - Pesquisa em perfis específicos. 
  * - Salva urls obtidas nas pesquisas em banco de dados indicando a fonte=instagram.
  * - baixar conteúdos (imagens, vídeos) e metadados.
  * - Realizar OCR e/ou imagem descrição nas imagens (jpeg, png).
  * - Transcrever vídeos.
  * - Disponibilizar material em banco de dados para análise via módulo de NLP existente.


* - **SEARCH_YOUTUBE** 
  * - Utilizar yt-dlp ou similar.
  * - Criar neste novo módulo um endpoind, para ser acionado via Cloud Scheduler.
  * - Pesquisa por hashtags ou termos de pesquisa.
  * - Pesquisa em perfis específicos. 
  * - Salva urls obtidas nas pesquisas em banco de dados indicando a fonte=youtube.
  * - baixar vídeos e metadados.
  * - Transcrever vídeos.
  * - Excluir vídeos transcritos.
  * - Disponibilizar material em banco de dados para análise via módulo de NLP existente.
  
  