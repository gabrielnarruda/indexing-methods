# O que esta PoC permite concluir

Os resultados completos e suas medições estão no [relatório](../reports/full/relatorio.html). As afirmações abaixo se referem à implementação executada, aos dois PDFs escolhidos e ao modelo local Qwen3:4b.

## Pontos fortes da proposta inicial

A combinação de texto original, busca lexical, vetores e fontes explícitas é uma base útil para investigar documentos extensos. Um formulário com perguntas e tipos permite medir erros por campo, preservar pendências e repetir o mesmo experimento. O grafo acrescenta uma forma inspecionável de percorrer relações; o explorador HTML permite conferir a citação de cada afirmação.

MCP torna a interface de recuperação utilizável por diferentes clientes. Nesta PoC, ele expõe busca, leitura, listagem e travessia. A qualidade das respostas continua dependendo de quais passagens são recuperadas, de como o escopo é comunicado ao modelo e de como os valores são verificados.

## Fragilidades demonstradas

**Uma citação verdadeira pode sustentar a resposta à pergunta errada.** Na extração de `resultado`, a variante F usou um trecho da ADI 2.076/AC, citada dentro do acórdão, para responder sobre a ADPF 54. A citação existia no PDF e o verificador aprovou a resposta. Isso exige representar o processo principal e distinguir precedentes citados, votos individuais e decisão colegiada.

**Papéis processuais podem ser confundidos.** A CNBB aparece requerendo ingresso como amicus curiae. O extrator a tratou como requerente da ADPF, cuja parte requerente indicada na referência é a CNTS. O segundo modelo repetiu a confusão. Extrair entidades sem contextualizar seus papéis não resolve esse problema.

**O mesmo modelo tende a reproduzir seus próprios erros.** A validação semântica encontrou algumas propostas sem suporte, mas também aprovou erros de atribuição. Ela tem custo mensurável e precisa ser avaliada por taxa de rejeição indevida e aceitação indevida. Um escore de confiança do próprio modelo não pode ser tomado como garantia de preenchimento correto.

**O grafo começa limitado pelo enriquecimento.** Foram retidas 187 das 352 relações propostas. As outras 165 falharam na verificação de fonte ou nos campos exigidos. A presença de uma citação localizada também não comprova que sujeito, relação e objeto foram interpretados corretamente. A resolução de nomes desta versão é simples e não trata correferência contextual.

**Poucas passagens não demonstram a completude de uma lista.** Encontrar um ministro divergente, uma data ou um evento não comprova que todos foram encontrados. Um campo de lista precisa de uma política de cobertura: quais peças ou seções foram examinadas, quais ainda faltam e quando pode ser declarado completo.

**Mais rodadas podem conservar um erro.** O controlador encerra um campo quando recebe uma proposta com citação válida e aprovação semântica. Uma resposta errada aprovada na primeira rodada não chega às demais. O aumento do número máximo de rodadas, isoladamente, não corrige a condição de parada.

## Próxima versão, em ordem de prioridade

1. **Revisar a referência de avaliação.** Conferir campos críticos e suas evidências com revisão humana, registrar aliases e separar um conjunto independente antes de alterar prompts. Acrescentar casos de precedentes citados, papéis distintos, conflitos e listas extensas.
2. **Adicionar estrutura e escopo.** Identificar capa, relatório, voto, precedente citado e dispositivo. Incluir identidade do documento, alvo da pergunta, autor da afirmação e natureza do trecho na recuperação e na validação. Para literatura, adaptar a classificação a narrador, fala de personagem e capítulo.
3. **Reavaliar recuperação e seleção de contexto.** Comparar o baseline lexical sobre texto sem enriquecimento, a busca híbrida e uma etapa de reranking. Manter os mesmos orçamentos de evidências e medir a recuperação das passagens necessárias antes de atribuir o erro ao extrator.
4. **Separar localização de suporte.** Conferir tipos e citações de forma determinística; avaliar um verificador com maior capacidade ou distinto do extrator. Medir tanto respostas erradas aprovadas quanto respostas corretas recusadas. Manter revisão para os campos de maior consequência enquanto o erro observado for alto.
5. **Implementar cobertura para listas.** Planejar uma varredura das seções pertinentes, deduplicar itens com suas fontes e produzir estado `partial` quando houver cobertura incompleta. Preservar diferenças entre data do evento, data do registro e data da decisão.
6. **Ampliar o grafo somente após medir sua contribuição.** Preservar um núcleo genérico de entidade, afirmação, evento e evidência; especializar papéis por domínio. Avaliar resolução de entidades, relações erradas e cobertura. Comparar o ganho da travessia com o uso dos mesmos fatos como metadados.
7. **Expandir o corpus e o perfil de custo.** Incluir autos completos, digitalizações, tabelas e outros gêneros. Medir OCR, falhas de leitura e reindexação após mudanças. Separar custos mínimos de indexação por variante e comparar investigação sob orçamento total equivalente.

## Critério para decidir sobre o grafo

O grafo deve ser mantido por ganho demonstrado em perguntas que dependem de relações ou evidências distantes, considerando precisão, cobertura, tempo de indexação, custo de investigação e manutenção. Esta amostra de dois documentos fornece um diagnóstico inicial de engenharia; não estabelece um padrão universal nem demonstra generalização para qualquer PDF.

As inspirações de pesquisa incluem [RAPTOR](https://arxiv.org/abs/2401.18059), [HippoRAG](https://arxiv.org/abs/2405.14831) e a comparação [RAG vs. GraphRAG](https://arxiv.org/abs/2502.11371). A PoC usa versões reduzidas de recuperação por resumos e travessia, descritas em [IMPLEMENTACAO.md](IMPLEMENTACAO.md).
