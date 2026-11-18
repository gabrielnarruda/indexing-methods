"""Generate a portable report directly from run artifacts, with no invented measurements."""
from collections import defaultdict
import csv
import gzip
import html
import json
from pathlib import Path
import statistics
import xml.etree.ElementTree as ET

from .common import ROOT, read_json, write_json
from tools.render_graph import render_graph
from tools.export_inputs import export_inputs


def escape(value):
    return html.escape(str(value))


def number(value,digits=2):
    return 'não configurado' if value is None else f'{value:.{digits}f}'


def events_in(directory):
    events=[]
    for path in directory.glob('events-*.jsonl'):
        events.extend(json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line)
    return events


def field_accounting(events):
    lookup={event['span_id']:event for event in events}
    result={}
    for event in events:
        parent=event
        visited=set()
        while not parent.get('field_path') and parent.get('parent_span_id') in lookup:
            if parent['span_id'] in visited:
                break
            visited.add(parent['span_id'])
            parent=lookup[parent['parent_span_id']]
        field=parent.get('field_path')
        if not field:
            continue
        row=result.setdefault(field,{'duration_seconds':0,'model_calls':0,'input_tokens':0,
                                    'output_tokens':0,'api_cost':0,'usage_unknown_calls':0,
                                    'mcp_tools':{},'stage_seconds':{}})
        stage=event['stage']
        row['stage_seconds'][stage]=row['stage_seconds'].get(stage,0)+event['duration_ms']/1000
        if stage=='field':
            row['duration_seconds']=event['duration_ms']/1000
        if stage=='mcp':
            tool=event['operation']
            row['mcp_tools'][tool]=row['mcp_tools'].get(tool,0)+1
        if event.get('billable'):
            row['model_calls']+=1
            row['input_tokens']+=event.get('input_tokens') or 0
            row['output_tokens']+=event.get('output_tokens') or 0
            row['api_cost']+=event.get('api_cost',0)
            row['usage_unknown_calls']+=event.get('input_tokens') is None
    return result


def stage_table_rows(corpus,label,metrics,events):
    rows=[]
    for stage,values in metrics['stages'].items():
        usage=[event for event in events if event['stage']==stage and event.get('billable')]
        rows.append([corpus,label,stage,values['calls'],round(values['inclusive_ms']/1000,2),
                     values['errors'],sum(e.get('input_tokens') or 0 for e in usage),
                     sum(e.get('output_tokens') or 0 for e in usage),
                     sum(e.get('api_cost',0) for e in usage)])
    return rows


def percent(items):
    return '—' if not items else f'{sum(items)/len(items)*100:.1f}%'


