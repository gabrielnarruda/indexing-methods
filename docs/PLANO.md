# Plano da prova de conceito

Revisão de 18 de novembro de 2026. Implementação e avaliação autorizadas pelo usuário após a revisão inicial do plano.

[Diagrama interativo](arquitetura.html) · [Testes](TESTES.md) · [Métricas](METRICAS.md) · [Fontes](FONTES.md) · [Repositório](https://github.com/gabrielnarruda/indexing-methods)

## Objetivo e entregas

Receber PDFs extensos e um formulário JSON, investigar os campos com ferramentas MCP e produzir valores acompanhados de evidências localizáveis. Executar o mesmo mecanismo em documento judicial e literatura para avaliar sua adaptação inicial entre domínios.

As entregas incluem ingestão reproduzível, busca lexical e vetorial, resumos, grafo Neo4j com proveniência, ferramentas MCP, extração iterativa, pipeline de testes e relatório final com método, resultados e discussão.

## Arquitetura

| Componente | Responsabilidade |
| --- | --- |
| Python | Coordenar ingestão, extração, validação e benchmark |
| Acervo local | Preservar PDFs, texto, páginas, coordenadas e hashes |
| OpenSearch | Recuperar texto, vetores, metadados e resumos |
| Neo4j | Armazenar entidades, eventos, afirmações e relações com fontes |
| MCP local | Expor busca, leitura de trechos, inventário de seções e travessia |
| Ollama | Executar modelos de linguagem e embedding no computador |
| Relatório local | Inspecionar respostas, qualidade, custos e tempos |

Os componentes de aplicação compartilham identificadores de corpus, documento, versão, trecho e execução. A indexação publica uma versão utilizável após validar os vínculos entre os armazenamentos. Falhas devem preservar checkpoints e impedir o uso silencioso de índices incompletos.

## Indexação

1. Validar arquivo, hash, quantidade de páginas e cobertura de leitura.
2. Extrair texto com localização e identificar páginas que precisam de OCR.
3. Identificar seções, capítulos ou peças e criar trechos ligados à estrutura.
4. Gerar embeddings, resumos e dados estruturados com modelos locais.
5. Ancorar entidades, eventos e relações em trechos e guardar ambiguidades.
6. Gravar e verificar os índices. Registrar tempo, uso e falhas por etapa.

O tamanho dos trechos será configurável. A configuração inicial por caracteres será documentada como aproximação e verificada contra o limite real do modelo de embedding. O texto original permanece acessível a todas as variantes de extração.

## Representação do grafo

O núcleo contém documentos, seções, trechos, menções, entidades, eventos e afirmações. Cada relação semântica contém fonte e trecho de suporte. Datas do evento e do registro são representadas separadamente quando disponíveis. Alegações, decisões e relatos do narrador preservam sua atribuição.

A resolução de entidades usa contexto dentro do corpus. Menções ambíguas conservam seus identificadores. O benchmark compara metadados extraídos com e sem travessia para avaliar o efeito da estrutura de grafo.

## Extração de formulários

Cada campo contém caminho no JSON, pergunta, schema do valor, política de ausência e critérios de completude. Campos relacionados podem compartilhar evidências. Listas precisam registrar seções examinadas e deduplicar itens com suporte preservado.

O agente busca candidatos, lê passagens originais, propõe o valor e verifica tipo, citações e consistência. Uma nova rodada deve declarar qual informação falta e qual busca pode obtê-la. O limite inicial proposto é de três rodadas por campo, acompanhado de limites de tempo e chamadas. Ausência de progresso encerra a investigação com pendência registrada.

Estados de campo incluem preenchido, não encontrado, conflitante e limite atingido. Um valor ausente só é serializado conforme o schema do formulário. A execução conserva um resultado parcial quando um campo obrigatório não puder ser sustentado.

## Sequência de implementação

| Etapa | Critério de conclusão |
| --- | --- |
| Corpus e formulários | Fontes verificadas, schemas válidos, casos de referência com fontes |
| Instrumentação e ingestão | PDFs processados, métricas de todas as etapas e cobertura registrada |
| Recuperação e grafo | Resultados isolados por corpus, travessias rastreáveis e índices verificáveis |
| MCP e extração | Cliente e servidor reais, JSON com citações e limites exercitados |
| Benchmark e discussão | Variantes comparadas, falhas descritas e relatório compilado |

Começar com um teste pequeno de capacidade e tempo dos modelos locais. Em seguida executar o corpus completo com checkpoints. Registrar separadamente os testes reduzidos e os benchmarks completos.

## Limites da conclusão

Os dois documentos constituem um piloto. Os resultados não demonstram generalização para todos os processos judiciais ou gêneros documentais. A interpretação do acórdão deve respeitar o recorte dos autos disponível. A avaliação de suporte semântico requer rubrica e revisão das evidências.
