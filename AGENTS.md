# Instruções para agentes neste repositório

Leia [README-AGENTE.md](README-AGENTE.md) antes de implementar. Ele contém o caminho de instalação, primeiro experimento, testes, mapa do código e critérios de entrega. Não é necessário acessar o chat que originou o projeto.

## Escopo e fonte de verdade

- A plataforma atual é local e individual: React/TypeScript, API Python, SQLite, Ollama, OpenSearch e Neo4j. Não requer AWS ou contas de serviços de IA externos.
- Código + [operação atual](docs/PLATAFORMA-LOCAL.md) + [validação](docs/VALIDACAO-PLATAFORMA.md) descrevem o que existe. [PLATAFORMA.md](docs/PLATAFORMA.md) e [WORKBENCH.md](docs/WORKBENCH.md) também contêm recursos futuros; não os apresente como implementados.
- Execute a tarefa solicitada pelo usuário. O roteiro não autoriza implementar todas as próximas fases, contratar serviços ou publicar a aplicação.

## Contratos que devem ser preservados

- Consulte `git status` antes de editar. Preserve alterações do usuário, relatórios históricos em `reports/full/`, dados locais e runs anteriores.
- Receitas, formulários e insumos de runs são versões imutáveis. Alterações criam versões novas; MCP recebe o índice/grafo explícito da run.
- Mudanças nos algoritmos de artefatos exigem atualização da versão de cache ou parâmetros de versão por etapa. Arquivar o código não invalida o cache automaticamente.
- Toda etapa conserva duração, uso, falhas e proveniência. Não some spans de MCP com os filhos já incluídos. Fila, trabalho novo e construção reaproveitada são separados. Custo de hardware sem tarifa e tempo não observado são desconhecidos, não zero.
- Separe teste de software de avaliação de modelos. Gabaritos não entram no prompt de extração. Registre abstenções, regressões e falhas; mais relações no grafo não comprovam melhor qualidade.
- Mantenha os serviços no loopback: o Compose local desativa autenticação. Não remova volumes, índices ou históricos para “corrigir” um teste. Novos experimentos usam novas identidades.
- Preserve a identidade visual existente e a tabela de tempo de cada etapa no detalhe e na comparação. Não substitua medições por dados do protótipo.

## Entrega

Use os testes pertinentes descritos no README do agente, informe aprovações e testes ignorados separadamente e atualize a documentação afetada. Não use `poc benchmark --name full` para uma execução nova. As evidências geradas pelos testes podem alterar arquivos de relatório: revise o diff antes de incluí-las em um commit.
