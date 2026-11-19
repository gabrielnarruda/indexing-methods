"""Readable, offline export of the same measurements shown in the local UI."""
import html
import json


def escape(value):
    return html.escape(str(value))


def duration(ms):
    if ms is None:return 'Não medido'
    if 0<ms<1:return '&lt;1 ms'
    if ms<1000:return f'{ms:.0f} ms'
    return f'{ms/1000:.3f} s'.replace('.',',')


def report(data):
    metrics=data['metrics']
    evaluation=(data.get('result') or {}).get('evaluation') or {}
    def cost(value):
        return 'Não configurado' if value is None else escape(f"{metrics['currency']} {value:.4f}")
    stages=''.join(
        f"<tr><th>{escape(s['label'])}</th><td>{duration(s.get('duration_ms'))}"
        f"{' · parcial' if s.get('duration_is_partial') or s.get('duration_is_running') else ''}</td>"
        f"<td>{escape(s['status'])}</td><td>{duration(s.get('history_ms')) if s.get('history_ms') is not None else '—'}</td>"
        f"<td>{cost(s.get('api_cost'))}</td><td>{cost(s.get('machine_cost_estimate'))}</td></tr>"
        for s in metrics['stages'])
    fields=''.join(
        '<tr><th>'+escape(field['question'])+'</th><td>'+escape(json.dumps(field['value'],ensure_ascii=False))+
        '</td><td>'+escape(field['status'])+'</td><td>'+escape(field.get('reason',''))+'</td></tr>'
        for field in data.get('fields',[]))
    accuracy=evaluation.get('accuracy')
    quality='Não avaliado' if accuracy is None else f"{accuracy*100:.1f}% · {evaluation['annotated_count']} campos anotados"
    wall=duration(metrics['wall_seconds']*1000 if metrics['wall_seconds'] is not None else None)
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Run {escape(data['id'])}</title>
<style>body{{font:16px/1.6 system-ui;color:#18352e;background:#f4f6f2;margin:0;padding:clamp(16px,4vw,48px)}}main{{max-width:1200px;margin:auto}}h1{{line-height:1.15}}.meta{{color:#53685f}}.cards{{display:flex;flex-wrap:wrap;gap:16px}}.cards div{{padding:16px;background:white;border:1px solid #d5dfd7;flex:1;min-width:180px}}strong{{display:block}}section{{background:white;border:1px solid #d5dfd7;margin:24px 0;padding:20px}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;text-align:left}}th,td{{border-bottom:1px solid #e3e8e2;padding:12px;vertical-align:top}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}summary{{cursor:pointer;font-weight:600}}code{{overflow-wrap:anywhere}}</style></head>
<body><main><p class="meta">Indexing Methods · relatório local · dados reais</p>
<h1>{escape(data['request']['recipe']['name'])}</h1>
<p><code>{escape(data['id'])}</code> · {escape(data['corpus_id'])} · {escape(data['status'])}</p>
<div class="cards"><div><span>Acerto automático</span><strong>{quality}</strong></div><div><span>Tempo da run</span><strong>{wall}</strong></div><div><span>Custo total estimado</span><strong>{cost(metrics['total_cost'])}</strong></div><div><span>Investigação</span><strong>{metrics['mcp_calls']} chamadas MCP · {metrics['agent_rounds']} rodadas</strong></div></div>
<p>Espera na fila: {duration(metrics['queue_seconds']*1000 if metrics['queue_seconds'] is not None else None)}. Referências provisórias; acerto automático não substitui revisão humana.</p>
<section><h2>Tempo de cada etapa</h2><div class="scroll"><table><thead><tr><th>Etapa</th><th>Duração nesta run</th><th>Estado</th><th>Construção anterior</th><th>API</th><th>Máquina estimada</th></tr></thead><tbody>{stages}</tbody></table></div>
<p>{escape(metrics['timing_note'])}</p><p>Etapas não executadas e durações desconhecidas não são medições de zero. Construção anterior não é somada ao trabalho novo. Custos de hardware sem tarifa permanecem desconhecidos.</p></section>
<section><h2>Respostas</h2><div class="scroll"><table><thead><tr><th>Pergunta</th><th>Valor</th><th>Estado</th><th>Motivo</th></tr></thead><tbody>{fields}</tbody></table></div></section>
<details><summary>Configuração, evidências, eventos e métricas completas (JSON)</summary><pre>{escape(json.dumps(data,ensure_ascii=False,indent=2))}</pre></details>
</main></body></html>'''
