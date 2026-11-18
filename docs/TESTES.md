# Pipeline de testes e benchmark

[Plano](PLANO.md) · [Diagrama](arquitetura.html) · [Métricas](METRICAS.md)

## Casos e referência

Proposta inicial de 40 campos ou perguntas, com 24 judiciais e 16 literários. Distribuir entre recuperação literal, cronologia, evidências distantes, síntese, listas, conflitos e informação ausente. Cada caso guarda resposta esperada ou rubrica, evidências e escopo documental.

Reservar aproximadamente um terço dos casos para a avaliação final. As anotações preliminares preparadas pelo agente devem ser identificadas como tal e acompanhadas das fontes. Guardar correções de referência com versão. Evitar ajustar prompts a partir dos erros do conjunto reservado.

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

- Teste rápido com páginas selecionadas e poucos campos dos dois documentos.
- Benchmark completo com as 433 páginas judiciais e 105 páginas literárias.
- Regressão com o mesmo corpus, referências e configuração de execuções anteriores.

Falhas de referência, infraestrutura, recuperação e geração devem ter causas registradas para permitir a investigação do resultado. Dados simulados só podem validar contratos e contabilidade. Resultados de qualidade precisam vir dos documentos reais.

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

Registrar uma indexação nova e uma execução com reaproveitamento. Proposta de três repetições da extração por configuração, com ordem, seed quando suportada, estado de aquecimento, cache, modelos e versões registrados.

## Métricas de qualidade

- Acerto por campo e taxa de JSONs válidos.
- Recuperação de todas as evidências necessárias dentro do orçamento.
- Validade da localização de citações e suporte semântico das respostas.
- Precisão e cobertura das listas.
- Abstenção correta e frequência de valores sem suporte.
- Taxa de conflitos e de encerramento por limite.
- Tempo, tokens, chamadas MCP e custo por campo correto.

Métricas de cobertura exigem conjuntos de evidência anotados. Listas equivalentes podem variar de ordem e forma textual, conforme a rubrica. O avaliador deve distinguir uma localização válida de uma afirmação realmente sustentada.

## Critérios de aceite e análise

Os testes de contrato, isolamento, proveniência e contabilização devem passar para considerar uma execução tecnicamente válida. Falhas do benchmark devem constar do denominador, acompanhadas de sua causa.

Apresentar valores por caso, por corpus e por variante. Para a amostra inicial, apresentar mediana e intervalo observado entre repetições. A qualidade observada orienta a escolha do método, com o custo e a latência ao lado. O limiar anterior de ganho de 10 pontos percentuais para o grafo permanece uma hipótese de decisão a avaliar com a amostra, sem representar garantia de desempenho.
