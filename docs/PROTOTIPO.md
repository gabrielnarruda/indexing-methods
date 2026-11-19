# Protótipo de interface da plataforma

Superfície local em `prototipo-plataforma.html`, independente de backend e de bibliotecas externas. A tarefa principal é duplicar uma configuração, alterar etapas, montar uma matriz, simular a execução e comparar resultados. Esta entrega é uma demonstração de UI/UX, não a implementação do motor de experimentos.

## Direção visual

Preservar a identidade verde do projeto em uma interface de trabalho: verde principal `#245e50`, tinta `#233b38`, fundo `#f4f7f6`, superfície branca, linha `#dce5e1` e âmbar `#8a5e19` para a identificação da demonstração. Tipografia de sistema, títulos contidos e texto funcional de pelo menos 14 px; corpo de 16 px. Nenhuma fonte ou imagem externa.

A navegação lateral identifica biblioteca, experimentos, prompts e grafo. Dentro de um experimento, as abas representam configuração, matriz, execuções e comparação. O editor usa navegação por etapa, área de trabalho e resumo do impacto da mudança. Em telas estreitas, a navegação e o resumo passam para o fluxo vertical.

Diagramas, tabelas e barras devem explicar dependências e diferenças, sem criar ruído decorativo. Não há publicidade, cadastro ou indicadores de serviços reais conectados. A identificação de protótipo permanece visível.

## Escopo funcional

- Editar parâmetros e prompts de demonstração; salvar versões e duplicar uma configuração no navegador.
- Selecionar eixos da matriz, documentos e repetições, com contagens calculadas e combinação inválida impedida.
- Simular uma fila por avanço manual, pausar/cancelar e abrir um detalhe de execução ilustrativo.
- Comparar configurações demonstrativas, alternar documentos e inspecionar campos/evidências fictícias.
- Ver **tempos por etapa** na comparação e no detalhe de cada run: fila, leitura do PDF, OCR, recortes, entidades/eventos/relações, resumos, embeddings, gravação no OpenSearch, gravação no Neo4j, busca/MCP, extração JSON, verificação e avaliação. [Abrir diretamente os tempos](prototipo-plataforma.html#tempos).
- Alternar entre construção dos índices mais extração e extração com índices prontos. Tempos históricos de artefatos reaproveitados ficam separados da duração nova. Etapas não executadas e runs sem duração final são identificadas. Os totais do exemplo sequencial incluem fila e avaliação; não representam a soma apropriada para uma execução paralela real.
- Explorar uma estrutura de grafo fictícia com seleção de nós e evidências.
- Exportar configuração e matriz como JSON identificado como protótipo.

Os nomes e quantidades de páginas dos dois documentos são do projeto; valores de qualidade, custo, duração, respostas e exemplos do grafo são fictícios e identificados. Não são medições novas nem previsões de ganho. O botão de simulação não chama modelos, não indexa documentos, não cobra APIs e não altera os bancos da PoC.

Alterações podem ser mantidas no localStorage deste navegador/origem, quando disponível. Não há sincronização com o repositório ou o banco real. O usuário pode restaurar a demonstração pelo menu de ajuda.

## Conferência

Verificar navegação por etapas, edição/salvamento, matriz, fila simulada, comparação e detalhe, grafo, exportação, teclado, larguras desktop/mobile, ausência de erros JavaScript e ausência de requisições externas. O HTML deve abrir por arquivo local e por servidor de preview. As evidências da revisão ficam em `reports/validation/prototype-*`.

Conferência realizada em 18/11/2026: **90 verificações aprovadas** no Edge via Playwright, com abertura por arquivo local. Inclui reconciliação dos tempos de etapas com os totais, exclusão de construção histórica reaproveitada, duração desconhecida de runs pendentes e atualização ao trocar versão/documento/cenário. Larguras verificadas: 390, 768, 1280 e 1440 px, sem transbordamento horizontal da página; tabelas largas usam rolagem própria. Nenhum erro JavaScript e nenhuma requisição de rede externa durante a conferência. O preview HTTP local também respondeu com status 200 na revisão inicial. As capturas de desktop e celular foram inspecionadas visualmente.

O roteiro reproduzível está em [`tools/verify-prototype.cjs`](../tools/verify-prototype.cjs); requer Node.js, Playwright e Edge. Execute `node tools/verify-prototype.cjs` com Playwright disponível no ambiente. Os resultados estão em [`prototype-checks.json`](../reports/validation/prototype-checks.json). Essa conferência valida a demonstração da interface; não mede a qualidade de extração, custo ou desempenho de modelos.
