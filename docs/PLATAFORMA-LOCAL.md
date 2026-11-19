# Plataforma local de experimentos

A aplicação funcional usa a interface aprovada no protótipo e consulta uma API local. Suas tabelas são preenchidas pelos eventos e resultados reais do pipeline. O HTML de demonstração permanece separado em `prototipo-plataforma.html` e continua identificado como fictício.

Para passar o projeto a outro agente desenvolvedor, comece pelo [README-AGENTE.md](../README-AGENTE.md): ele reúne preparação, smoke test real, testes, pontos de alteração e critérios de entrega.

## Iniciar

Requisitos: Windows, Python 3.12, `uv`, Node.js compatível com Vite 8, npm e Docker Desktop. As versões de Python e JavaScript estão fixadas em `requirements.lock.txt` e `frontend/package-lock.json`.

Na primeira instalação:

```powershell
./tools/start-workbench.ps1 -Setup -Services -PrepareOnly
```

Os modelos devem estar instalados no Ollama do projeto. A aplicação lista os modelos presentes e valida suas capacidades antes de criar runs:

```powershell
.venv/Scripts/python.exe -m poc.fetch
docker compose exec ollama ollama pull qwen3:4b
docker compose exec ollama ollama pull embeddinggemma:300m
```

O comando `poc.fetch` baixa/verifica os mesmos PDFs da PoC. Depois da preparação, inicie normalmente:

```powershell
./tools/start-workbench.ps1
```

Abra **http://127.0.0.1:18766**. A API serve o build React; nenhum site é publicado. Depois da instalação e do download dos documentos/modelos, a execução usa serviços locais. OpenSearch, Neo4j, Ollama e a API estão vinculados ao loopback. O perfil AWS não é usado.

O serviço da API pode ser iniciado sem recompilar com `.venv/Scripts/python.exe -m workbench`. Uma porta alternativa pode ser escolhida com `--port`. O frontend deve ter sido compilado previamente com `npm --prefix frontend run build`.

## Fluxo de trabalho

1. **Biblioteca:** confira o PDF e a leitura, consulte as perguntas, edite o JSON de formulário/referências e salve uma versão. Versões antigas continuam disponíveis. Cada campo tem pergunta, caminho JSON e schema de valor. Referências têm resposta, aliases, páginas e conjunto de avaliação.
2. **Configuração:** duplique uma receita e altere parser, páginas, recortes, prompts, modelos, embeddings, estratégia de busca, profundidade do grafo, rodadas, contexto e política de cache. Resumo, relações, resposta e verificação usam prompts/modelos independentes. Salve uma versão.
3. **Matriz de testes:** selecione documentos, campos e conjunto de desenvolvimento/reservado. Escolha indexação isolada ou indexação + extração + avaliação. Adicione até cinco eixos como arrays JSON. Exemplos: `top_k: [4, 8]`, `max_rounds_per_field: [1, 3]`, `answer_model: ["modelo:a", "modelo:b"]`, `answer_prompt: ["prompt completo A", "prompt completo B"]`.
4. **Conferir combinações:** a API valida todos os parâmetros e mostra a quantidade de configurações e runs. Há um limite de 200 runs por envio; uma run é uma configuração/documento/repetição. Campos não selecionados explicitamente seguem o conjunto de avaliação escolhido.
5. **Executar bateria real:** a fila é persistida no SQLite. Um worker por vez evita disputar o mesmo modelo local durante a medição. A geração de respostas é repetida; não usa respostas anteriores como se fossem novas amostras.
6. **Execuções:** acompanhe estados, tempo, qualidade e custo. Inspecione uma run para ver cada etapa, resultados, citações, consultas, rankings por canal, validações e rodadas. Exporte JSON, CSV de etapas ou relatório HTML.
7. **Comparação:** escolha referência e candidata. A tela compara métricas reais e resultados por campo. Diferenças de documentos, páginas, perguntas ou gabaritos produzem um aviso de não comparabilidade. Os números não são substituídos pelos do protótipo.
8. **Grafo:** selecione uma construção, veja relações aceitas/rejeitadas e abra suas citações na página original. Os nós representam propostas do modelo, não fatos automaticamente comprovados.

## Tempo, qualidade e custo

