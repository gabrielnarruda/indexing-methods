# Relatório de experimentos em documentos extensos

Leia primeiro o [relatório completo em linguagem simples](relatorio.html): método, recortes, prompts exatos, resultados, limites e próximos passos. A nova fase é o [workbench de testes](../../docs/WORKBENCH.md), com evolução de cada componente e avaliação controlada do grafo. As tabelas abaixo conservam as medições originais.

Estado Completo. 36/36 execuções e 720 avaliações de campos.

## Método

Corpus integral de 433 páginas da ADPF 54 e 105 páginas de Dom Casmurro. Trechos por página com orçamento de caracteres e sobreposição. Grupos contíguos geram resumos e relações por Qwen3 local. EmbeddingGemma produz vetores. OpenSearch recupera por BM25 e similaridade, com fusão RRF. Neo4j fornece passagens por entidades compartilhadas. Um cliente MCP real chama busca e leitura. O modelo extrai o valor e uma segunda chamada verifica o suporte. Citações são validadas contra o texto original.

## Resultados

| Corpus | Variante | Repetições | Exatidão | Mediana s | Intervalo s | MCP | Rodadas |
| --- | --- | --- | --- | --- | --- | --- | --- |
| adpf54 | A | 3 | 50.0% | 100.2 | 100.1–102.0 | 48.0 | 24.0 |
| adpf54 | B | 3 | 54.2% | 100.0 | 98.1–100.4 | 48.0 | 24.0 |
| adpf54 | C | 3 | 50.0% | 100.3 | 99.8–100.7 | 48.0 | 24.0 |
| adpf54 | D | 3 | 54.2% | 99.4 | 98.5–99.5 | 48.0 | 24.0 |
| adpf54 | E | 3 | 45.8% | 97.8 | 97.6–97.8 | 48.0 | 24.0 |
| adpf54 | F | 3 | 54.2% | 122.3 | 122.1–125.8 | 58.0 | 29.0 |
| dom-casmurro | A | 3 | 56.2% | 65.9 | 65.1–66.0 | 32.0 | 16.0 |
| dom-casmurro | B | 3 | 56.2% | 60.6 | 60.0–60.7 | 32.0 | 16.0 |
| dom-casmurro | C | 3 | 56.2% | 66.2 | 65.8–66.3 | 32.0 | 16.0 |
| dom-casmurro | D | 3 | 62.5% | 60.5 | 60.3–63.7 | 32.0 | 16.0 |
| dom-casmurro | E | 3 | 50.0% | 65.5 | 64.4–65.5 | 32.0 | 16.0 |
| dom-casmurro | F | 3 | 50.0% | 70.1 | 70.0–70.2 | 34.0 | 17.0 |

## Discussão

O enriquecimento consumiu 540.0 s, equivalente a 91.0% do tempo total de indexação. Das 352 propostas de relações, 165 foram descartadas por falha na localização da citação ou nos campos exigidos. O grafo final é esparso e sua cobertura precisa ser avaliada antes de atribuir erros apenas à travessia.

Todas as variantes compartilham a preparação completa do corpus. O tempo de indexação é medido uma vez por documento; este experimento não mede uma indexação mínima separada para cada variante. Resumo e relações são produzidos na mesma chamada, portanto seus custos não podem ser separados retrospectivamente.

A precisão semântica das relações do grafo não foi medida contra um gabarito de relações. A verificação automática da indexação cobre estrutura e localização da fonte; o benchmark de formulários mede um efeito indireto na recuperação e na extração.

No corpus adpf54, a maior exatidão automática observada foi 54.2% na variante F. Empates devem ser lidos junto da tabela de tempos e chamadas.

A diferença de D para B em adpf54 foi +0.0 pontos percentuais nesta avaliação.

A diferença de F para E em adpf54 foi +8.3 pontos percentuais; a tabela registra o custo em rodadas adicionais.

No corpus dom-casmurro, a maior exatidão automática observada foi 62.5% na variante D. Empates devem ser lidos junto da tabela de tempos e chamadas.

A diferença de D para B em dom-casmurro foi +6.2 pontos percentuais nesta avaliação.

A diferença de F para E em dom-casmurro foi +0.0 pontos percentuais; a tabela registra o custo em rodadas adicionais.

A variante F pode consumir até três vezes o número de rodadas de E. Esse contraste mede investigação com orçamento maior, não isola o efeito do agente sob custo total idêntico. A variante A também pesquisa metadados extraídos. O grafo utiliza resolução de nomes simples e uma travessia por entidades compartilhadas; resultados desta implementação não equivalem a uma avaliação de todas as técnicas GraphRAG.

