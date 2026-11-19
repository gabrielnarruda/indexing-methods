# Manutenção do relatório explicado

O relatório principal é [reports/full/relatorio.html](../reports/full/relatorio.html). Ele é um único HTML offline com leitura simples, diagramas, tabelas de resultados, prompts exatos e anexo com as 720 avaliações. Os arquivos de evidências e exportações permanecem links relativos no mesmo pacote.

## Direção de leitura

Preservar a identidade verde, fundo claro e tipografia de sistema do projeto. A leitura principal usa frases curtas e a analogia da biblioteca, sem tratar hipóteses como resultados. Os termos técnicos são explicados ao aparecer e têm glossário. Navegação lateral em telas grandes; navegação em fluxo nas pequenas. Corpo com medida de leitura limitada; tabelas largas rolam dentro de seu próprio contêiner.

Os diagramas de recortes e grafo são explicativos e identificados como tal. As barras de resultados são calculadas das medições; escala comum de 0 a 100%. Resultados por documento podem ser alternados por botão. Sem JavaScript, ambas as tabelas permanecem legíveis. Impressão inclui os dois documentos e omite o anexo extenso de auditoria.

## Fontes e geração

- `poc/report_explained.html`: texto, estrutura e estilo da leitura explicada.
- `poc/report_explained.py`: injeta medições e recupera prompts/schema do ZIP congelado; inclui o relatório técnico dentro do anexo.
- `poc/report.py`: continua gerando as medições e o relatório técnico e aplica a leitura explicada ao experimento identificado pelo fingerprint original.
- `docs/WORKBENCH.md`: roteiro técnico da próxima fase, alinhado aos capítulos 11 e 12.

A interpretação é específica do experimento de novembro de 2026. O fingerprint impede que seu texto seja apresentado como conclusão de outra bateria. Novos experimentos continuam recebendo o relatório técnico e exigem nova interpretação.

Para atualizar apenas a apresentação, sem serviços, inferência ou alteração das medições:

```powershell
.venv/Scripts/python.exe -m poc.report_explained
```

Para regenerar os artefatos a partir das execuções locais existentes, o comando original permanece disponível:

```powershell
.venv/Scripts/python.exe -m poc report --name full
```

Preservar os dados e o ZIP congelado. Conferir o HTML no navegador, navegação por teclado, resultados por documento, filtros da auditoria, projeção de custos, impressão e largura mobile. Os detalhes da conferência desta revisão ficam em `reports/validation/report-revision.json`; isso é verificação da apresentação, não um novo benchmark de qualidade.