def render_report(name='full'):
    benchmark=read_json(ROOT/'runs'/f'benchmark-{name}'/'benchmark.json')
    destination=ROOT/'reports'/name
    destination.mkdir(parents=True,exist_ok=True)
    rows=[]
    field_rows=[]
    details=[]
    indexes=[]
    stage_rows=[]
    archives=[]
    reused=[]
    examples={}
    output_links=[]
    for path in sorted((ROOT/'runs').glob('indexing-*/run.json')):
        metadata=read_json(path)
        if metadata.get('reused') and (path.parent/'metrics.json').exists():
            reused.append({**metadata,'metrics':read_json(path.parent/'metrics.json')})
    for corpus in ['adpf54','dom-casmurro']:
        index=read_json(ROOT/'data/indexes'/f'{corpus}.json')
        metrics=read_json(ROOT/'runs'/index['run_id']/'metrics.json')
        indexes.append({'corpus':corpus,**index,'metrics':metrics})
        directory=ROOT/'runs'/index['run_id']
        events=events_in(directory)
        stage_rows.extend(stage_table_rows(corpus,'indexação',metrics,events))
        archives.append({'kind':'indexing','manifest':index,'run':read_json(directory/'run.json'),
                         'metrics':metrics,'events':events})
    for job in benchmark['jobs']:
        if job.get('status')!='complete':
            continue
        directory=ROOT/'runs'/job['run_id']
        evaluation=read_json(directory/'evaluation.json')
        metrics=read_json(directory/'metrics.json')
        fields=read_json(directory/'fields.json')
        events=events_in(directory)
        accounting=field_accounting(events)
        for metric in ('model_calls','input_tokens','output_tokens','api_cost','usage_unknown_calls'):
            if sum(item[metric] for item in accounting.values())!=metrics[metric]:
                raise ValueError(f'Field accounting does not reconcile for {job["run_id"]}: {metric}')
        archives.append({'kind':'extraction','run':read_json(directory/'run.json'),
                         'experiment':read_json(directory/'experiment.json'),'fields':fields,
                         'result':read_json(directory/'result.json'),'evaluation':evaluation,
                         'metrics':metrics,'events':events})
        output_name=f"{job['corpus']}-{job['variant']}-r{job['repetition']+1}"
        write_json(destination/'outputs'/f'{output_name}.json',read_json(directory/'result.json'))
        write_json(destination/'outputs'/f'{output_name}-evidence.json',{'run_id':job['run_id'],'fields':fields})
        output_links.append({'name':output_name,'run_id':job['run_id'],
                             'result':f'outputs/{output_name}.json','evidence':f'outputs/{output_name}-evidence.json'})
        field_times={event['field_path']:event['duration_ms'] for event in events if event['stage']=='field'}
        stage_rows.extend(stage_table_rows(job['corpus'],f"{job['variant']} / {job['repetition']+1}",metrics,events))
        row={'corpus':job['corpus'],'variant':job['variant'],'repetition':job['repetition'],
             'run_id':job['run_id'],'accuracy':evaluation['accuracy'],'fields':evaluation['field_count'],
             **{k:metrics[k] for k in ['wall_seconds','input_tokens','output_tokens','model_calls','mcp_calls','agent_rounds','api_cost','machine_cost_estimate','errors','cache_hits','usage_unknown_calls']}}
        correct_count=sum(field['correct'] for field in evaluation['fields'])
        row.update(correct_fields=correct_count,
                   seconds_per_correct=None if not correct_count else metrics['wall_seconds']/correct_count,
                   input_tokens_per_correct=None if not correct_count else metrics['input_tokens']/correct_count,
                   api_cost_per_correct=None if not correct_count else metrics['api_cost']/correct_count)
        rows.append(row)
        scores={score['field_id']:score for score in evaluation['fields']}
        for field in fields:
            field_rows.append({'run_id':job['run_id'],'corpus':job['corpus'],'variant':job['variant'],
                               'repetition':job['repetition'],**scores[field['id']],
                               'accounting':accounting.get(field['path'],{})})
            evidence='<ul>'+''.join(f"<li>Página {citation['page']} · {escape(citation['chunk_id'])}<blockquote>{escape(citation['quote'])}</blockquote></li>" for citation in field['evidence'])+'</ul>'
            duration=field_times.get(field['path'],0)/1000
            trace=f'<p>Tempo do campo {duration:.2f} s · rodadas {len(field["rounds"])}</p><ol>'+''.join(f"<li><strong>Rodada {step['round']}</strong> — {escape(step['query'])}<br>{escape(step['answer'].get('reason',''))}<br>Trechos {escape(', '.join(step['retrieved_ids']))}<br>Proposta original: {escape(json.dumps(step.get('raw_answer',{}).get('value'),ensure_ascii=False))}<br>Validação: {escape(json.dumps(step.get('support_check'),ensure_ascii=False))}</li>" for step in field['rounds'])+'</ol>'
            usage=accounting.get(field['path'],{})
            trace+=f'<p>Chamadas de modelo {usage.get("model_calls",0)} · tokens de entrada {usage.get("input_tokens",0)} · saída {usage.get("output_tokens",0)} · API {usage.get("api_cost",0):.2f} BRL</p>'
            value=escape(json.dumps(field['value'],ensure_ascii=False))
            details.append(f"<details data-corpus='{escape(job['corpus'])}' data-variant='{job['variant']}'><summary>{escape(job['corpus'])} · {job['variant']} · repetição {job['repetition']+1} · {escape(field['id'])} · {escape(field['status'])}</summary><p>{escape(field['question'])}</p><pre>{value}</pre><p>Acerto automático {scores[field['id']]['correct']} · referência {escape(json.dumps(scores[field['id']]['expected'],ensure_ascii=False))}</p>{evidence}{trace}</details>")
            if (job['corpus']=='adpf54' and job['variant']=='F' and field['id'] in ('resultado','requerente')
                    and not scores[field['id']]['correct'] and field['status']=='filled'):
                examples.setdefault(field['id'],{'run_id':job['run_id'],'field':field,'score':scores[field['id']]})
    with (destination/'executions.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        if rows:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    validation_path=ROOT/'reports/validation/junit.xml'
    validation=ET.parse(validation_path).getroot().find('testsuite').attrib if validation_path.exists() else {}
    environment_path=ROOT/'reports/validation/environment.json'
    environment=read_json(environment_path) if environment_path.exists() else {}
    release_path=ROOT/'reports/validation/release.json'
    release=read_json(release_path) if release_path.exists() else None
    write_json(destination/'measurements.json',{'benchmark':benchmark,'indexes':indexes,'reused_indexes':reused,
               'executions':rows,'fields':field_rows,'stages':stage_rows,'tests':validation,'environment':environment,
               'release_validation':release})
    with gzip.open(destination/'audit.json.gz','wt',encoding='utf-8') as stream:
        json.dump({'benchmark':benchmark,'runs':archives,'reused_indexes':reused},stream,ensure_ascii=False)
    write_json(destination/'outputs/index.json',output_links)
    with (destination/'stages.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.writer(stream)
        writer.writerow(['corpus','execution','stage','calls','inclusive_seconds','errors','input_tokens','output_tokens','api_cost_brl'])
        writer.writerows(stage_rows)
    groups=defaultdict(list)
    for row in rows:
        groups[(row['corpus'],row['variant'])].append(row)
    table=[]
    markdown=[]
    quality=[]
    quality_markdown=[]
    for (corpus,variant),items in sorted(groups.items()):
        accuracy=statistics.mean(r['accuracy'] for r in items)*100
        seconds=statistics.median(r['wall_seconds'] for r in items)
        minimum=min(r['wall_seconds'] for r in items)
        maximum=max(r['wall_seconds'] for r in items)
        calls=statistics.mean(r['mcp_calls'] for r in items)
        rounds=statistics.mean(r['agent_rounds'] for r in items)
        values=[corpus,variant,len(items),f'{accuracy:.1f}%',f'{seconds:.1f}',f'{minimum:.1f}–{maximum:.1f}',f'{calls:.1f}',f'{rounds:.1f}']
        table.append('<tr>'+''.join(f'<td>{escape(value)}</td>' for value in values)+'</tr>')
        markdown.append('| '+' | '.join(map(str,values))+' |')
        fields=[field for field in field_rows if field['corpus']==corpus and field['variant']==variant]
        filled=[field for field in fields if field['status']=='filled']
        negatives=[field for field in fields if field['is_negative']]
        lists=[field for field in fields if field['list_recall'] is not None]
        quality_values=[corpus,variant,len(filled),percent([field['correct'] for field in filled]),
                        percent([field['reference_page_hit'] for field in fields if field['reference_page_hit'] is not None]),
                        percent([field['list_precision'] for field in lists]),percent([field['list_recall'] for field in lists]),
                        percent([field['correct'] for field in negatives]),
                        sum(field['status']=='limit_reached' for field in fields),sum(field['status']=='error' for field in fields)]
        quality.append('<tr>'+''.join(f'<td>{escape(value)}</td>' for value in quality_values)+'</tr>')
        quality_markdown.append('| '+' | '.join(map(str,quality_values))+' |')
    index_table=[]
    for index in indexes:
        m=index['metrics']
        values=[index['corpus'],index['pages'],index['chunks'],index['sections'],index['facts'],
                index['rejected_facts'],number(m['wall_seconds']),m['input_tokens'],m['output_tokens']]
        index_table.append('<tr>'+''.join(f'<td>{escape(value)}</td>' for value in values)+'</tr>')
    completed=len(rows)
    total=len(benchmark['jobs'])
    title='Relatório de experimentos em documentos extensos'
    method='Corpus integral de 433 páginas da ADPF 54 e 105 páginas de Dom Casmurro. Trechos por página com orçamento de caracteres e sobreposição. Grupos contíguos geram resumos e relações por Qwen3 local. EmbeddingGemma produz vetores. OpenSearch recupera por BM25 e similaridade, com fusão RRF. Neo4j fornece passagens por entidades compartilhadas. Um cliente MCP real chama busca e leitura. O modelo extrai o valor e uma segunda chamada verifica o suporte. Citações são validadas contra o texto original.'
    limits='As referências foram preparadas pelo agente e têm status provisório. O acerto usa aliases, tipos e comparação de listas; correspondência textual pode aceitar formulações semanticamente incorretas. Dois campos judiciais foram usados no teste preliminar, incluindo um marcado como held_out, portanto esta avaliação é exploratória. A conferência literal de citações e a verificação por modelo são medidas distintas de uma revisão humana. Os grupos de resumo usam orçamento de caracteres e representam dois níveis de recuperação. O corpus judicial cobre as peças reproduzidas no acórdão. Dois documentos limitam conclusões sobre generalização. Repetições com temperatura zero medem sobretudo estabilidade e tempo. O modelo de validação é o mesmo modelo da extração, com erros potencialmente correlacionados. OCR automático, correferência contextual e varredura exaustiva para listas ainda não estão implementados.'
    discussion=[]
    total_proposed=sum(index['facts']+index['rejected_facts'] for index in indexes)
    total_rejected=sum(index['rejected_facts'] for index in indexes)
    enrich_seconds=sum(index['metrics']['stages']['enrichment']['inclusive_ms']/1000 for index in indexes)
    total_index_seconds=sum(index['metrics']['wall_seconds'] for index in indexes)
    discussion.append(f"O enriquecimento consumiu {enrich_seconds:.1f} s, equivalente a {enrich_seconds/total_index_seconds*100:.1f}% do tempo total de indexação. Das {total_proposed} propostas de relações, {total_rejected} foram descartadas por falha na localização da citação ou nos campos exigidos. O grafo final é esparso e sua cobertura precisa ser avaliada antes de atribuir erros apenas à travessia.")
    discussion.append('Todas as variantes compartilham a preparação completa do corpus. O tempo de indexação é medido uma vez por documento; este experimento não mede uma indexação mínima separada para cada variante. Resumo e relações são produzidos na mesma chamada, portanto seus custos não podem ser separados retrospectivamente.')
    discussion.append('A precisão semântica das relações do grafo não foi medida contra um gabarito de relações. A verificação automática da indexação cobre estrutura e localização da fonte; o benchmark de formulários mede um efeito indireto na recuperação e na extração.')
    for corpus in ['adpf54','dom-casmurro']:
        scores={variant:statistics.mean(r['accuracy'] for r in items) for (c,variant),items in groups.items() if c==corpus}
        if scores:
            best=max(scores,key=scores.get)
            discussion.append(f"No corpus {corpus}, a maior exatidão automática observada foi {scores[best]*100:.1f}% na variante {best}. Empates devem ser lidos junto da tabela de tempos e chamadas.")
        if 'B' in scores and 'D' in scores:
            discussion.append(f"A diferença de D para B em {corpus} foi {(scores['D']-scores['B'])*100:+.1f} pontos percentuais nesta avaliação.")
        if 'E' in scores and 'F' in scores:
            discussion.append(f"A diferença de F para E em {corpus} foi {(scores['F']-scores['E'])*100:+.1f} pontos percentuais; a tabela registra o custo em rodadas adicionais.")
    discussion.append('A variante F pode consumir até três vezes o número de rodadas de E. Esse contraste mede investigação com orçamento maior, não isola o efeito do agente sob custo total idêntico. A variante A também pesquisa metadados extraídos. O grafo utiliza resolução de nomes simples e uma travessia por entidades compartilhadas; resultados desta implementação não equivalem a uma avaliação de todas as técnicas GraphRAG.')
    discussion.append('O próximo experimento deve revisar as referências e separar uma amostra independente, testar perguntas que exijam evidências distantes, analisar os candidatos recusados pelo verificador e comparar modelos de validação. Segmentação por peças/capítulos e cobertura de listas devem ser avaliadas antes de ampliar a ontologia do grafo.')
    status='Completo' if completed==total else 'Parcial'
    index_seconds=sum(index['metrics']['wall_seconds'] for index in indexes)
    extract_seconds=sum(row['wall_seconds'] for row in rows)
    reuse_text='; '.join(f"{item.get('corpus_id')}: {item['metrics']['wall_seconds']:.3f} s, {item['metrics']['model_calls']} chamadas de modelo" for item in reused)
    test_text=f"{validation.get('tests','não informado')} testes; {validation.get('failures','?')} falhas; {validation.get('errors','?')} erros; {validation.get('skipped','?')} ignorados. Duração da suíte {validation.get('time','?')} s."
    machine_costs=[row['machine_cost_estimate'] for row in rows]
    machine_text='não configurado' if any(value is None for value in machine_costs) else number(sum(machine_costs))+' BRL'
    unknown_usage=sum(row['usage_unknown_calls'] for row in rows)
    example_html=[]
    example_markdown=[]
    for key,example in examples.items():
        field=example['field']
        actual=json.dumps(field['value'],ensure_ascii=False)
        expected=json.dumps(example['score']['expected'],ensure_ascii=False)
        explanation=('O modelo confundiu o julgamento de um precedente citado com o resultado da ação principal.'
                     if key=='resultado' else 'O modelo confundiu um pedido de intervenção como amicus curiae com a identificação da parte requerente.')
        quote=field['evidence'][0] if field['evidence'] else {'page':'?','quote':''}
        description=f"Campo {key}, variante F, execução {example['run_id']}: resposta {actual}; referência {expected}. {explanation} A citação foi localizada e o verificador semântico aprovou a proposta."
        example_html.append('<p>'+escape(description)+'</p><blockquote>'+escape(quote['quote'])+'</blockquote><p>Página '+str(quote['page'])+'.</p>')
        example_markdown.append(description+f" Fonte citada: página {quote['page']}.")
    if examples:
        discussion.append('Os exemplos de atribuição incorreta mostram que esta configuração ainda não sustenta preenchimento judicial sem conferência. O controle de escopo deve distinguir o processo principal, processos citados, partes, intervenientes e posições individuais antes de aceitar uma resposta como resolvida.')
    document=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;color:#21343e;background:#f6f7f4;margin:0}}main{{max-width:1200px;margin:auto;padding:40px 24px}}h1{{line-height:1.15;font-size:36px}}h2{{margin-top:36px}}table{{border-collapse:collapse;width:100%;background:white;font-size:14px}}th,td{{padding:10px;text-align:left;border-bottom:1px solid #d8e0df}}.scroll{{overflow:auto}}details{{background:white;padding:14px;margin:8px 0;border:1px solid #d8e0df;border-radius:8px}}summary{{cursor:pointer;font-weight:600}}blockquote{{border-left:3px solid #559789;padding-left:16px}}pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#edf3f1;padding:12px}}a{{color:#215d89}}select{{font:inherit;padding:7px}}.status{{color:#326c5d}}li{{margin:8px 0}}@media print{{details{{break-inside:avoid}}select{{display:none}}}}</style><main>
<p><a href="../../docs/arquitetura.html">Arquitetura e testes</a> · <a href="grafo.html">Explorar afirmações do grafo</a> · <a href="https://github.com/gabrielnarruda/indexing-methods">Repositório privado</a></p>
<h1>{title}</h1><p class="status">{status} · {completed}/{total} execuções · {len(field_rows)} avaliações de campos</p>
<h2>Método</h2><p>{method}</p><p>A · BM25. B · híbrida. C · híbrida e resumos. D · híbrida e grafo. E · híbrida, resumos e grafo. F · E com até três rodadas. O orçamento de trechos por rodada é fixo. As referências ficam fora dos prompts e índices.</p>
<p>Ambiente: {escape(environment.get('cpu','não registrado'))}; GPU {escape(environment.get('gpu','não registrada'))}; {escape(environment.get('python',''))}. Modelos Qwen3:4b e EmbeddingGemma:300m. Ordem aleatória fixa, temperatura zero, modelos aquecidos, cache de embedding habilitado e cache de geração desabilitado. Hashes e digests estão nas medições.</p>
<h2>Indexação</h2><div class="scroll"><table><thead><tr><th>Corpus</th><th>Páginas</th><th>Trechos</th><th>Resumos</th><th>Relações</th><th>Descartadas</th><th>Segundos</th><th>Tokens entrada</th><th>Tokens saída</th></tr></thead><tbody>{''.join(index_table)}</tbody></table></div>
<h2>Resultados da extração</h2><p>Exatidão automática média entre repetições e tempo mediano em segundos. O intervalo mostra mínimo e máximo. As chamadas e rodadas são médias por formulário completo.</p><div class="scroll"><table><thead><tr><th>Corpus</th><th>Variante</th><th>Repetições</th><th>Exatidão</th><th>Tempo mediano</th><th>Intervalo</th><th>Chamadas MCP</th><th>Rodadas</th></tr></thead><tbody>{''.join(table)}</tbody></table></div>
<h2>Qualidade e campos pendentes</h2><p>Contagens acumuladas entre repetições. Precisão dos preenchidos usa a referência automática. Página encontrada significa recuperar ao menos uma página anotada. A abstenção estrita exige status not_found em um campo de referência nula; limit_reached permanece pendente. Precisão e cobertura de listas são médias por caso.</p><div class="scroll"><table><thead><tr><th>Corpus</th><th>Variante</th><th>Preenchidos</th><th>Precisão</th><th>Página encontrada</th><th>Precisão listas</th><th>Cobertura listas</th><th>Abstenção estrita</th><th>Limites</th><th>Erros de campo</th></tr></thead><tbody>{''.join(quality)}</tbody></table></div>
<h2>Custos e uso</h2><p>Cobrança de API local: indexação {sum(i['metrics']['api_cost'] for i in indexes):.2f} BRL; extrações {sum(r['api_cost'] for r in rows):.2f} BRL. Custo de máquina das extrações: {machine_text}. A tarifa ausente não significa hardware ou energia gratuitos. Tokens de entrada nas extrações {sum(r['input_tokens'] for r in rows):,}; saída {sum(r['output_tokens'] for r in rows):,}; chamadas de modelo {sum(r['model_calls'] for r in rows):,}. Chamadas com uso desconhecido: {unknown_usage}.</p><p>Tempo de indexação acumulado {index_seconds:.2f} s. Tempo de extração acumulado {extract_seconds:.2f} s. Reutilização dos índices: {escape(reuse_text)}. Downloads, preparação dos contêineres e testes preliminares estão fora desses totais.</p><p><label>Simular tarifa de máquina (BRL/h) <input id="rate" type="number" min="0" step="0.1" placeholder="Informe uma tarifa"></label> <output id="cost">Simulação não configurada</output></p><p><a href="executions.csv">Execuções CSV</a> · <a href="stages.csv">Etapas CSV</a> · <a href="measurements.json">Medições JSON</a> · <a href="audit.json.gz">Trilha completa compactada</a></p>
<details><summary>Duração, tokens e custo por etapa e execução</summary><p>Tempos inclusivos. Chamadas MCP, rodadas e campos contêm subetapas e podem se sobrepor. Tokens e custos de API são atribuídos somente à operação do modelo que os consumiu.</p><div class="scroll"><table><thead><tr><th>Corpus</th><th>Execução</th><th>Etapa</th><th>Operações</th><th>Segundos</th><th>Erros</th><th>Entrada</th><th>Saída</th><th>API BRL</th></tr></thead><tbody>{''.join('<tr>'+''.join('<td>'+escape(v)+'</td>' for v in row)+'</tr>' for row in stage_rows)}</tbody></table></div></details>
<h2>Testes de engenharia</h2><p>{escape(test_text)} O protocolo MCP e a integridade dos dois bancos foram exercitados com serviços reais. Timeout, cache e truncamento foram verificados com transporte simulado. A aprovação dessa suíte verifica os contratos implementados e não substitui a avaliação de qualidade.</p><p><a href="../validation/junit.xml">Resultado JUnit</a> · <a href="end-to-end.json">Auditoria dos resultados completos</a> · <a href="../validation/environment.json">Ambiente e digests</a> · <a href="../../docs/IMPLEMENTACAO.md">Implementação e limites</a> · <a href="../../docs/DISCUSSAO.md">Crítica e próximos passos</a></p>
<p>Os resultados acima pertencem ao snapshot experimental arquivado. Após o benchmark, foram acrescentadas verificações para campos inválidos, sobreposição alta e falha na inicialização. A conferência dos 1.057 trechos preservou conteúdo e offsets; prompts e funções de extração por campo permaneceram iguais. <a href="../validation/release.json">Verificação da versão de entrega e extração real adicional</a>.</p>
<details><summary>Formulários JSON produzidos e evidências</summary><p>Saídas reais do experimento, incluindo os erros discutidos abaixo. Cada formulário possui arquivo de evidências e estados por campo.</p><ul>{''.join('<li>'+escape(item['name'])+' · <a href="'+item['result']+'">JSON</a> · <a href="'+item['evidence']+'">Evidências</a></li>' for item in output_links)}</ul><p><a href="frozen-inputs.zip">Código e insumos congelados</a></p></details>
<h2>Discussão</h2>{''.join('<p>'+escape(paragraph)+'</p>' for paragraph in discussion)}<p>{limits}</p>
<h2>Falhas observadas com citações reais</h2>{''.join(example_html) if example_html else '<p>Nenhum exemplo selecionado nesta execução parcial.</p>'}
<h2>Respostas, evidências e investigação</h2><label>Corpus <select id="corpus"><option value="">Todos</option><option>adpf54</option><option>dom-casmurro</option></select></label> <label>Variante <select id="variant"><option value="">Todas</option>{''.join('<option>'+v+'</option>' for v in 'ABCDEF')}</select></label>
{''.join(details)}<script>const filter=()=>{{for(const row of document.querySelectorAll('details[data-corpus]'))row.hidden=(document.getElementById('corpus').value&&row.dataset.corpus!==document.getElementById('corpus').value)||(document.getElementById('variant').value&&row.dataset.variant!==document.getElementById('variant').value);}};document.getElementById('corpus').onchange=filter;document.getElementById('variant').onchange=filter;document.getElementById('rate').oninput=()=>{{const value=document.getElementById('rate').value;const rate=Number(value);document.getElementById('cost').textContent=value!==''&&rate>=0?'Projeção: indexação '+(rate*{index_seconds}/3600).toFixed(2)+' BRL; extrações '+(rate*{extract_seconds}/3600).toFixed(2)+' BRL':'Simulação não configurada';}};</script></main></html>'''
    (destination/'relatorio.html').write_text(document,encoding='utf-8')
    summary=f"# {title}\n\nEstado {status}. {completed}/{total} execuções e {len(field_rows)} avaliações de campos.\n\n## Método\n\n{method}\n\n## Resultados\n\n| Corpus | Variante | Repetições | Exatidão | Mediana s | Intervalo s | MCP | Rodadas |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n"+'\n'.join(markdown)+"\n\n## Discussão\n\n"+'\n\n'.join(discussion)+f"\n\n{limits}\n\n[Relatório interativo](relatorio.html) · [Medições](measurements.json)\n"
    summary+=f"\n## Qualidade detalhada\n\n| Corpus | Variante | Preenchidos | Precisão | Página encontrada | Precisão listas | Cobertura listas | Abstenção estrita | Limites | Erros |\n| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n"+'\n'.join(quality_markdown)
    summary+=f"\n\n## Custos e testes\n\nIndexação: {index_seconds:.2f} s; extrações: {extract_seconds:.2f} s acumulados. API local: zero BRL. Custo de máquina das extrações: {machine_text}. Downloads e preparação do ambiente estão fora desses totais.\n\n{test_text}\n\n[Etapas CSV](stages.csv) · [Trilha de auditoria](audit.json.gz) · [Implementação e limites](../../docs/IMPLEMENTACAO.md)\n"
    summary+='\n## Falhas observadas\n\n'+'\n\n'.join(example_markdown)+'\n'
    summary+='\n## Versão de entrega\n\nO benchmark conserva seu código em frozen-inputs.zip. A versão de entrega acrescenta controles para entradas inválidas, sobreposição alta e falha na inicialização. Conteúdo e offsets dos 1.057 trechos foram comparados e permaneceram iguais. Os prompts e as funções de extração por campo não mudaram. [Verificação e extração adicional](../validation/release.json).\n'
    (destination/'RELATORIO.md').write_text(summary,encoding='utf-8')
    render_graph(name)
    export_inputs(name)
    return destination/'relatorio.html'