O próximo experimento deve revisar as referências e separar uma amostra independente, testar perguntas que exijam evidências distantes, analisar os candidatos recusados pelo verificador e comparar modelos de validação. Segmentação por peças/capítulos e cobertura de listas devem ser avaliadas antes de ampliar a ontologia do grafo.

Os exemplos de atribuição incorreta mostram que esta configuração ainda não sustenta preenchimento judicial sem conferência. O controle de escopo deve distinguir o processo principal, processos citados, partes, intervenientes e posições individuais antes de aceitar uma resposta como resolvida.

As referências foram preparadas pelo agente e têm status provisório. O acerto usa aliases, tipos e comparação de listas; correspondência textual pode aceitar formulações semanticamente incorretas. Dois campos judiciais foram usados no teste preliminar, incluindo um marcado como held_out, portanto esta avaliação é exploratória. A conferência literal de citações e a verificação por modelo são medidas distintas de uma revisão humana. Os grupos de resumo usam orçamento de caracteres e representam dois níveis de recuperação. O corpus judicial cobre as peças reproduzidas no acórdão. Dois documentos limitam conclusões sobre generalização. Repetições com temperatura zero medem sobretudo estabilidade e tempo. O modelo de validação é o mesmo modelo da extração, com erros potencialmente correlacionados. OCR automático, correferência contextual e varredura exaustiva para listas ainda não estão implementados.

[Relatório interativo](relatorio.html) · [Medições](measurements.json)

## Qualidade detalhada

| Corpus | Variante | Preenchidos | Precisão | Página encontrada | Precisão listas | Cobertura listas | Abstenção estrita | Limites | Erros |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| adpf54 | A | 54 | 66.7% | 40.9% | 25.0% | 12.5% | 0.0% | 18 | 0 |
| adpf54 | B | 57 | 68.4% | 40.9% | 50.0% | 50.0% | 0.0% | 15 | 0 |
| adpf54 | C | 57 | 57.9% | 27.3% | 56.2% | 43.8% | 50.0% | 12 | 0 |
| adpf54 | D | 57 | 68.4% | 40.9% | 50.0% | 50.0% | 0.0% | 15 | 0 |
| adpf54 | E | 51 | 58.8% | 27.3% | 31.2% | 18.8% | 50.0% | 15 | 0 |
| adpf54 | F | 60 | 60.0% | 27.3% | 81.2% | 68.8% | 50.0% | 6 | 0 |
| dom-casmurro | A | 39 | 69.2% | 80.0% | 0.0% | 0.0% | 0.0% | 9 | 0 |
| dom-casmurro | B | 36 | 75.0% | 86.7% | 66.7% | 66.7% | 0.0% | 12 | 0 |
| dom-casmurro | C | 45 | 60.0% | 80.0% | 66.7% | 66.7% | 0.0% | 3 | 0 |
| dom-casmurro | D | 39 | 76.9% | 86.7% | 66.7% | 66.7% | 0.0% | 9 | 0 |
| dom-casmurro | E | 45 | 53.3% | 73.3% | 66.7% | 66.7% | 0.0% | 3 | 0 |
| dom-casmurro | F | 45 | 53.3% | 73.3% | 66.7% | 66.7% | 0.0% | 3 | 0 |

## Custos e testes

Indexação: 593.20 s; extrações: 3029.13 s acumulados. API local: zero BRL. Custo de máquina das extrações: não configurado. Downloads e preparação do ambiente estão fora desses totais.

25 testes; 0 falhas; 0 erros; 0 ignorados. Duração da suíte 2.905 s.

[Etapas CSV](stages.csv) · [Trilha de auditoria](audit.json.gz) · [Implementação e limites](../../docs/IMPLEMENTACAO.md)

## Falhas observadas

Campo requerente, variante F, execução extraction-20261118T224615-81a5a2: resposta "Conferência Nacional dos Bispos do Brasil – CNBB"; referência "Confederação Nacional dos Trabalhadores na Saúde". O modelo confundiu um pedido de intervenção como amicus curiae com a identificação da parte requerente. A citação foi localizada e o verificador semântico aprovou a proposta. Fonte citada: página 9.

Campo resultado, variante F, execução extraction-20261118T224615-81a5a2: resposta "improcedente"; referência "procedente". O modelo confundiu o julgamento de um precedente citado com o resultado da ação principal. A citação foi localizada e o verificador semântico aprovou a proposta. Fonte citada: página 39.

## Versão de entrega

O benchmark conserva seu código em frozen-inputs.zip. A versão de entrega acrescenta controles para entradas inválidas, sobreposição alta e falha na inicialização. Conteúdo e offsets dos 1.057 trechos foram comparados e permaneceram iguais. Os prompts e as funções de extração por campo não mudaram. [Verificação e extração adicional](../validation/release.json).
