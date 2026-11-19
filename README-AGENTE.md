# Comece aqui — agente desenvolvedor

Este guia permite preparar o projeto, executar uma comparação real e continuar o desenvolvimento sem depender do chat original. Repositório privado: [gabrielnarruda/indexing-methods](https://github.com/gabrielnarruda/indexing-methods).

**Produto atual:** bancada local para mudar prompts, modelos, recortes e busca; salvar versões; executar uma matriz; comparar qualidade, custo e tempo das 13 etapas; investigar respostas e fontes. Os dois documentos são o acórdão da ADPF 54 (433 páginas) e Dom Casmurro (105 páginas). O acórdão não corresponde a todos os autos do processo.

**O que ainda não existe:** adaptadores pagos OpenAI/Google, S3, colaboração multiusuário, análise agregada p50/p95, reranqueamento e resolução semântica robusta de entidades. Consulte os roteiros para evoluir esses pontos; não trate o protótipo HTML como aplicação funcional.

## 1. Entrar no projeto

Se o repositório já estiver aberto no workspace, use essa pasta e pule o clone. Em uma máquina nova, com acesso ao repositório privado já configurado:

```powershell
git clone https://github.com/gabrielnarruda/indexing-methods.git
Set-Location indexing-methods
git status --short
```

Trabalhe a partir da raiz do repositório. Preserve alterações preexistentes. Leia [AGENTS.md](AGENTS.md), [operação atual](docs/PLATAFORMA-LOCAL.md) e [resultados/limites](docs/VALIDACAO-PLATAFORMA.md). Não é preciso ler todos os relatórios para iniciar.

## 2. Preparar a máquina

O caminho validado usa **Windows + PowerShell**, Git, Python 3.12, `uv`, Node.js/npm, Docker Desktop com contêineres Linux e Microsoft Edge para os testes de interface. O pacote Vite fixado exige Node `^20.19.0 || >=22.12.0`; use uma versão que satisfaça essa condição. Dependências estão fixadas nos lockfiles.

O `compose.yaml` usa GPU NVIDIA por meio de `gpus: all`. Para executar somente em CPU, retire essa linha na sua configuração local antes de subir os serviços e registre a diferença de ambiente. O desempenho em CPU não foi validado. Não são necessárias chaves de API pagas. Instalação e primeiro download de PDFs/modelos precisam de internet.

Confira as ferramentas:

```powershell
git --version
uv --version
node --version
npm --version
docker version
docker compose version
```

Prepare dependências e serviços, depois baixe os documentos/modelos. Pare e corrija qualquer comando que retorne erro antes de avançar:

```powershell
./tools/start-workbench.ps1 -Setup -Services -PrepareOnly
.venv/Scripts/python.exe -X utf8 -m poc.fetch
docker compose exec ollama ollama pull qwen3:4b
docker compose exec ollama ollama pull embeddinggemma:300m
docker compose ps
```

O primeiro comando cria `.venv`, instala o lockfile Python, executa `npm ci` e inicia o Compose. Ele **não** baixa PDFs/modelos. Aguarde o Ollama iniciar antes dos comandos `pull`; se ainda estiver iniciando, confira os logs e tente novamente.

O Compose usa o nome de projeto `indexing-method`: duas cópias na mesma máquina compartilham esse nome e podem disputar portas/volumes. Não trate outro clone como um ambiente isolado automaticamente.

## 3. Abrir a plataforma

Em um terminal dedicado:

```powershell
./tools/start-workbench.ps1
```

Mantenha esse terminal aberto. O script compila a interface e inicia a API. Abra **http://127.0.0.1:18766**. Nos próximos comandos, use outro terminal na raiz do repositório.

| Componente | Endereço local |
| --- | --- |
| Interface/API | `http://127.0.0.1:18766` |
| Documentação da API | `http://127.0.0.1:18766/docs` |
| OpenSearch | `http://127.0.0.1:19200` |
| Neo4j Browser | `http://127.0.0.1:17474` |
| Neo4j Bolt | `bolt://127.0.0.1:17687` |
| Ollama | `http://127.0.0.1:11435` |

Confirme **o conteúdo** do health check; HTTP 200 sozinho não significa que os três serviços estejam disponíveis:

```powershell
$WorkbenchUrl = 'http://127.0.0.1:18766'
$WorkbenchHealth = Invoke-RestMethod "$WorkbenchUrl/api/health"
if (-not ($WorkbenchHealth.opensearch.ok -and $WorkbenchHealth.neo4j.ok -and $WorkbenchHealth.ollama.ok)) {
    $WorkbenchHealth | ConvertTo-Json -Depth 5
    throw 'Há um serviço local indisponível. Confira docker compose logs.'
}
```

Uma instalação nova começa sem as runs da máquina original: SQLite, índices, modelos e execuções completas não estão no Git. Os relatórios exportados estão no repositório. Não tente abrir os IDs de run publicados como se existissem no banco de um clone novo.

## 4. Primeiro experimento real, pequeno e comparável

Este exemplo cria **duas runs** do livro, páginas 1–2, campos título/autor e `top_k` 2 versus 4. Ele utiliza a receita do experimento de prompt já exportada no repositório, incluindo limite de oito relações por pacote. Essa receita é diferente do default genérico da classe `Recipe`.

Execute com a API ativa. Isto chama os modelos locais; não é simulação. Os relatórios servem apenas para recuperar a **receita**; respostas e gabaritos do relatório não são enviados como evidência ao extrator.

```powershell
$WorkbenchSnapshot = Get-Content -Raw -Encoding utf8 reports/validation/workbench-real.json | ConvertFrom-Json
$WorkbenchExample = $WorkbenchSnapshot.runs | Where-Object {
    $_.corpus_id -eq 'dom-casmurro' -and $_.request.recipe.name -eq 'Experimento de prompt · evidências diretas'
} | Select-Object -First 1
if (-not $WorkbenchExample) { throw 'Receita de exemplo não encontrada no relatório.' }
$WorkbenchRecipe = $WorkbenchExample.request.recipe
$WorkbenchRecipe.name = 'Onboarding do agente - ' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$WorkbenchRecipe.pages = '1-2'
$WorkbenchRecipe.max_rounds_per_field = 1
$WorkbenchRequest = @{
    recipe = $WorkbenchRecipe
    axes = @{ top_k = @(2, 4) }
    documents = @('dom-casmurro')
    repetitions = 1
    split = 'development'
    mode = 'end_to_end'
    field_ids = @{ 'dom-casmurro' = @('titulo', 'autor') }
} | ConvertTo-Json -Depth 100
$WorkbenchHeaders = @{ 'X-Workbench' = 'local' }
$WorkbenchPreview = Invoke-RestMethod "$WorkbenchUrl/api/experiments/preview" -Method Post -Headers $WorkbenchHeaders -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($WorkbenchRequest))
if ($WorkbenchPreview.run_count -ne 2) { throw 'A prévia deveria conter exatamente duas runs.' }
$WorkbenchBatch = Invoke-RestMethod "$WorkbenchUrl/api/experiments" -Method Post -Headers $WorkbenchHeaders -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($WorkbenchRequest))
$WorkbenchBatch.jobs | Select-Object id, corpus_id, status
```

Acompanhe pela aba **Execuções** ou repita a consulta abaixo até as duas runs terminarem. Há um worker por vez; uma bateria já em andamento pode manter estas runs na fila. Preserve os IDs e investigue qualquer estado `failed`, `partial` ou `interrupted` antes de declarar sucesso.

```powershell
$WorkbenchBatch.jobs | ForEach-Object {
    Invoke-RestMethod "$WorkbenchUrl/api/runs/$($_.id)" |
        Select-Object id, status, error, @{ Name = 'segundos'; Expression = { $_.metrics.wall_seconds } }
}
$WorkbenchComparisonUrl = "$WorkbenchUrl/?reference=$($WorkbenchBatch.jobs[0].id)&candidate=$($WorkbenchBatch.jobs[1].id)#tempos"
$WorkbenchComparisonUrl
```

Quando ambas estiverem `complete`, abra a URL impressa. Confira as 13 linhas de tempo, acerto com denominador, chamadas MCP, evidências e a diferença entre trabalho novo e construção reaproveitada. Ausência de OCR deve aparecer como etapa não necessária. Custo local de API é zero; hardware sem tarifa permanece não configurado. Um smoke test de duas páginas não é avaliação dos documentos completos.

Para o experimento completo, deixe `pages` vazio, selecione os dois documentos e defina previamente os campos e a matriz. Comece variando um fator. Os resultados de desenvolvimento conhecidos (6/6 campos com o novo prompt) não são uma garantia para outros campos e documentos.

## 5. Rodar os testes certos

Contratos sem serviços, depois build:

```powershell
.venv/Scripts/python.exe -X utf8 -m pytest -q -m 'not integration'
npm --prefix frontend run build
```

Suíte completa, com serviços preparados:

```powershell
./tools/validate-workbench.ps1
```

O checkpoint entregue tinha **39 testes aprovados**. Em um clone novo, quatro testes de integração histórica podem ser ignorados por falta dos índices em `data/indexes/`. Isso não equivale a 39 aprovações nem prova a integração nova; confira o resumo do pytest. O smoke test acima valida o caminho novo com MCP real. Não é necessário reconstruir toda a PoC histórica para desenvolver a interface.

Para a interface, é preciso ter concluído pelo menos duas runs reais, além de Edge e Playwright. Playwright não está no `package-lock.json` da aplicação. Se não houver instalação fornecida pelo ambiente do agente, prepare uma instalação de ferramentas separada:

```powershell
npm install --prefix .cache/browser-tools --no-save playwright
$env:NODE_PATH = (Resolve-Path .cache/browser-tools/node_modules).Path
node tools/verify-workbench.cjs
```

O script usa Edge (`channel: msedge`), cria configurações/versões/runs de teste, cancela sua própria fila e escreve screenshots/JSON em `reports/validation/`. Ele não apaga experimentos antigos. A conferência entregue tinha **36 verificações de UI aprovadas**. Essa ferramenta auxiliar não tem versão fixada no lockfile da aplicação: registre a versão usada se mudar o ambiente.

`tools/verify-workbench-runs.py` audita a bateria **completa** selecionada e escreve relatórios. Ele exige PDFs inteiros e pressupõe aquela comparação controlada; não serve para validar o smoke test de duas páginas. Para contratos, use dados simulados quando adequado; para qualidade e latência, use resultados reais e rotule o escopo.

## 6. Onde alterar cada parte

| Alteração | Arquivos de entrada |
| --- | --- |
| Parâmetros, defaults e templates de prompt | `workbench/configuration.py` |
| Editor, matriz, lista, comparação, grafo e tabela de tempos | `frontend/src/main.tsx`, `types.ts`, `api.ts`, `style.css` |
| Contratos HTTP, exports e leitura de evidências | `workbench/api.py`, `reporting.py` |
| Validação da matriz, snapshots e comparação | `workbench/service.py` |
| Versões imutáveis e estados persistidos | `workbench/database.py` |
| Fila, identidade de processos, cancelamento e execução | `workbench/coordinator.py`, `worker.py` |
| Leitura/OCR, recortes, resumos, grafo, embeddings e cache | `workbench/pipeline.py` |
| Cliente de modelos local | `poc/models.py` |
| Recuperação e armazenamento nos bancos | `poc/retrieval.py`, `storage.py` |
| Investigação por campo, geração e verificação JSON | `poc/extraction.py` |
| Servidor e entrada MCP | `poc/mcp_server.py`, `tools/serve_mcp.py` |
| Eventos, tempo/custo e avaliação | `poc/telemetry.py`, `workbench/metrics.py`, `evaluation.py` |
| Formulários/gabaritos iniciais | `forms/`, `evaluation/cases.json` |
| URLs locais e configuração da PoC antiga | `config.json`, `compose.yaml` |

`config.json` fornece os endereços de serviços e a configuração antiga; os parâmetros de uma run do workbench vêm da receita congelada. Editar defaults não altera receitas salvas. Para formulários já importados, use uma nova versão pela Biblioteca/API; editar `forms/` não substitui automaticamente as versões existentes no SQLite.

Para alterar apenas prompt/modelo/parâmetro, prefira a interface ou API: não é preciso editar Python. Para adicionar um parâmetro novo, conecte validação/default → snapshot → execução/chave de cache → interface → métricas/testes pertinentes.

Após mudar o frontend, execute `npm --prefix frontend run build`; a API serve `frontend/dist`. O script `npm run dev` sozinho ainda não integra um proxy da API. Após mudar Python, aguarde a fila terminar ou cancele as runs pela interface e aguarde o estado final antes de reiniciar a API. Não altere o código durante uma medição que pretenda comparar cientificamente.

## 7. Diagnóstico rápido

| Sintoma | Verificação e ação |
| --- | --- |
| Docker/GPU não inicia | Confira Docker Desktop em modo Linux e o runtime NVIDIA. Para CPU, ajuste `gpus` como descrito acima. |
| Serviço indisponível | `docker compose ps` e `docker compose logs --tail 100 opensearch neo4j ollama`; confira os três valores de `/api/health`. |
| Modelo não aparece | `docker compose exec ollama ollama list`; confirme que usou o Ollama do projeto, não outra instalação na porta 11434 do host. |
| Falta PDF | Execute `python -m poc.fetch` com o Python da `.venv`; confira hash/páginas em `data/corpus-manifest.json`. Mudança de fonte requer revisão dos gabaritos. |
| Interface 503 ou sem build | Execute `npm --prefix frontend ci` e `npm --prefix frontend run build`, depois reinicie a API se ela iniciou antes de existir `frontend/dist`. |
| POST retorna 403 | Use JSON e `X-Workbench: local`; pela interface use a mesma origem da API. |
| Porta 18766 ocupada | Reutilize a instância do projeto ou use `./tools/start-workbench.ps1 -Port 18767`; atualize `$WorkbenchUrl`. Não encerre um processo desconhecido. |
| Run interrompida | Consulte `data/workbench/logs/<id>.log` e `runs/<id>/`; use **Repetir com a mesma receita**. A run original permanece preservada. |
| Modelo excedeu tokens | Inspecione a etapa e o erro. Em uma nova receita, ajuste pacote/limite de relações/orçamento/modelo; não apague o erro para fazer a run parecer concluída. |
| Resultado igual após mudar algoritmo | Revise chaves de cache. Incremente `workbench-stage-v1` ou a versão da etapa; para conferir, use `cache_policy=rebuild`. |
| Teste do browser não encontra Playwright/Edge | Confira `NODE_PATH` da instalação auxiliar e a instalação local do Edge. |

Para encerrar tudo, cancele/aguarde as runs, encerre o terminal da API e use `docker compose stop`. Não use remoção de volumes como rotina de diagnóstico.

## 8. Critério de entrega da próxima alteração

1. Declare a hipótese e o componente alterado; preserve o histórico e as entradas das runs antigas.
2. Rode testes proporcionais à mudança e informe aprovações, falhas e testes ignorados. Para UI, confira no navegador desktop/celular. Para métodos, compare com os mesmos casos, gabaritos, limites e condições de cache explícitas.
3. Confira que as 13 etapas, tempo total/fila, uso/custo, chamadas MCP e evidências continuam explicáveis. Verifique o diff antes de incluir relatórios gerados.
4. Atualize a documentação operacional afetada e registre limitações. Cite os IDs e arquivos de evidência; não anuncie ganho de grafo sem um contraste com/sem grafo.
5. Entregue o código e o resumo da validação. Faça commit/push quando isso fizer parte da tarefa autorizada; não publique a aplicação ou crie infraestrutura por consequência do setup local.

### Texto para iniciar o próximo agente

> Trabalhe neste repositório. Leia AGENTS.md e README-AGENTE.md, confira o estado atual e preserve os resultados históricos. Prepare/verifique o ambiente local conforme o guia. A tarefa específica é: **[descreva a alteração desejada]**. Implemente-a com parâmetros versionados, mantenha métricas reais de qualidade, custo e tempo de cada etapa e execute a validação pertinente. Ao entregar, informe arquivos alterados, testes, evidências e limitações. Não assuma que os recursos futuros do plano já existem.