Cada run registra leitura do PDF, OCR quando necessário, recortes, relações, resumos, embeddings de trechos e de resumos, escrita no OpenSearch, escrita no Neo4j, recuperação/MCP, extração JSON, verificação e avaliação. O tempo de fila é separado do tempo de processamento.

O total da run é medido diretamente. O tempo de MCP inclui a espera da ferramenta e o embedding da consulta; o tempo dos spans internos não é somado novamente. Inicialização, validação de cache e orquestração também consomem tempo, portanto a soma de uma seleção de etapas não substitui o total. Em interrupções abruptas, tempos parciais permanecem identificados; uma duração final não observada permanece desconhecida.

Uma etapa reaproveitada tem um pequeno tempo novo de validação/leitura. O tempo de construção anterior aparece separadamente, com a origem do artefato. Pacotes completos de resumo e grafo também têm checkpoints: a retomada reaproveita apenas arquivos cujo checksum corresponde ao conteúdo. Arquivos incompletos não são publicados como artefatos completos.

Enquanto uma etapa de indexação está em andamento, a tela mostra seu tempo decorrido. Na extração, busca e verificação intercaladas, mostra a soma parcial das operações já registradas; ela é atualizada quando cada chamada termina. Além do cache de etapas, chamadas de embedding podem reaproveitar o cache local de respostas do modelo: essa quantidade aparece na etapa. Use a política **rebuild** para desativar ambos os reaproveitamentos, lembrando que isso não descarrega o modelo da memória nem esfria os caches dos bancos.

A API local do Ollama tem custo de API zero. Hardware/energia não são tratados como gratuitos: informe uma tarifa por hora e moeda em **Custo e execução**, ou deixe o custo como não configurado. O valor de hardware é uma estimativa proporcional ao tempo medido. Chamadas, tokens e uso desconhecido são registrados por operação; a mesma chamada não é contabilizada no cliente MCP e no servidor novamente.

A qualidade exibida é o acerto automático contra a versão de gabarito congelada na run. Mostra o denominador de campos anotados. As referências iniciais são provisórias e precisam de revisão humana. Existência de uma citação, acerto do valor e suporte semântico são coisas diferentes. A avaliação não envia o gabarito ao extrator.

## Versões e armazenamento

```text
frontend/                  React + TypeScript, identidade do protótipo
workbench/                 API, planejador, fila, workers, cache e métricas
data/workbench/
  workbench.sqlite3        configurações, versões de formulários, fila e etapas
  artifacts/<hash>/        resultados de etapas, checksums e checkpoints
  indexes/<hash>/          manifestos, texto/chunks, resumos e relações
  logs/<run_id>.log         log do processo worker
runs/<run_id>/             configuração, eventos, respostas e avaliações
reports/validation/        evidências de testes selecionadas para o repositório
```

PDFs e texto completo ficam no armazenamento local. O OpenSearch indexa o texto pesquisável e os vetores, mas exclui texto e vetor do `_source` na nova plataforma. A leitura da evidência busca o trecho no artefato local. O grafo usa uma versão própria, independente do nome do índice vetorial. Toda chamada MCP recebe a versão de índice da run; não consulta um ponteiro global mutável.

Cache é por etapa e dependências. Alterar prompt de resposta ou `top_k` preserva a indexação. Alterar o modelo de embedding preserva texto e relações. Alterar prompt de relações preserva embeddings independentes. Parser, páginas, recortes e pacote participam dos hashes dos derivados. A versão/digest local do modelo também participa. A consulta vetorial verifica compatibilidade com a versão que produziu o índice.

Novas runs arquivam o código Python inicial em `implementation.zip` e registram seu hash, commit e digests dos modelos. Se o desenvolvedor alterar o código durante uma run, a proveniência sinaliza essa mudança. Para uma comparação experimental, execute com o código estável; editar prompts/receitas pela interface cria versões de dados sem alterar o programa.

Ao mudar o algoritmo Python que produz artefatos, o desenvolvedor precisa alterar a versão de cache `workbench-stage-v1` em `pipeline.py` ou incluir uma versão específica nos parâmetros da etapa. O snapshot do código é uma evidência de proveniência; ele não invalida sozinho todos os artefatos existentes. Para uma conferência imediata de uma mudança de algoritmo, use **rebuild**.

