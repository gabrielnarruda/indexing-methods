# Métricas e custos

Cada execução recebe um run_id, configuração congelada, hashes do corpus e identificadores das versões dos índices e modelos. Eventos usam relógio monotônico para duração e horário UTC para ordenação e auditoria.

A tabela abaixo descreve o modelo de observabilidade. Na implementação atual, corpus e versão também são recuperáveis pelo manifesto da execução; `operation` identifica a ferramenta MCP. Não existe versão de preço externo porque todas as inferências são locais.

## Registro por operação

| Campo | Finalidade |
| --- | --- |
| run_id, span_id, parent_span_id | Correlacionar execução e etapas |
| corpus_id, document_id, index_version | Identificar os dados utilizados |
| field_path, round_index | Localizar campo e rodada |
| stage, operation, tool_name | Identificar etapa e ferramenta MCP |
| started_at, duration_ms, status | Medir tempo e resultado |
| model, model_digest | Reproduzir a configuração efetiva |
| input_tokens, output_tokens | Medir uso quando informado pelo modelo |
| cache_hit, attempt, error_type | Registrar reaproveitamento e falhas |
| api_cost, currency, pricing_version | Identificar custo e regra usada |

Valores de tokens indisponíveis devem permanecer ausentes e ser sinalizados. Qualquer contagem estimada precisa ser identificada como estimativa.

## Tempos

Indexação mede leitura, OCR, segmentação, embeddings, resumos, extração de entidades e relações, gravação e validação dos índices. Extração mede busca, leitura, travessia, modelo, validação e total por campo.

Nas medições desta versão, leitura e segmentação entram em `parse`; resumo e relações são gerados na mesma chamada `enrichment`. OCR é somente detectado, sem execução. As demais etapas são `embedding`, `search_index`, `graph_index`, `retrieval`, `query_embedding`, `graph_retrieval`, `generation`, `support_validation` e `validation`. Inicialização de clientes e verificações finais aparecem no tempo total e podem não possuir span individual.

O total decorrido é medido no nível da execução. Etapas podem conter subetapas ou sobrepor-se. A apresentação mostra essa estrutura para evitar interpretar a soma de tempos inclusivos como tempo total.

## Iterações

Uma rodada corresponde a uma tentativa de resolver ou reavaliar um campo. Uma rodada pode executar várias ferramentas. O relatório apresenta contagem de rodadas, chamadas MCP por ferramenta, chamadas de modelo e tentativas repetidas após erro.

`mcp_calls` conta invocações de ferramentas, incluindo as que devolvem erro. Inicialização da sessão e descoberta com `list_tools` ficam fora dessa contagem; seu tempo participa do total da execução. Travessias internas da busca aparecem em `graph_retrieval`, sem criar uma chamada MCP adicional.

O campo agregado `errors` conta spans terminados com erro. Uma exceção propagada pode marcar mais de um span; essa contagem não equivale ao número de incidentes independentes. Campos com status `error` são contabilizados separadamente na avaliação.

## Custo

A configuração local tem cobrança de API igual a zero. Custo de máquina é calculado pela duração da execução multiplicada pela tarifa horária explicitamente informada. Sem tarifa, o valor é não configurado.

Custos por token de provedores externos só serão usados se um provedor for escolhido futuramente e sua tabela for registrada. Uma simulação de preço deve ficar identificada como projeção. Energia exige medida ou hipótese explícita de potência e tarifa.

Custos são registrados uma vez por operação faturável e agregados para indexação, extração e corpus. Retentativas que efetivamente consumiram modelo entram no total. Cache registra o trabalho reaproveitado e o custo incremental da consulta.

## Visualização

O relatório apresenta comparação por variante e uma trilha por campo. Deve permitir inspecionar pergunta, consultas, passagens, candidatos, valor final, validações, tempos e motivo de encerramento. Exportações JSON e CSV preservam os dados utilizados para gerar as tabelas.
