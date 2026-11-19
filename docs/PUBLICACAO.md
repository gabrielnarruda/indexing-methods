# Publicação do repositório

Em 19/11/2026, o conteúdo foi preparado para publicação com revisão dos arquivos e de todo o histórico a publicar, incluindo os arquivos ZIP/GZIP. A revisão por padrões não encontrou credenciais, chaves privadas ou tokens. Essa verificação não constitui garantia de ausência de todo dado sensível.

O e-mail pessoal e o nome da máquina foram removidos da autoria dos cinco commits originais. A autoria pública usa o usuário do GitHub e um endereço `noreply`. O hostname presente em `reports/full/measurements.json`, `reports/validation/junit.xml` e `reports/validation/workbench-junit.xml` foi substituído por `redacted-local-host` em todas as versões desses arquivos.

Não foram alterados código de execução, respostas, gabaritos, testes registrados, durações, custos, métricas ou arquivos compactados históricos. Os relatórios continuam disponíveis em [reports/full](../reports/full/) e [reports/validation](../reports/validation/). Os nomes e trechos provenientes das fontes públicas do corpus foram preservados.

Os identificadores dos commits mudaram por causa da anonimização. Um backup do histórico original foi preservado fora do conteúdo publicado. A publicação usa um repositório independente do original privado para que os objetos Git antigos não sejam expostos no repositório público. Referências a commits anteriores eventualmente presentes em artefatos históricos são registros de proveniência; não devem ser tratadas como revisões acessíveis no histórico público.

Quem possui um clone anterior à publicação deve guardar suas alterações locais e fazer um novo clone. Não faça merge ou push do histórico antigo para o repositório público.

PDFs baixados, bancos locais, execuções completas, caches e credenciais não fazem parte do Git publicado. O clone inclui os relatórios exportados; siga [README-AGENTE.md](../README-AGENTE.md) para preparar o ambiente e gerar novas execuções.

Antes de publicar relatórios futuros, revise seus metadados: ferramentas como o pytest podem voltar a registrar o hostname ao gerar JUnit. Preserve as medidas originais e remova somente identificadores pessoais. Configure a identidade Git do desenvolvedor com seu próprio endereço `noreply` do GitHub quando desejar manter o e-mail pessoal privado.
