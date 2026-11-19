# Validação da primeira plataforma local

Conferência realizada em 19/11/2026. Esta entrega conecta a interface ao pipeline real; os números abaixo vêm das runs, não do HTML de demonstração. O uso é individual, com Qwen3:4b e EmbeddingGemma:300m no Ollama local.

## O que foi verificado

- **39 testes Python aprovados:** contratos, índices históricos, MCP, versões de formulário/receita, matrizes, integridade e dependências de cache, contagem de tempo/uso, exportações, cancelamento e recuperação. [JUnit](../reports/validation/workbench-junit.xml).
- **36 verificações de interface aprovadas:** editar/salvar, recarregar versões, executar/cancelar uma matriz, comparar respostas, abrir evidências, editar JSON, ler o PDF, navegar no grafo e exportar. Zero erros JavaScript; larguras de 390, 768, 1280 e 1440 px sem transbordamento horizontal da página. Tabelas usam rolagem própria. [Evidências](../reports/validation/workbench-ui-checks.json).
- **85 verificações sobre seis runs reais aprovadas:** páginas completas, índices/grafos da versão correta, fontes, campos, contagem de MCP/modelos e reconciliação dos tempos. [Dados e configurações](../reports/validation/workbench-real.json).
- Instalação JavaScript reproduzida por `npm ci`, build TypeScript/Vite aprovado e dependências Python compatíveis. A suíte Python emite um aviso de depreciação de `httpx` no cliente de testes do Starlette; isso não impediu a validação.

Testes de software aprovados não significam que toda resposta de um modelo esteja correta. Os testes de interface deixam configurações e runs identificadas como validação; as runs criadas para testar cancelamento são conservadas e não entram nas seis runs de qualidade abaixo.

## Experimento real

Foram processadas as 433 páginas do acórdão da ADPF 54 e as 105 páginas de Dom Casmurro. Nesta receita, a indexação produziu 777/280 trechos, 110/45 resumos e 468/210 relações com citações localizadas, respectivamente. Localizar a citação não comprova a precisão semântica de cada relação.

A bateria usa três perguntas por documento: identificação, relator e resultado da ADPF; título, autor e pai do narrador no livro. São **seis perguntas únicas**, 18 avaliações em seis runs, com uma execução por configuração/documento. O conjunto `all` foi usado para desenvolvimento; não é uma avaliação reservada após congelamento de escolhas.

| Documento e receita | Construção nesta run | Acerto | Tempo da run, sem fila | Extração JSON | Verificação | Chamadas MCP |
| --- | --- | --- | --- | --- | --- | --- |
| [Livro · prompt inicial · k=4](../reports/validation/workbench-run-dom-casmurro-k4.html) | Nova, com cache de chamadas de embedding | 0/3 | 472,196 s | 35,247 s | 0,003 s | 14 |
| [ADPF · prompt inicial · k=8](../reports/validation/workbench-run-adpf54-k8.html) | Retomada, com 57 pacotes preservados | 0/3 | 786,217 s | 27,589 s | 0,001 s | 10 |
| [Livro · prompt inicial · k=8](../reports/validation/workbench-run-dom-casmurro-k8.html) | Índices reaproveitados | 0/3 | 54,857 s | 52,650 s | 0,002 s | 18 |
| [ADPF · prompt inicial · k=4](../reports/validation/workbench-run-adpf54-k4.html) | Índices reaproveitados | 0/3 | 32,025 s | 29,929 s | 0,001 s | 10 |
| [ADPF · prompt direto · k=4](../reports/validation/workbench-run-adpf54-prompt.html) | Índices reaproveitados | 3/3 | 16,680 s | 8,476 s | 6,203 s | 6 |
| [Livro · prompt direto · k=4](../reports/validation/workbench-run-dom-casmurro-prompt.html) | Índices reaproveitados | 3/3 | 14,748 s | 7,114 s | 6,070 s | 6 |

Os HTMLs ligados na tabela mostram **cada uma das 13 etapas**, os tempos anteriores dos artefatos, os estados, as respostas e a configuração. A espera na fila aparece separadamente. O tempo novo da ADPF retomada não inclui os 405,153 s de processamento anterior dos 57 pacotes; esse tempo fica registrado como histórico.

O prompt inicial se absteve mesmo quando a passagem recuperada continha a resposta. O novo prompt explicita quando preencher o JSON a partir de cabeçalhos, identificações e vínculos presentes no texto, sem exigir que a fonte repita a pergunta. Não fornece os valores do gabarito. Os dois prompts completos estão congelados nos dados exportados.

Nesta amostra, o novo prompt levou a seis respostas corretas e sustentadas pelo verificador local. A verificação passou a consumir cerca de seis segundos por run porque havia respostas preenchidas para conferir. Não se pode atribuir a diferença de tempo total entre o livro inicial e a nova receita apenas ao prompt: a primeira run construiu índices e a última os reaproveitou. Compare as etapas de extração, os estados de cache e as rodadas separadamente.

O resultado não demonstra que grafos superam busca sem grafo: ambas as receitas usam a variante F. Também não estima qualidade geral, p95, desempenho com modelos maiores ou custo de APIs externas. O próximo teste científico deve revisar os gabaritos, ampliar os campos, reservar casos e comparar variantes com/sem grafo sob o mesmo orçamento.

## Custo e recuperação

O custo de API local foi zero. Hardware e energia ficaram **não configurados**, sem serem apresentados como gratuitos. A interface permite uma tarifa/hora explícita para estimá-los; os seis testes não usaram essa tarifa.

Um encerramento forçado do terminal matou API e worker durante a construção da ADPF. O coordenador detectou a run interrompida. A construção seguinte reaproveitou os 57 pacotes completos e terminou; a repetição da run original preservou seus insumos e usou o índice completo. Nenhum registro antigo foi sobrescrito. [Auditoria da recuperação](../reports/validation/workbench-restart.json).

As primeiras construções ocorreram enquanto a plataforma era desenvolvida e não têm o arquivo de código inicial introduzido depois. As quatro runs seguintes já conservam `implementation.zip` e hashes de início/fim iguais. Por isso, esta bateria valida o funcionamento da plataforma e orienta os próximos experimentos; não é uma medição de latência em ambiente congelado. Reexecute a receita no commit entregue para uma nova referência de desempenho.

## Repetir a conferência

Use as instruções de instalação e execução em [PLATAFORMA-LOCAL.md](PLATAFORMA-LOCAL.md). Execute `tools/validate-workbench.ps1` para testes/build e `node tools/verify-workbench.cjs` para a interface, com Playwright e Edge disponíveis.

A auditoria de runs é somente leitura sobre os experimentos: `python tools/verify-workbench-runs.py --runs <ids>`. Ela gera os arquivos de evidência. Para a auditoria específica de retomada desta bateria, acrescente `--interrupted wb-7d775bc2b17147a98a1736528d134897 --retry wb-522c877dc5584aa99bbf05a291536eae` e inclua a run `wb-8e2e9973323b4efa9106bc50e274bcc1`, que reutilizou os checkpoints.

Os relatórios e evidências selecionados estão no repositório; PDFs, modelos, SQLite e execuções completas permanecem locais. O benchmark histórico `full` e seus índices não foram substituídos.
