# Plano da plataforma local de experimentos

Status: plano de referência, com a primeira plataforma funcional implementada. O escopo efetivamente entregue, comandos, evidências e limites ficam em [PLATAFORMA-LOCAL.md](PLATAFORMA-LOCAL.md); o restante deste documento conserva o roteiro de evolução e não deve ser interpretado como uma lista de recursos já disponíveis. Escopo confirmado: uso local individual, interface no navegador, modelos locais e opção futura de APIs externas. Os conjuntos de dados continuam sendo o acórdão da ADPF 54 e Dom Casmurro, com os hashes registrados.

[Abrir o protótipo interativo de UI/UX](prototipo-plataforma.html). A interface permite experimentar o fluxo localmente com dados fictícios, antes da implementação do motor de execução. O [escopo do protótipo](PROTOTIPO.md) descreve as interações e a conferência realizada.

## 1. O produto que queremos

Uma bancada para criar versões de uma receita de processamento, executar essas receitas sobre documentos e comparar qualidade, tempo e custo. O usuário deve conseguir mudar prompt, modelo, embedding, recortes e estratégia de busca pela interface, sem editar arquivos Python.

Fluxo principal:

1. Selecionar documentos e conjunto de perguntas/gabarito.
2. Duplicar uma configuração existente ou criar uma nova.
3. Escolher quais parâmetros variar e quais manter fixos.
4. Conferir a matriz: quantidade de combinações, etapas novas, etapas reaproveitadas e estimativa de uso/custo.
5. Executar um caso pequeno, uma etapa isolada ou a bateria selecionada.
6. Acompanhar fila, etapas, custos conhecidos, erros e limites.
7. Comparar com uma referência e abrir qualquer campo para entender a diferença.
8. Salvar uma configuração candidata, exportar resultados e executar sua avaliação reservada.

O principal recurso não é apenas um editor de prompts: é a ligação rastreável entre configuração, artefatos produzidos, execução, evidência e avaliação.

## 2. Conceitos que aparecerão na interface

| Conceito | Significado |
| --- | --- |
| Documento | PDF original e sua identidade por hash; pode ter várias versões de texto extraído. |
| Conjunto de dados | Seleção versionada de documentos, perguntas, schemas e referências. |
| Configuração | Receita editável em rascunho: componentes, versões, parâmetros e limites. |
| Versão da configuração | Fotografia imutável da receita ao ser executada; alterações posteriores criam outra versão. |
| Experimento | Pergunta que queremos testar, referência de comparação, eixos de variação e bateria de execuções. |
| Run | Uma execução de uma configuração, sobre um documento/conjunto definido, com uma repetição identificada. A bateria terá runs por documento. |
| Etapa / tentativa | Trabalho de uma peça, como embedding. Retentativa é registrada dentro da etapa e não conta como nova repetição experimental. |
| Artefato | Resultado versionado: texto, recortes, embeddings, grafo, índice, evidências, JSON ou relatório. |
| Avaliação | Comparação de resultados com uma versão de gabarito e avaliador. Reavaliar gera um novo registro, preservando a avaliação anterior. |

A comparação deve mostrar exatamente o que mudou entre versões. Credenciais não fazem parte da receita exportada; ela guarda apenas referência ao provedor/credencial configurado localmente.

## 3. Telas da primeira versão

### Biblioteca e referências

Importar os dois documentos existentes; abrir PDF e texto extraído lado a lado; selecionar páginas; inspecionar recortes e estrutura; registrar falhas de leitura. Editar formulários JSON, perguntas, tipos e regras de ausência. Revisar respostas de referência, relações do grafo e evidências com estado “provisório” ou “revisado”.

Separar conjunto de desenvolvimento de conjunto reservado. Gabaritos não entram na indexação nem nos prompts de execução. Anotações precisam apontar para documento/página/trecho de fonte, não depender só do ID de um chunk que muda quando trocamos a segmentação.

### Configurações

Editor por etapas com controles adequados ao componente. Selecionar provedor/modelo, editar prompt com variáveis permitidas, validar schema, conferir tokens de uma amostra e visualizar o pedido final renderizado. Salvar rascunho, duplicar, comparar versões e testar uma amostra.

