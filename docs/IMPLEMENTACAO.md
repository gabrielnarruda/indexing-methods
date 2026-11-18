# Implementação da PoC

## Caminho dos dados

1. `fetch` obtém os dois PDFs, verifica formato e páginas e preserva os hashes.
2. `index` extrai blocos de texto e coordenadas de cada página com PyMuPDF. Blocos de texto idênticos dentro da mesma página são deduplicados.
3. Cada página produz trechos de até 1.800 caracteres, com 200 de sobreposição. Os cortes procuram espaços. O identificador inclui corpus, hash do PDF, página e posição inicial.
4. Grupos contíguos com orçamento aproximado de 10 mil caracteres geram um resumo e até seis afirmações. Qwen3:4b executa no Ollama, com temperatura zero e raciocínio explícito desativado.
5. Uma afirmação só entra no grafo se trouxer sujeito, predicado, objeto e citação que exista no trecho indicado. Isso valida a localização da citação; não demonstra automaticamente a correção semântica da relação extraída.
6. EmbeddingGemma:300m vetoriza trechos e resumos completos, em lotes de 16, com truncamento desativado. O embedding nunca substitui o texto original por um resumo quando falta espaço: a chamada falha de forma observável.
7. OpenSearch e Neo4j recebem os dados versionados. A versão é publicada após conferir contagens e vínculos. Uma reexecução verifica ambos os armazenamentos antes de reutilizar a versão.

## Busca e grafo

OpenSearch usa análise de português para texto e metadados. A busca vetorial desta amostra faz comparação exata de cosseno. A fusão RRF usa constante 60 e até 12 candidatos por canal. O contexto entregue ao extrator tem até quatro trechos por rodada.

As variantes com resumos pesquisam os três resumos mais relevantes por busca lexical e incluem seus trechos filhos na fusão. São dois níveis de recuperação, com grupos por orçamento de caracteres. Não há árvore recursiva nem detecção de capítulos ou peças processuais nesta versão.

O Neo4j contém `Chunk`, `Entity` e `Fact`. Uma entidade liga-se a uma afirmação como sujeito ou objeto; a afirmação liga-se ao trecho por `EVIDENCED_BY`. Predicado, data, autor e citação ficam na afirmação. A resolução de entidades normaliza espaços e caixa dentro da versão do corpus. Não há resolução contextual robusta de homônimos, pronomes ou aliases.

A travessia parte dos quatro primeiros candidatos, segue entidades compartilhadas e retorna outros trechos, ordenados por quantidade de afirmações conectadas. Os candidatos entram na mesma fusão RRF. A travessia pode não alterar o resultado final; o benchmark mede esse efeito. Os metadados extraídos ficam disponíveis para todas as variantes, inclusive a lexical A. Assim, A significa BM25 sobre texto e metadados, não um índice sem enriquecimento.

## MCP e extração

O cliente abre um servidor por formulário via stdio, inicializa a sessão e descobre quatro ferramentas: `search_passages`, `read_passages`, `list_sections` e `follow_links`. O controlador deste experimento chama busca e leitura em cada rodada. A travessia ocorre dentro da busca quando a variante a habilita. Não há supervisor com múltiplos agentes independentes.

`tools/serve_mcp.py --corpus adpf54` é o ponto de entrada para clientes MCP externos. Ele cria a execução de métricas automaticamente e instrumenta as chamadas recebidas. O benchmark mantém sua instrumentação no cliente para correlacionar cada chamada com campo e rodada. O ponto de entrada externo foi verificado em um teste de integração separado.

Cada pergunta parte do formulário, sem acesso às respostas de referência. O modelo propõe valor, estado, citações e próxima consulta. JSON Schema verifica tipos; o verificador literal exige que cada citação pertença a um dos trechos fornecidos. Uma segunda chamada do mesmo modelo avalia o suporte semântico.

A variante F permite até três rodadas, enquanto A–E executam uma. Uma rodada adicional usa consulta sugerida pelo modelo ou uma consulta de recuperação após erro de validação. Consultas repetidas encerram o campo. Para combinar evidências, uma rodada posterior pode manter um trecho anterior e três novos. O orçamento por rodada é comparável; F dispõe de maior orçamento total, declarado na análise.

O formulário final contém valores ou `null`. `fields.json` distingue `filled`, `not_found`, `conflicting`, `limit_reached` e `error`. `not_found` significa não localizado nas evidências consultadas. Erros de um campo preservam resultados já produzidos. Falha ao inicializar o servidor pode encerrar o formulário inteiro.

## Persistência, limites e segurança local

As versões de índice dependem do hash do documento, configuração e digests de modelos. Chamadas de indexação e embeddings usam cache; respostas de extração e verificação semântica não usam cache. Os arquivos de checkpoints são substituídos atomicamente. Cada processo escreve seu próprio JSONL de eventos, com correlação entre cliente e servidor MCP.

O timeout HTTP é de 300 segundos e falhas de conexão/timeout do modelo permitem duas tentativas. O timeout de uma chamada MCP é de 330 segundos. Não existe prazo total rígido por formulário. Execuções concorrentes da indexação do mesmo corpus não são suportadas por lock; execute uma por vez.

Após o benchmark, a versão de entrega passou a rejeitar seleções de campos vazias/desconhecidas, registrar falhas durante a inicialização e garantir avanço do corte mesmo quando a sobreposição se aproxima do tamanho do trecho. O snapshot experimental permanece arquivado. A comparação dos 1.057 trechos confirmou conteúdo e offsets idênticos com a configuração usada; os prompts e funções de extração por campo não foram alterados.

Os contêineres vinculam portas a `127.0.0.1`. OpenSearch e Neo4j estão sem autenticação para esta PoC local. Os documentos são instruídos como dados nos prompts; isso não constitui uma defesa comprovada contra prompt injection. As ferramentas do experimento só recuperam e leem dados locais.

## Diferenças entre plano e implementação

| Tema do plano | Estado nesta versão |
| --- | --- |
| OCR | Detecta páginas com menos de 20 caracteres e interrompe a publicação; OCR automático não implementado |
| Hierarquia estrutural | Agrupamento contíguo por caracteres, com dois níveis; sem classificação de peças ou capítulos |
| Entidades e eventos genéricos | Afirmações com sujeito, predicado, objeto, data e autor; sem ontologia completa ou correferência |
| Datas do evento e registro | Uma data textual por afirmação; separação temporal ainda não implementada |
| Listas completas | Schema, citações e avaliação de precisão/cobertura; sem varredura exaustiva ou garantia de completude |
| Coordenadas | Blocos de página preservam bounding boxes; citações da resposta usam página, trecho e offsets, sem realce em PDF |
| Avaliação independente | Referências provisórias anotadas pelo agente; sem revisão humana e sem avaliação final inteiramente cega |
| Custos | Uso e tempos medidos; API local zero, hardware/energia sem tarifa informada |
| Novos documentos | Núcleo sem ontologia obrigatória por domínio; CLI e matriz do benchmark enumeram os dois corpora desta PoC e precisam ser ampliadas para novas entradas |

Essas limitações fazem parte do resultado da PoC. Expandir o corpus, revisar as referências e testar resolução de entidades e cobertura de listas são os próximos passos antes de uso operacional.