O parser permite preservar todos os blocos originais ou remover blocos de texto exatamente iguais dentro de cada página. A segunda opção evita duplicação de camadas encontrada no acórdão; não é uma garantia universal de leitura correta. As duas opções preservam localização por página e ficam identificadas na receita.

## Cancelamento e recuperação

Fechar a aba do navegador não encerra a fila ou os workers. O cancelamento impede novas operações; uma chamada já enviada pode terminar antes de o pedido ser atendido. Respostas e eventos parciais são preservados.

O coordenador verifica PID **e instante de criação do processo** antes de concluir que um worker morreu. Falta de permissão para inspecionar o processo é estado desconhecido, não prova de término. Um encerramento forçado da árvore de processos pode parar a API e o worker: na próxima abertura a run vira **Interrompida**, sem ser marcada como concluída.

Use **Repetir com a mesma receita** para uma retomada verificável. Isso cria outra run vinculada à anterior, congela os mesmos insumos e reaproveita etapas/pacotes completos. As respostas do formulário são geradas novamente para não misturar repetições experimentais. O registro antigo nunca é sobrescrito. Se a política original era reconstrução, a repetição mantém essa política e recalcula os artefatos.

Para encerrar todo o trabalho, cancele as runs na interface e aguarde o estado final antes de fechar os serviços. `docker compose stop` encerra os bancos e o Ollama, preservando volumes. Dados locais e PDFs não são enviados ao Git.

## Verificação

[Resultados da entrega e limites da bateria real](VALIDACAO-PLATAFORMA.md): testes de software, conferência da interface, seis runs completas e tempos por etapa.

```powershell
./tools/validate-workbench.ps1
```

Inclui contratos, índices históricos, MCP real, versões imutáveis, matriz, cache, integridade dos artefatos, isolamento das métricas, cancelamento e detecção de workers interrompidos. Os serviços locais precisam estar disponíveis para os testes de integração. Para contratos sem bancos, use `pytest -m "not integration"` no mesmo ambiente.

Com a plataforma em execução, Playwright e Edge disponíveis, `node tools/verify-workbench.cjs` verifica a interface. O teste cria configurações/versões de formulário e runs identificadas como validação; cancela sua própria fila e conserva os registros. Ele não apaga os experimentos do usuário. É necessário haver ao menos duas runs reais avaliadas para conferir comparação e evidências. `NODE_PATH` pode apontar para uma instalação externa do Playwright.

O teste real de qualidade é separado dos testes de software. Sua identidade, páginas, campos, configurações e resultados ficam nos próprios registros das runs. Um smoke test com duas páginas não é apresentado como avaliação do documento completo.

## Limites desta versão

O uso validado é individual, local, com Ollama, OpenSearch e Neo4j. APIs pagas OpenAI/Google não são chamadas por esta entrega; podem ser adicionadas por adaptadores com preços e credenciais locais. Não há publicação, S3, autenticação multiusuário ou serviços de nuvem.

OCR automático depende de Tesseract e dos idiomas instalados. Os dois documentos de validação têm texto selecionável; isso não valida OCR em PDFs digitalizados. A interface informa falhas do componente.

O primeiro workbench oferece variação paramétrica e evidencia erros dos modelos atuais. Experimentos de segmentação por tokens/estrutura, resolução semântica de entidades, reranqueadores, leitura com evidência humana fixa, avaliação de precisão/cobertura do grafo e seleção automática de melhores métodos continuam no roteiro de robustecimento. A plataforma não afirma que o método de grafo já é superior.

O plano completo também prevê distribuição de latências entre repetições, amortização de custo, orçamento por provedor e reavaliação de respostas sob um novo gabarito. Esses recursos não estão incluídos nesta primeira entrega; a comparação atual é entre runs individuais, com exportação das medições para análise adicional.

## Identidade da interface

A aplicação mantém a direção visual documentada em [PROTOTIPO.md](PROTOTIPO.md): superfícies claras, verde do projeto, tipografia do sistema e navegação por etapa. Na versão funcional, o aviso de demonstração foi substituído pela indicação de execução local real e pelo estado dos serviços. Tabelas de tempo ficam tanto no detalhe da run quanto na comparação; o atalho `#tempos` abre diretamente a tabela após carregar os dados. Os screenshots de validação registram desktop e celular.