Prompts de resumo, entidades/relações, resposta JSON e verificação são independentes. Modelos e parâmetros também. Campos não suportados pelo provedor devem aparecer como incompatíveis antes da execução.

### Experimentos paramétricos

Selecionar uma configuração base e eixos: por exemplo, dois prompts, dois modelos de extração, dois embeddings e três valores de top_k. A interface expande a matriz, mostra combinações inválidas, etapas compartilhadas e orçamento. Permite executar seleção manual, variação de um fator por vez ou produto cartesiano limitado.

Exemplo ilustrativo: 2 × 2 × 2 × 3 = 24 configurações; em dois documentos e três repetições, 144 runs de documento. Isso não exige 144 indexações completas: o planejador compartilha artefatos compatíveis.

### Execuções

Fila e detalhe com estados por etapa, progresso real, tempo decorrido, chamadas, uso, erros e artefatos. Ações: iniciar, cancelar, repetir, retomar etapas incompletas e duplicar configuração. Cancelamento interrompe novas operações e preserva o parcial; uma chamada externa já enviada pode terminar e ser cobrada.

Fechar a aba não encerra o trabalho. Reiniciar a aplicação identifica trabalhos interrompidos e oferece retomada verificável. Estado não depende apenas da memória do processo.

### Comparação

Selecionar uma referência e candidatos. Tabela com qualidade, custo e tempo; diferença de parâmetros; gráfico qualidade × custo, com tempo visível; resultados por documento, tipo de pergunta e campo. Separar execuções com orçamento/cache distintos e explicitar essa diferença.

Cada campo abre uma comparação lado a lado: pergunta, resposta, referência, citações, consultas, candidatos por canal, caminhos do grafo, trechos efetivamente lidos, verificações e motivo de parada. Identificar ganhos, regressões e respostas igualmente erradas.

### Laboratório do grafo

Selecionar versão de construção e versão da navegação separadamente. Inspecionar entidades, menções, eventos, papéis e evidências; comparar duas versões; revisar amostras; visualizar quais caminhos trouxeram uma evidência nova. A construção do grafo tem métricas próprias, mesmo sem rodar um formulário final.

## 4. Parâmetros substituíveis

| Etapa | Controles previstos |
| --- | --- |
| PDF / OCR | Parser, OCR quando aplicável, idioma, páginas, extração de tabelas e estrutura. |
| Segmentação | Estratégia, unidade caracteres/tokens, tamanho, sobreposição, limites de página/peça/capítulo, contexto de vizinhos. |
| Pacote para extrair relações | Tamanho e sobreposição próprios; organização dos chunks e orçamento de contexto. Independente da unidade de busca. |
| Resumo | Habilitação, prompt, modelo, parâmetros e nível estrutural. |
| Entidades e relações | Prompt, schema/ontologia, modelo, política de cobertura, papéis, citações e limites. |
| Resolução de entidades | Estratégia de aliases/correferência, critérios de união, conflitos e revisão. |
| Embedding | Provedor/modelo/versão, dimensão quando suportada, preparação do texto e configuração query/document. |
| Índice | Campos, análise textual, armazenamento de fonte, método vetorial e parâmetros de indexação. |
| Recuperação | BM25, vetorial, híbrida, resumos, grafo; filtros, top_k por canal e final, fusão, reranqueamento. |
| Grafo na busca | Entidades iniciais, tipos de ligação, profundidade, direção, orçamento de expansão, tempo/papel/peça. |
| Extração JSON | Modelo, prompt, schema do formulário, contexto, parâmetros suportados e tratamento de conflitos/listas. |
| Investigação | Estratégia de próxima consulta, memória, limite de rodadas, ferramentas, tokens e tempo. |
| Verificação | Regras determinísticas, verificador semântico, modelo, prompt, rubrica e política de abstenção. |
| Avaliação | Versão do gabarito, regras por tipo de campo, avaliação de listas, suporte das citações e revisão humana. |

Cada componente possui contrato de entrada/saída, identidade de versão, validação dos parâmetros e produtor de métricas. Prompts são dados; a interface não executa código Python arbitrário fornecido pelo usuário.

## 5. Arquitetura proposta

