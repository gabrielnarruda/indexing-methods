# Pipeline de testes e benchmark

[Plano](PLANO.md) · [Diagrama](arquitetura.html) · [Métricas](METRICAS.md)

## Casos e referência

Foram implementados 40 campos: 24 judiciais e 16 literários. Há recuperação literal, datas, relações, listas e três perguntas sobre informação ausente. Cada caso guarda resposta esperada, aliases quando aplicáveis, páginas de referência e escopo documental. Conflitos e síntese ampla ainda não possuem casos anotados suficientes para uma avaliação dedicada.

O arquivo de referências marca cerca de um terço dos campos como `held_out`. Contudo, o campo `relator`, que estava nessa divisão, também foi usado no teste preliminar de contrato de resposta, junto de `identificacao`. Por isso, este relatório é uma avaliação exploratória e não uma avaliação final inteiramente cega. As anotações foram preparadas pelo agente, têm páginas de fonte e permanecem provisórias, sem revisão humana. A configuração foi congelada antes do benchmark completo, sem ajustes a partir dos resultados por variante.

## Testes automatizados

| Área | Casos | Critério |
| --- | --- | --- |
| Schema | Tipos, campos obrigatórios, listas e ausência | Aceitar entradas válidas e reportar violações |
| Ingestão | Texto vazio, corte entre páginas, localização e cobertura | Toda evidência aponta para a versão correta do documento |
| Armazenamento | Reindexação, retomada e falha parcial | Identificadores consistentes e ausência de duplicação |
| Isolamento | Consulta com outro corpus e IDs externos | Recuperação restrita ao corpus solicitado |
| Grafo | Relações sem fonte, menções ambíguas e travessia | Relações utilizáveis possuem evidências válidas |
| MCP | Inicialização, descoberta, ferramentas e argumentos inválidos | Executar pelo protocolo real e devolver erros identificáveis |
| Extração | Literal, várias evidências, conflito, ausência e lista | Valores e estados coerentes com a referência |
| Limites | Timeout, repetição de busca, indisponibilidade e saída inválida | Encerrar com resultado parcial e motivo |
| Telemetria | Cache, erro, repetição e duração sobreposta | Contabilizar operações uma vez e preservar falhas |

## Níveis de execução

- Teste rápido com dois campos judiciais sobre o índice completo.
- Benchmark completo com as 433 páginas judiciais e 105 páginas literárias.
- Regressão com o mesmo corpus, referências e configuração de execuções anteriores.

Falhas de referência, infraestrutura, recuperação e geração devem ter causas registradas para permitir a investigação do resultado. Dados simulados só podem validar contratos e contabilidade. Resultados de qualidade precisam vir dos documentos reais.

## Pipeline executável e cobertura atual

`tools/validate.ps1 -Full -Name local` encadeia download/verificação, indexação, testes, benchmark, relatório e auditoria das saídas. Os 25 testes automatizados compreendem 21 verificações de contrato/limites e quatro integrações reais: sessão MCP, ponto de entrada para cliente externo e integridade de cada corpus nos dois bancos. O arquivo [JUnit](../reports/validation/junit.xml) registra o resultado da suíte.

A auditoria `tools/verify_run.py` confere todos os formulários completos, tipos dos valores, origem e página das citações de campos preenchidos, limites de rodadas, relações entre spans, contagens de chamadas, custos e igualdade dos JSONs exportados. Essa auditoria não atesta a correção semântica das respostas. `tools/verify-html.cjs` usa Playwright e Edge para verificar os diagramas, filtros, navegação pelo grafo, calculadora de custos e layout móvel; depende de Node e Playwright disponíveis.

Os testes de timeout, saída truncada e cache usam transporte HTTP simulado para verificar comportamento e contabilidade de forma determinística. Os testes MCP abrem cliente e servidor reais e consultam o índice publicado. Foram medidas uma indexação inicial e uma reutilização completa por corpus. Não foi executada uma campanha de desligamento forçado dos contêineres durante a gravação; a presença de checkpoints não deve ser interpretada como comprovação de recuperação para toda falha possível.

## Variantes

| Código | Recursos habilitados |
| --- | --- |
| A | BM25 |
| B | Busca híbrida lexical e vetorial |
| C | Busca híbrida e resumos hierárquicos |
| D | Busca híbrida e travessia do grafo |
| E | Busca híbrida, hierarquia e grafo |
| F | Variante E e investigação iterativa |

Usar o mesmo modelo extrator e orçamento comparável de evidências. Os dados extraídos usados como metadados estarão disponíveis em B e D. A comparação D contra B mede a contribuição da travessia.

O benchmark usa três repetições por configuração, ordem embaralhada com seed 42 e seeds de geração 42, 43 e 44. A temperatura é zero, portanto seeds distintas não garantem respostas estocasticamente independentes. Modelos já estavam carregados após a indexação e os testes preliminares. Embeddings de consultas podem ser reutilizados; geração e validação semântica sempre executam. O manifesto preserva hashes de código, configuração, formulários, referências e índices.

## Métricas de qualidade

- Acerto por campo e taxa de JSONs válidos.
- Recuperação de todas as evidências necessárias dentro do orçamento.
- Validade da localização de citações e suporte semântico das respostas.
- Precisão e cobertura das listas.
- Abstenção correta e frequência de valores sem suporte.
- Taxa de conflitos e de encerramento por limite.
- Tempo, tokens, chamadas MCP e custo por campo correto.

Métricas de cobertura exigem conjuntos de evidência anotados. Listas equivalentes podem variar de ordem e forma textual, conforme a rubrica. O avaliador deve distinguir uma localização válida de uma afirmação realmente sustentada.

Nesta versão, `reference_page_hit` verifica se alguma página de referência foi recuperada; não mede cobertura completa de todas as evidências. A exatidão de strings aceita aliases por correspondência textual normalizada e pode produzir falsos positivos em respostas contraditórias. Listas exigem todos os itens esperados, mesmo tamanho e ausência de duplicatas. Os resultados ficam disponíveis para revisão por campo. JSON válido, citação localizada e resposta correta são critérios distintos.

## Critérios de aceite e análise

Os testes de contrato, isolamento, proveniência e contabilização devem passar para considerar uma execução tecnicamente válida. Falhas do benchmark devem constar do denominador, acompanhadas de sua causa.

Apresentar valores por caso, por corpus e por variante. Para a amostra inicial, apresentar mediana e intervalo observado entre repetições. A qualidade observada orienta a escolha do método, com o custo e a latência ao lado. O limiar anterior de ganho de 10 pontos percentuais para o grafo permanece uma hipótese de decisão a avaliar com a amostra, sem representar garantia de desempenho.
