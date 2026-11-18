# Indexing Methods

Prova de conceito local de recuperação em documentos extensos e extração de formulários JSON com evidências verificáveis.

O sistema combina busca lexical e vetorial, dois níveis de recuperação com resumos, grafo de afirmações com fontes e investigação iterativa por MCP. O benchmark compara qualidade, duração, uso de modelos e custo por etapa.

[Repositório privado](https://github.com/gabrielnarruda/indexing-methods)

## Documentação

- [Diagrama interativo da arquitetura e dos testes](docs/arquitetura.html). Baixe ou abra esse arquivo no navegador. O HTML funciona offline e contém zoom, navegação e detalhes dos componentes.
- [Plano de implementação](docs/PLANO.md).
- [Plano de testes](docs/TESTES.md).
- [Métricas e contabilidade de custos](docs/METRICAS.md).
- [Corpus e fontes](docs/FONTES.md).
- [Funcionamento, decisões e limites da implementação](docs/IMPLEMENTACAO.md).
- [Crítica do método e prioridades para a próxima versão](docs/DISCUSSAO.md).
- [Relatório dos experimentos](reports/full/relatorio.html).
- [Explorador do grafo extraído, com citações e páginas](reports/full/grafo.html).

## Estado do projeto

Implementação local com Python, OpenSearch, Neo4j, Ollama e cliente/servidor MCP reais. O corpus completo possui 538 páginas, 1.057 trechos, 132 resumos e 187 afirmações ancoradas em citações. A suíte automatizada contém 25 testes; o relatório registra 36 execuções e 720 avaliações de campos, com seis variantes e três repetições.

A avaliação encontrou respostas preenchidas com atribuição incorreta, incluindo confusão entre o processo principal e um precedente citado. Os JSONs produzidos por esta configuração exigem conferência. O relatório conserva esses erros e suas evidências para orientar a próxima versão.

Os modelos de linguagem e embedding executam localmente. OpenSearch, Neo4j e Ollama usam contêineres com portas vinculadas ao endereço de loopback. Os PDFs, modelos, índices e execuções ficam no computador. O repositório contém código, configurações, documentação e artefatos de avaliação selecionados.

## Entradas e saídas

Entradas são documentos versionados e um formulário com perguntas, tipos e regras de preenchimento. A saída inclui o JSON extraído e um registro por campo com fontes, buscas, rodadas, custos, tempos e pendências.

O corpus inicial contém o inteiro teor do acórdão da ADPF 54, com 433 páginas, e Dom Casmurro, com 105 páginas. A cobertura judicial se limita às peças reproduzidas no PDF.

## Preparação

O ambiente utilizado tem Windows, Docker Desktop com GPU NVIDIA disponível para os contêineres e Python 3.12. A configuração usa `gpus: all`; para uma máquina sem GPU compatível, remova essa linha antes de subir os serviços. O desempenho em CPU não foi medido.

```powershell
uv venv .venv --python 3.12
uv pip install --python .venv/Scripts/python.exe -r requirements.lock.txt
.venv/Scripts/python.exe -m poc.fetch
docker compose up -d
docker compose exec ollama ollama pull qwen3:4b
docker compose exec ollama ollama pull embeddinggemma:300m
```

O primeiro comando requer Python 3.12 e `uv` disponíveis. Também é possível criar o ambiente com `python -m venv .venv` e instalar o arquivo de dependências com `pip`. Aguarde os três serviços ficarem disponíveis. O download verifica formato PDF, quantidade mínima de páginas e checksum em reexecuções.

## Executar

```powershell
.venv/Scripts/python.exe -m poc index --corpus all
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m poc extract --corpus adpf54 --variant F
.venv/Scripts/python.exe -m poc benchmark --name local --repetitions 3 --variants ABCDEF
.venv/Scripts/python.exe -m poc report --name local
```

Uma execução pequena pode usar `extract --corpus adpf54 --variant F --fields identificacao relator`. O comando imprime seu `run_id`. Os arquivos `runs/<run_id>/result.json` e `fields.json` contêm, respectivamente, o formulário e a trilha por campo. Eventos e métricas ficam na mesma pasta.

Para o pipeline completo, execute `./tools/validate.ps1 -Full -Name meu-experimento`. Ele baixa/verifica o corpus, indexa, executa os testes, compara as variantes e gera o relatório. `./tools/validate.ps1` executa somente a suíte de testes. Os serviços e modelos precisam estar preparados.

O benchmark retoma formulários concluídos sob o mesmo nome e rejeita alterações nos hashes dos insumos. Use outro nome após mudar configuração, código de extração ou referências. A indexação reutiliza checkpoints; `--refresh` regrava os índices usando os artefatos existentes. Para recalcular o enriquecimento, crie uma nova versão de configuração e índice.

O experimento entregue chama-se `full` e conserva o código medido em `reports/full/frozen-inputs.zip`. Após sua conclusão, foram acrescentados controles de entradas inválidas, sobreposição alta e falha na inicialização. Os prompts e a lógica de extração por campo permaneceram iguais; a comparação dos 1.057 trechos foi idêntica. A [verificação de manutenção](reports/validation/release.json) documenta essa separação. Use um nome novo, como `local`, para executar a versão atual.

Abra `docs/arquitetura.html` ou `reports/full/relatorio.html` diretamente no navegador. Os HTMLs funcionam offline. `docker compose stop` encerra os serviços preservando os volumes.

## Estrutura

Para conectar um cliente MCP externo, use o executável `.venv/Scripts/python.exe` com os argumentos `tools/serve_mcp.py --corpus adpf54`, fornecendo caminhos absolutos na configuração do cliente. O transporte é stdio. Esse ponto de entrada cria uma execução de métricas automaticamente e registra as chamadas no servidor. A configuração de um cliente externo não é necessária para executar o benchmark.

```text
docs/                 Plano, testes, métricas, fontes e diagrama
poc/                  Implementação Python
forms/                Perguntas, caminhos JSON e schemas de valores
evaluation/           Referências provisórias para avaliação
tests/                Contratos, limites, integração MCP e bancos
tools/                Pipeline e geração dos formulários iniciais
reports/              Relatórios e medições selecionadas
runs/                 Eventos, resultados e checkpoints de execução
data/raw/             PDFs e manifestos locais
data/corpus-manifest.json
sources.json          Catálogo de fontes e escopo
config.json           Modelos, limites e tarifa opcional
compose.yaml          Serviços locais
requirements.lock.txt Dependências fixadas da preparação
```

As configurações de modelos e limites são parâmetros experimentais. Os manifestos registram as versões efetivamente executadas. A cobrança de API é zero neste modo local; custo de hardware e energia permanece não configurado até informar uma tarifa em `config.json`.