```text
Interface no navegador: React + TypeScript
                  |
API local Python: FastAPI
                  |
Planejador de dependências + coordenador de execuções persistente
          |                       |
     SQLite local             Workers Python
  configurações, runs,       etapas e adaptadores
  avaliações e fila               |
          |            +----------+-----------+-------------+
          |            |          |           |             |
     Artefatos       Modelos   OpenSearch    Neo4j     Leitura de PDFs
   em arquivos       locais/    versões     versões     e avaliação
   identificados     APIs      de índice   de grafo
     por hash
```

- **Interface:** React + TypeScript, empacotada com Vite, para edição, comparação e inspeção. O build pode ser servido pela API local; não depende de hospedagem.
- **API e processamento:** Python para reaproveitar o núcleo existente. A API valida pedidos e consulta estado; um processo coordenador e workers executam tarefas demoradas fora do ciclo de uma requisição web.
- **Metadados:** SQLite em disco local, com transações curtas e coordenação das escritas. Guardar configuração, fila, dependências, referências aos artefatos e resultados de avaliações. Eventos volumosos e arquivos grandes ficam no armazenamento de artefatos.
- **Arquivos:** PDFs, texto/OCR, chunks, vetores exportáveis, propostas do grafo, evidências e respostas com manifesto e checksum. Interface de armazenamento permite acrescentar objetos/S3 mais adiante.
- **Busca e grafo:** preservar OpenSearch e Neo4j. Versões de runs não podem ler a “versão ativa” global de outro experimento. Toda leitura recebe explicitamente a versão do artefato/índice/grafo.
- **Modelos:** adaptadores para Ollama e APIs externas configuradas. Registrar modelo solicitado, versão efetivamente informada e uso disponível. Seed não garante saída idêntica em todos os provedores.
- **Operação local:** serviços vinculados ao loopback; segredos no ambiente ou armazenamento local de credenciais, fora de logs, Git e exports. Requisições de execução vão à API local com validação de origem e proteção contra chamadas de páginas externas.

