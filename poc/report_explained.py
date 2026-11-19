"""Add the plain-language reading guide to the preserved November 2026 experiment."""
import ast
from collections import Counter
import html
import json
from pathlib import Path
import re
import statistics
import zipfile

from .common import ROOT

EXPERIMENT = 'a1f0b3e18acd9bc0b5842aa3c613fd5138e3a3f675e9d73094a538c2bf5b3819'


def explained_report(technical_html, measurements, frozen_path):
    # Interpretation and examples describe this experiment, not arbitrary future runs.
    if measurements['benchmark']['input_fingerprint'] != EXPERIMENT:
        return technical_html
    esc = lambda value: html.escape(str(value))
    fmt = lambda value, digits=0: f'{value:,.{digits}f}'.replace(',', '_').replace('.', ',').replace('_', '.')
    runs = measurements['executions']
    indexes = measurements['indexes']
    fields = measurements['fields']
    statuses = Counter(row['status'] for row in fields)
    with zipfile.ZipFile(frozen_path) as archive:
        indexing = ast.parse(archive.read('poc/indexing.py').decode('utf-8-sig'))
        models = ast.parse(archive.read('poc/models.py').decode('utf-8-sig'))
        extraction = ast.parse(archive.read('poc/extraction.py').decode('utf-8-sig'))
    graph_prompt = next(node.value.left.value for node in ast.walk(indexing)
                        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'prompt' for t in node.targets)
                        and isinstance(node.value, ast.BinOp))
    system_prompt = next(node.value for node in ast.walk(models) if isinstance(node, ast.Constant)
                         and isinstance(node.value, str) and node.value.startswith('Você extrai informações'))
    strings = [node.value for node in ast.walk(extraction) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
    extraction_prompt = next(value for value in strings if value.startswith('Extraia somente'))
    verification_prompt = next(value for value in strings if value.startswith('Confira a resposta'))
    schema = next(ast.literal_eval(node.value) for node in ast.walk(indexing) if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == 'ENRICHMENT_SCHEMA' for t in node.targets))
    index_seconds = sum(i['metrics']['wall_seconds'] for i in indexes)
    extract_seconds = sum(r['wall_seconds'] for r in runs)
    enrichment = sum(i['metrics']['stages']['enrichment']['inclusive_ms'] for i in indexes) / 1000
    graph_facts = sum(i['facts'] for i in indexes)
    rejected = sum(i['rejected_facts'] for i in indexes)
    labels = {'A': 'Palavras', 'B': 'Palavras + sentido', 'C': 'B + resumos',
              'D': 'B + grafo', 'E': 'B + resumos + grafo', 'F': 'E + novas buscas'}
    charts = []
    for corpus, title in [('adpf54', 'Documento judicial'), ('dom-casmurro', 'Livro de literatura')]:
        bars = []
        for variant, label in labels.items():
            entries = [r for r in runs if r['corpus'] == corpus and r['variant'] == variant]
            accuracy = statistics.mean(r['accuracy'] for r in entries) * 100
            correct = statistics.mean(r['correct_fields'] for r in entries)
            count = entries[0]['fields']
            median = statistics.median(r['wall_seconds'] for r in entries)
            bars.append(f'<tr><th scope="row">{variant} · {label}</th><td><div class="bar" aria-hidden="true"><span style="width:{accuracy:.4f}%"></span></div><strong>{fmt(accuracy, 1)}%</strong></td><td>{fmt(correct)} de {count}</td><td>{fmt(median, 1)} s</td></tr>')
        charts.append(f'<section class="result-panel" data-result="{corpus}" aria-label="{title}"><h3>{title}</h3><div class="scroll" tabindex="0" aria-label="Tabela de resultados de {title}"><table><caption>Acertos por formulário e tempo mediano nas três repetições</caption><thead><tr><th scope="col">Forma de procurar</th><th scope="col">Acerto automático</th><th scope="col">Campos corretos</th><th scope="col">Tempo / formulário</th></tr></thead><tbody>{"".join(bars)}</tbody></table></div></section>')
    index_rows = []
    for row in indexes:
        index_rows.append('<tr>' + ''.join(f'<td>{esc(value)}</td>' for value in [
            'Acórdão ADPF 54' if row['corpus'] == 'adpf54' else 'Dom Casmurro',
            row['pages'], row['chunks'], row['sections'], row['facts'], row['rejected_facts'],
            fmt(row['metrics']['wall_seconds'], 2) + ' s']) + '</tr>')
    stages = []
    for stage, label in [('parse', 'Ler o texto do PDF'), ('enrichment', 'Fazer resumos e relações'),
                         ('embedding', 'Produzir os vetores'), ('search_index', 'Gravar no OpenSearch'),
                         ('graph_index', 'Gravar no Neo4j')]:
        seconds = sum(i['metrics']['stages'][stage]['inclusive_ms'] for i in indexes) / 1000
        stages.append(f'<tr><th scope="row">{label}</th><td>{fmt(seconds, 2)} s</td></tr>')
    body = technical_html.split('<main>', 1)[1].rsplit('</main>', 1)[0]
    body = body.replace('<h1>', '<h3>').replace('</h1>', '</h3>')
    values = {
        'SYSTEM_PROMPT': esc(system_prompt), 'GRAPH_PROMPT': esc(graph_prompt.strip()),
        'EXTRACTION_PROMPT': esc(extraction_prompt), 'VERIFICATION_PROMPT': esc(verification_prompt),
        'GRAPH_SCHEMA': esc(json.dumps(schema, ensure_ascii=False, indent=2)),
        'RESULTS': ''.join(charts), 'INDEX_ROWS': ''.join(index_rows), 'STAGE_ROWS': ''.join(stages),
        'INDEX_SECONDS': fmt(index_seconds, 2), 'EXTRACT_SECONDS': fmt(extract_seconds, 2),
        'ENRICHMENT_PERCENT': fmt(enrichment / index_seconds * 100, 1),
        'FACTS': fmt(graph_facts), 'REJECTED': fmt(rejected), 'PROPOSED': fmt(graph_facts + rejected),
        'FILLED': fmt(statuses['filled']), 'LIMIT': fmt(statuses['limit_reached']), 'NOT_FOUND': fmt(statuses['not_found']),
        'CORRECT_FILLED': fmt(sum(r['correct'] for r in fields if r['status'] == 'filled')),
        'CORRECT_TOTAL': fmt(sum(r['correct'] for r in fields)),
        'MCP_CALLS': fmt(sum(r['mcp_calls'] for r in runs)),
        'ROUNDS': fmt(sum(r['agent_rounds'] for r in runs)),
        'MODEL_CALLS': fmt(sum(r['model_calls'] for r in runs)),
        'INPUT_TOKENS': fmt(sum(r['input_tokens'] for r in runs)),
        'OUTPUT_TOKENS': fmt(sum(r['output_tokens'] for r in runs)),
        'TECHNICAL': body,
    }
    template = (Path(__file__).parent / 'report_explained.html').read_text(encoding='utf-8')
    return re.sub(r'@@([A-Z_]+)@@', lambda match: values[match.group(1)], template)


def rebuild_saved_report(name='full'):
    """Refresh only the HTML, without inference, services, or rewriting the measurements."""
    directory = ROOT / 'reports' / name
    path = directory / 'relatorio.html'
    original = path.read_text(encoding='utf-8')
    start, end = '<!-- TECHNICAL-START -->', '<!-- TECHNICAL-END -->'
    if start in original:
        original = '<main>' + original.split(start, 1)[1].split(end, 1)[0] + '</main>'
    measurements = json.loads((directory / 'measurements.json').read_text(encoding='utf-8'))
    path.write_text(explained_report(original, measurements, directory / 'frozen-inputs.zip'), encoding='utf-8')
    return path


if __name__ == '__main__':
    print(rebuild_saved_report())
