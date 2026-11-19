# Próxima fase: workbench de recuperação e extração

Este é o roteiro solicitado para a próxima implementação. **Ainda não foi executado.** O [relatório explicado](../reports/full/relatorio.html#workbench) apresenta o contexto, as métricas existentes e este plano em linguagem simples.

## Objetivo e hipótese

Evoluir leitura de PDF, segmentação, prompts, modelos, extração do grafo, recuperação e preenchimento de JSON. Criar uma bancada que permita trocar cada peça e medir sua contribuição. Manter como entradas os mesmos dois PDFs: acórdão completo da ADPF 54 (433 páginas, não os autos completos) e Dom Casmurro (105 páginas). Preservar seus hashes.

A hipótese otimista de que grafos podem melhorar a recuperação deve ser investigada com um grafo mais robusto. O resultado atual não permite concluir que grafos não funcionam. Também não permite atribuir a baixa qualidade exclusivamente ao modelo pequeno, ao prompt ou à leitura: precisamos separar esses efeitos.

## Entregas por componente

| Frente | Trabalho do desenvolvedor | Comparação e métricas |
| --- | --- | --- |
| Referência | Revisar humanamente perguntas, respostas e evidências; anotar texto, estrutura, entidades e relações em amostras. Separar desenvolvimento e avaliação reservada antes dos ajustes. | Concordância da revisão; divergências resolvidas; cobertura por classe de pergunta. As repetições não contam como novas perguntas. |
| Leitura | Comparar PyMuPDF com parser que preserve estrutura; OCR quando necessário; conservar página, bloco, coordenadas e versão. Para OCR, usar cópias rasterizadas identificadas dos mesmos PDFs. | Erro de caracteres/palavras, ordem de leitura, tabelas, páginas vazias, tempo e custo por página; gabarito humano, não o extrator antigo como verdade. |
| Recortes | Implementar estratégias por caracteres/tokens, frases, parágrafos, capítulos e peças; ligação trecho–seção; vizinhos e sobreposição entre pacotes configuráveis. | Evidências partidas, duplicação, tokens, quantidade de vetores, espaço, tempo e Recall@k. Separar tamanho da unidade de busca do pacote de extração. |
| Prompts e modelos | Adaptadores para resumo, extração de relações, resposta e verificação. Versionar prompts e schemas. Verificar candidatos e documentação atuais antes da seleção. | Mesmo contexto para modelos diferentes; mesmo modelo para prompts diferentes; teste com evidência humana fornecida diretamente. Qualidade, uso, custo, latência e erros de formato. |
| Embeddings | Comparar modelo local com candidatos OpenAI/Google. Indexar documentos e consultas com espaços vetoriais compatíveis; testar dimensões e parâmetros recomendados para cada tarefa. | Recuperação em português e por classe de pergunta, espaço por vetor, tempo, custo, qualidade final com extrator fixo. Não inferir qualidade apenas do número de dimensões. |
| Construção do grafo | Separar resumo e relações; substituir teto arbitrário de seis por política de cobertura/orçamento; extrair menções, entidades, eventos, papéis, datas, atribuição, modalidade, negação e fontes. Resolver aliases, pronomes e homônimos sem fusões indevidas. | Precisão/cobertura de entidades e relações, papéis, datas e negação; correferência; suporte da citação; duplicatas, órfãos, densidade e custo por relação correta. Mais relações não implicam mais qualidade. |
| Navegação do grafo | Comparar grafo atual, grafo melhorado e subgrafo revisado por humano. Testar caminhos de múltiplas relações, filtros por papel/tempo/peça, limites de expansão e origem dos candidatos. | Evidências exclusivas do grafo, quantas chegam ao contexto, cobertura conjunta de múltiplas evidências, acerto final, tempo e custo incremental. |
| Recuperação | Linha de base lexical realmente sem enriquecimento, vetorial, híbrida, resumos, grafo, reranqueamento e leitura de vizinhos. | Recall@k, MRR/nDCG com relevância anotada, cobertura do conjunto de evidências, candidatos repetidos, latência e bytes. |
| Extração JSON | Consultas por campo, memória de evidências, conflito, listas completas, critérios de parada e validadores alternativos. Preservar null e motivo para pendências. | Acerto, precisão dos preenchidos, cobertura de listas, suporte das citações, abstenção, atribuição errada, falsas aprovações, chamadas MCP, rodadas e custo por campo correto. |
| Armazenamento | Interface local/objetos; texto/OCR completo e origem fora do índice; referências, termos pesquisáveis e vetores no índice. Leitura seletiva, cache e reconstrução versionada. | Bytes por página/documento, RAM, requisições, tráfego, cache, latência e custo total. Não confundir excluir da resposta com excluir do _source armazenado. |

O núcleo do grafo deve ser genérico, com extensões para jurídico e literatura. No jurídico, distinguir processo principal, precedentes citados, partes, intervenientes, alegações, votos e decisão. Na literatura, preservar narrador, personagem, fala e evento. Todas as relações devem apontar para evidências verificáveis. Confiança declarada pelo modelo não equivale a probabilidade calibrada.

## Matriz de experimentos

1. Reproduzir a configuração atual como referência histórica, sem sobrescrever o experimento `full`.
2. Avaliar as peças isoladas contra amostras revisadas. Testar o extrator com evidências corretas fornecidas diretamente.
3. Trocar um fator por vez: parser, segmentação, prompt, modelo, embedding, construção do grafo, travessia e reranqueamento. Registrar parâmetros e resultados negativos.
4. Testar as interações relevantes, especialmente prompt × modelo e construção do grafo × navegação. Não é preciso executar todas as combinações possíveis; a seleção deve ser registrada antes da avaliação reservada.
5. Comparar variantes com e sem grafo mantendo o mesmo extrator e entradas. Fazer um contraste com igual orçamento de contexto e outro com teto de custo ou tempo. Reportar custos reais e limites atingidos.
6. Comparar investigação iterativa com leitura ampliada sob orçamento equivalente. Usar uma bateria de perguntas simples, papéis, negação, conflito, listas e múltiplas evidências distantes.
7. Congelar a seleção e avaliar a parte reservada. Usar repetições para estabilidade e latência, não para inflar o tamanho da amostra independente.
8. Analisar diferenças pareadas por pergunta, por tipo e por documento. Intervalos de incerteza devem respeitar essa unidade; dois documentos não demonstram generalização para todo processo ou romance.

Se o subgrafo revisado ajudar e o automático não, priorizar a construção. Se ambos recuperarem evidências corretas e o JSON falhar, priorizar extração/verificação. Se o candidato correto existir mas for eliminado antes do contexto, priorizar seleção/reranqueamento. Não prometer um percentual de melhora antes do experimento.

## Instrumentação obrigatória

- Identidade: run_id, commit, hashes dos PDFs e dos artefatos derivados, versões de parser, recortes, modelos, prompts, schemas, índice e grafo.
- Configuração: estratégias, parâmetros, seeds, limites de contexto/rodadas, concorrência, estado de aquecimento e política de cache.
- Tempo: duração por etapa e tempo total; p50/p95 quando houver amostra suficiente. Tempos inclusivos não devem ser somados como se fossem disjuntos.
- Uso: tokens de entrada/saída e, quando fornecidos, cache/raciocínio; chamadas de modelo, rodadas do controlador e chamadas MCP separadas; erros, retentativas e limites.
- Custo: API por operação faturável, preços e data da tabela, hardware/energia com tarifa explícita ou “não configurado”; cache e retentativas. Separar medido de projetado e contabilizar cada custo uma vez.
- Indexação: tempo/custo de cada componente, taxa de reutilização, documentos/páginas/trechos, propostas/aceitas/rejeitadas e espaço. Resumo e grafo devem ter chamadas/etapas separadas para permitir comparação de custos.
- Recuperação: consultas, rankings por canal, IDs, scores, filtros, trilhas do grafo, conteúdo selecionado e evidências novas por componente.
- Extração: proposta inicial, resultado final, suporte literal/semântico, campo, citações, status e motivo de parada.

## Interface do workbench

O painel deve permitir configurar, salvar, executar e comparar variantes. Exibir qualidade × custo × tempo, com filtros por documento, classe de pergunta e versão. Cada campo deve abrir o caminho pergunta → consultas → candidatos → caminhos no grafo → trechos → proposta → validação → resultado. Disponibilizar JSON, CSV, HTML e as configurações necessárias para reproduzir a execução.

Mostrar vínculos de evidência até a página original; comparar grafos e explicar mudanças de entidade/relação. Custos desconhecidos não aparecem como zero. Execuções parciais e erros não desaparecem dos totais. Reexecuções só reutilizam cache quando entradas e configuração correspondem.

## Pipeline de testes e critérios de conclusão

Executar: contratos unitários → integração com bancos/MCP → teste curto ponta a ponta → avaliação das peças → ablações → combinações selecionadas → bateria reservada → relatório e revisão dos erros.

Antes da bateria reservada, definir e registrar limites de qualidade por campo, tolerância a resposta sem suporte, custo, latência e cobertura de listas. Não adotar um limiar numérico arbitrário como garantia de segurança. Testes de software aprovados não substituem avaliação semântica.

O workbench estará entregue quando houver componentes substituíveis, matriz reproduzível, métricas reconciliadas e painel com investigação por campo. O método só poderá ser escolhido após mostrar ganhos e regressões com os mesmos casos e orçamento declarado. Mesmo a nova bateria permanece limitada a estes dois documentos; avaliação de generalização e carga de produção fica para uma fase posterior.

## Escopo desta revisão

Esta revisão atualiza o relatório e orienta a próxima fase. Não muda os modelos, prompts, recortes ou resultados do benchmark já executado. Não implementa nem mede ainda o novo workbench. S3 e APIs externas continuam como opções futuras, não componentes usados no resultado histórico.