As versões de dependências serão fixadas na implementação. Decisões de stack apoiadas na documentação oficial: [React/Vite](https://react.dev/learn/build-a-react-app-from-scratch), [tarefas demoradas no FastAPI](https://fastapi.tiangolo.com/tutorial/background-tasks/), [uso local do SQLite](https://www.sqlite.org/whentouse.html), [concorrência e limitações do WAL](https://www.sqlite.org/wal.html). SQLite fica no mesmo computador; não será colocado em pasta de rede para compartilhar a fila.

## 6. O núcleo: recalcular só o que depende da mudança

```text
PDF → texto/estrutura → chunks ┬→ embeddings → índice vetorial ┐
                              ├→ índice textual               ├→ busca
                              ├→ resumos → índice de resumos  ┤    |
                              └→ pacotes → relações           |    v
                                           → entidades → grafo┘ evidências
                                                                  |
                                                     extração + verificação
                                                                  |
                                                             avaliação
```

Esse desenho é um grafo de dependências de processamento. É diferente do grafo de conhecimento que contém pessoas, eventos e relações.

Cada etapa calcula uma chave a partir de insumos, versão do componente, parâmetros efetivos, prompt/schema/modelo e versões dos artefatos anteriores. Evitar o hash global atual que inclui configurações não relacionadas. Reutilizar só artefatos completos e conferidos.

| Mudança | Reutilização esperada |
| --- | --- |
| Só a regra de avaliação ou o gabarito | Preservar respostas; gerar nova avaliação versionada. |
| Só prompt/modelo da resposta JSON | Preservar indexação. No modo de evidências fixas, repetir só resposta/verificação; no modo agêntico, novas respostas podem mudar próximas consultas e exigem nova investigação. |
| Só top_k, fusão ou travessia | Preservar índices/grafo compatíveis; repetir recuperação e etapas posteriores. |
| Só embedding | Preservar texto/chunks e grafo independentes; gerar vetores de documentos/consultas e índice vetorial compatível; repetir busca e posteriores. |
| Só prompt/modelo de relações | Preservar texto/chunks e embeddings originais; refazer relações, resolução e grafo; repetir caminhos que usam esses artefatos. |
| Só prompt/modelo de resumo | Preservar chunks, embeddings dos chunks e grafo; refazer resumos e seu canal de busca. |
| Tamanho dos chunks | Preservar a leitura do PDF; refazer derivados dos chunks. |
| Parser/OCR | Preservar original; refazer o texto e todos os derivados afetados. |

A separação pressupõe texto original e enriquecimentos em canais distintos. Se uma variante adicionar relações ao campo lexical ou embutir resumo no texto vetorizado, essa dependência deve ser declarada e invalidar também o índice correspondente. Não reutilizar dados só porque os nomes dos modelos coincidem.

Em repetições experimentais, geração de respostas não usa resultados de gerações anteriores como se fossem novas amostras. Indexação pode ser compartilhada; cache de consultas e aquecimento precisam ser declarados. Um modo “reproduzir a tela com respostas salvas” será identificado como replay.

## 7. Modos de teste

1. **Etapa isolada:** testar parser, pacote de extração de relações, resolução de entidades, embeddings ou verificador.
2. **Extração com evidências fixas:** mesmos trechos para cada prompt/modelo; isola interpretação e preenchimento.
3. **Extração com evidências revisadas:** trechos corretos escolhidos por humano; mede o que o leitor consegue fazer quando a busca já acertou.
4. **Recuperação:** avaliar encontrar evidências sem executar a resposta final.
5. **Ponta a ponta:** indexar/usar artefatos, investigar, extrair e avaliar o formulário.
6. **Matriz paramétrica:** repetir qualquer modo em configurações selecionadas e agregar os resultados, preservando detalhes por caso.

O editor de matriz permite restringir casos/documentos, combinar eixos válidos, fixar orçamento e escolher política de cache. A prévia mostra três quantidades distintas: configurações, runs e etapas novas únicas.

## 8. Métricas de qualidade

| Área | Medição |
| --- | --- |
| Texto/OCR | Erro de caracteres/palavras, ordem, tabelas, páginas sem texto e vínculo com a fonte, contra amostra revisada. |
| Grafo | Precisão/cobertura de entidades, relações e eventos; papéis, atribuição, negação, datas; fusões indevidas, duplicatas e suporte da evidência. |
| Recuperação | Recall@k, ranking da evidência correta e cobertura de todas as evidências necessárias; contribuição exclusiva de grafo/resumo/vetor/palavras. |
| JSON | Acerto por campo, precisão dos preenchidos, cobertura, listas completas, abstenções e conflitos. |
| Evidências | Citação localizada, suporte semântico, processo/peça/pessoa corretos e referência de página. Essas medidas permanecem separadas. |
| Verificador | Falsas aprovações e falsas rejeições contra revisão humana. |

O painel deve mostrar resultados por tipo de campo, não apenas uma média. Tipos determinísticos usam regras explícitas; texto livre precisa de rubrica versionada. Juiz LLM é avaliação auxiliar com modelo/prompt registrados, não verdade automática. Uma amostra humana mede sua concordância.

Comparações diretas exigem mesmo conjunto de casos, gabarito e avaliador. Quando versões diferirem, reavaliar respostas antigas sob uma versão comum ou separar os resultados. Exibir denominadores e casos sem anotação; não inventar cobertura de relações sem gabarito suficiente.

Manter o grafo como hipótese central: comparar sem grafo, grafo atual, grafo robustecido e subgrafo revisado. Separar qualidade da construção da utilidade da navegação. Uma melhora deve aparecer em evidências/respostas e no seu custo; mais nós não é critério suficiente.

## 9. Métricas de tempo e custo

Registrar por etapa e tentativa: duração de parede, tempo de fila, chamadas, tokens de entrada/saída, cache e raciocínio quando reportados, limites, retentativas e uso desconhecido. Tempos inclusivos não são somados duas vezes. Distinguir duração total da bateria de soma do tempo ocupado pelos workers.

**Tempo de cada etapa é um requisito explícito da interface.** A comparação entre versões e o detalhe de cada run devem mostrar fila, leitura do PDF, OCR quando necessário, recortes/pacotes, extração de entidades/eventos/relações, resumos, embeddings, gravação no OpenSearch, gravação no Neo4j, recuperação/chamadas MCP, extração JSON, verificação e avaliação contra o gabarito. Cada linha apresenta duração, estado e diferença para a referência. O [protótipo de tempos](prototipo-plataforma.html#tempos) ilustra essa apresentação com valores fictícios.

Na implementação, usar relógio monotônico para durações e registrar horários de início/fim para correlação dos eventos. Uma etapa pode conter várias tentativas e chamadas; o detalhe deve expor essas durações sem somar novamente tempos já incluídos no pai. Mostrar fila separadamente, registrar espera/retentativas dentro da etapa correspondente e relacionar chamadas MCP ao passo que as originou. Medir a duração total de ponta a ponta diretamente, incluindo execução parcial quando aplicável. Para uma bateria, mostrar distribuição por etapa (mediana e p95 com tamanho da amostra), além do detalhe individual, sob as mesmas condições de cache/concorrência.

Etapas reaproveitadas mostram o tempo histórico de construção do artefato separado do trabalho novo, incluindo eventual carregamento do cache. Uma etapa não executada, ainda em fila ou sem telemetria não pode parecer uma medição de 0 s. Comparações entre construção completa e consulta com índices prontos devem ter cenários separados. Testes precisam verificar reconciliação em execução sequencial e ausência de dupla contagem quando houver paralelismo, retentativas, cancelamento ou cache.

Mostrar separadamente:

- Custo efetivamente incorrido por esta run: novas chamadas/serviços e uso local com tarifa explícita.
- Custo de construção dos artefatos reutilizados: atribuído à etapa que os produziu; uma bateria não o soma novamente em cada run.
- Custo estimado de reproduzir uma variante do zero: projeção identificada, apoiada em registros disponíveis, sem confundir com cobrança realizada.
- Custo amortizado por N consultas: N informado pelo usuário e hipótese declarada.
- Custo de extração e de avaliação separados; avaliação por LLM também consome recursos.
- Custo por campo correto e sustentado: explicitar regra, denominador e casos não avaliados. Quando não houver acertos, mostrar “não calculável”.

Cada preço terá provedor, modelo, moeda e vigência. Ausência de tarifa/uso é desconhecido, não zero. Valores de moedas distintas não são somados sem conversão registrada. Hardware e energia locais podem receber tarifa; a gratuidade da chamada ao Ollama não elimina esses custos.

A prévia de orçamento estima o trabalho, mas não promete uma conta exata. O coordenador controla despacho e reserva de orçamento para chamadas em voo. Ao atingir limite, impede novas chamadas; cancelamentos/timeouts externos podem ainda gerar cobrança. Guardar IDs de requisição e uso indeterminado para reconciliação, sem duplicar custos entre cliente MCP, servidor e provedor.

## 10. Execução confiável

- Estados: rascunho → planejada → na fila → executando → concluída, parcial, falhou, cancelada ou interrompida. Estados por etapa, inclusive aguardando dependência e reutilizada.
- Um coordenador persiste concessões de trabalho, heartbeat e transições; workers executam etapas com concorrência limitada. Começar com uma tarefa de GPU local por vez. Limites de APIs são separados.
- Etapas independentes podem ser compartilhadas por várias runs. Publicar artefatos e versões de índices somente após validar conclusão. Escritas parciais ficam identificadas e não viram cache válido.
- Retomada valida checkpoints e insumos. Se o provedor não permitir idempotência, registrar a incerteza de uma chamada interrompida; não prometer exatamente uma cobrança.
- Remover artefatos exige conferir referências de runs/configurações e uma ação explícita; limpeza não deve apagar evidências de uma comparação salva.
- Benchmark de latência registra aquecimento, concorrência e cache. Comparar medições com condições diferentes exige identificação visível.

## 11. Reuso do projeto atual

Preservar os PDFs, formulários, referências provisórias, benchmark `full`, índices/grafo históricos e relatórios. Importar o histórico como somente leitura, com seus limites e proveniência; não apresentá-lo como medição da nova plataforma.

Refatorações necessárias:

1. Substituir `config.json` global por configuração imutável passada a cada etapa e cliente MCP.
2. Separar resumo e relações, hoje gerados na mesma chamada.
3. Externalizar prompts e schemas com versões e prévia de renderização.
4. Transformar o adaptador exclusivo de Ollama em interfaces por capacidade de modelo.
5. Separar versões de texto, chunks, embeddings, enriquecimentos, índices e grafo.
6. Substituir a enumeração fixa A–F por configuração declarativa, preservando A–F como receitas históricas.
7. Persistir catálogo de runs, jobs, tentativas, artefatos e avaliações; adaptar os eventos existentes sem perder hierarquia.
8. Retirar dependência de um único índice “ativo” por corpus. A ferramenta MCP recebe a versão da run.
9. Ampliar avaliação e revisão humana; manter medição por campo e exportação.

## 12. Implementação por entregas verificáveis

| Entrega | Resultado concreto | Aceite |
| --- | --- | --- |
| 1. Motor versionado | Configuração por run, artefatos e dependências, prompts externos e adaptadores | Duas receitas diferentes coexistem; modificar uma não altera execução ou índice da outra. Histórico importado permanece intacto. |
| 2. Primeiro fluxo pela interface | Biblioteca, editor, uma execução, progresso e resultado por campo | Alterar um prompt, executar uma amostra e comparar duas runs pela tela, com tempo/uso e evidências. Fechar a aba não interrompe o worker. |
| 3. Matrizes e reaproveitamento | Eixos paramétricos, prévia, fila persistente, cancelamento e retomada | Produto cartesiano validado; só derivados afetados são refeitos; uma falha pode ser retomada sem misturar versões. |
| 4. Qualidade e comparação | Gabaritos versionados, modos isolados, painel por campo, ranking e custos | Mesmo caso comparado lado a lado; avaliação separada da geração; dados exportados reconciliam com a tela. |
| 5. Grafo e leitura robustecidos | Parsers/recortes substituíveis, extração de relações aprimorada, revisão e caminhos | Construção e navegação avaliadas separadamente; evidências exclusivas do grafo rastreadas até as respostas. |
| 6. Nova bateria | Comparações controladas com os dois documentos e relatório final | Configurações congeladas, orçamento declarado, amostra reservada, análise de ganhos/regressões, custos e limitações. |

O primeiro marco de uso é a entrega 2. Ela já deve permitir a ação central: duplicar → mudar → rodar → comparar. As entregas seguintes aprofundam o laboratório sem adiar esse fluxo até todas as técnicas estarem prontas.

## 13. Plano de testes da plataforma

- Configuração: validação por provedor, prompts/schema, versões imutáveis, configurações incompatíveis e segredos ausentes.
- Dependências/cache: trocar cada parâmetro e provar quais etapas invalidam; não reutilizar versões incompletas; repetir uma geração de avaliação não pode virar cache silencioso.
- Estado: reinício, lease expirado, erro de worker, cancelamento, timeout e retomada com artefatos parciais.
- Isolamento: runs simultâneas/alternadas nunca consultam grafo ou índice de outra versão; os dois documentos não misturam evidências.
- Métricas: operação faturável contada uma vez; retentativas, uso desconhecido, paralelismo, cache, custo compartilhado e avaliação separados.
- Qualidade: regras de datas, listas, negação, escopo e abstenção; referências reservadas não entram na execução; anotação sobre fonte sobrevive a mudança de chunks.
- Interface: criar/duplicar/configurar, variar parâmetros, prévia de matriz, executar, cancelar, comparar e abrir evidência; teclado, layouts e estados vazios/falha.
- Ponta a ponta: testes pequenos controlados com provedores simulados para contratos; teste real reduzido com serviços/modelos; bateria de qualidade real separada. Simulação não é resultado de qualidade de modelo.
- Exportação: JSON/CSV/HTML e configurações preservam resultados, unidades, versões, denominadores e custos exibidos.

Critério geral: a plataforma deve explicar de onde veio cada número e permitir repetir a mesma configuração. Não basta mostrar gráficos; precisamos conseguir investigar o que mudou e por quê.

## 14. Limites da primeira versão

Uso individual local, com armazenamento local como padrão. Colaboração simultânea, hospedagem pública e controle multiusuário ficam fora desta primeira entrega. O uso de APIs externas depende de provedores/credenciais e limites configurados; não faz parte de um benchmark até efetivamente executado.

Os dois PDFs permitem comparar métodos nestes exemplos. Não demonstram generalização, capacidade para milhões de páginas ou segurança para extração judicial sem revisão. O roteiro de robustecimento detalhado permanece em [WORKBENCH.md](WORKBENCH.md); este plano acrescenta o produto, a execução versionada e a interface que tornam esses experimentos operáveis.
