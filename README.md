# Indexing Methods

Prova de conceito local de recuperação em documentos extensos e extração de formulários JSON com evidências verificáveis.

O sistema proposto combina busca lexical e vetorial, resumos hierárquicos, grafo de entidades e eventos e investigação iterativa por MCP. O benchmark compara qualidade, duração, uso de modelos e custo por etapa.

[Repositório privado](https://github.com/gabrielnarruda/indexing-methods)

## Documentação

- [Diagrama interativo da arquitetura e dos testes](docs/arquitetura.html). Baixe ou abra esse arquivo no navegador. O HTML funciona offline e contém zoom, navegação e detalhes dos componentes.
- [Plano de implementação](docs/PLANO.md).
- [Plano de testes](docs/TESTES.md).
- [Métricas e contabilidade de custos](docs/METRICAS.md).
- [Corpus e fontes](docs/FONTES.md).

## Estado do projeto

Em 18 de novembro de 2026, o usuário autorizou a implementação, os testes ponta a ponta e um relatório final com método, resultados e discussão. O corpus foi baixado e a base de configuração está preparada. Os resultados serão publicados após execução e verificação.

Os modelos de linguagem e embedding serão executados localmente. OpenSearch, Neo4j e Ollama usam contêineres com portas vinculadas ao endereço de loopback. Os PDFs, modelos, índices e execuções ficam no computador. O repositório contém código, configurações, documentação e artefatos de avaliação selecionados.

## Entradas e saídas

Entradas são documentos versionados e um formulário com perguntas, tipos e regras de preenchimento. A saída inclui o JSON extraído e um registro por campo com fontes, buscas, rodadas, custos, tempos e pendências.

O corpus inicial contém o inteiro teor do acórdão da ADPF 54, com 433 páginas, e Dom Casmurro, com 105 páginas. A cobertura judicial se limita às peças reproduzidas no PDF.

## Preparação existente

```powershell
uv venv .venv --python 3.12
uv pip install --python .venv/Scripts/python.exe -r requirements.lock.txt
.venv/Scripts/python.exe -m poc.fetch
docker compose up -d
```

O primeiro comando requer Python 3.12 disponível no ambiente. O download verifica o formato PDF, quantidade mínima de páginas e checksum em reexecuções. Os comandos de indexação e benchmark serão documentados juntamente com sua implementação.

## Estrutura

```text
docs/                 Plano, testes, métricas, fontes e diagrama
poc/                  Implementação Python
data/raw/             PDFs e manifestos locais
data/corpus-manifest.json
sources.json          Catálogo de fontes e escopo
config.json           Modelos, limites e tarifa opcional
compose.yaml          Serviços locais
requirements.lock.txt Dependências fixadas da preparação
```

As configurações de modelos e limites são parâmetros experimentais. O benchmark registrará as versões efetivamente executadas.
