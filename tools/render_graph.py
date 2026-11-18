"""Export a small, offline explorer of the indexed assertions and their sources."""
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def render_graph(name='full'):
    corpora = {}
    for corpus in ('adpf54', 'dom-casmurro'):
        manifest = read(ROOT/'data/indexes'/f'{corpus}.json')
        directory = ROOT/manifest['directory']
        document = read(directory/'document.json')
        chunks = {chunk['id']: chunk for chunk in document['chunks']}
        facts = []
        for section in document['sections']:
            for fact in read(directory/f"{section['id']}.json")['facts']:
                chunk = chunks[fact['chunk_id']]
                facts.append({**fact, 'page': chunk['page'], 'start': chunk['start'],
                              'end': chunk['end']})
        corpora[corpus] = {'facts': facts, 'source': document['source']['filename'],
                          'hash': manifest['source_hash'], 'pages': manifest['pages']}
    template = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Indexing Methods · Grafo de afirmações</title>
<style>body{margin:0;background:#f5f6f3;color:#203641;font:16px/1.5 system-ui,sans-serif}main{max-width:1250px;margin:auto;padding:28px}h1{font-size:30px;line-height:1.2}a{color:#215d89}label{display:inline-flex;flex-direction:column;margin-right:14px;gap:5px}select,input,button{font:inherit;padding:8px;border:1px solid #9bafb6;border-radius:6px;background:white;color:inherit}select{max-width:360px}button{cursor:pointer}.controls{display:flex;gap:12px;flex-wrap:wrap;align-items:end}.graph{margin-top:20px;border:1px solid #becdd0;border-radius:10px;background:white;overflow:auto}svg{display:block;min-width:1000px;width:100%}.node{cursor:pointer}.node:focus{outline:none}.node:focus rect,.node:hover rect{stroke:#216d62;stroke-width:3}svg text{font:15px system-ui,sans-serif;fill:#203641;pointer-events:none}.muted{font-size:14px;color:#506771}.detail{background:#fff;border:1px solid #becdd0;border-radius:10px;padding:20px;margin-top:16px}blockquote{border-left:3px solid #277566;padding-left:15px;white-space:pre-wrap}#count{margin-top:12px}#source{display:inline-block} @media(max-width:650px){main{padding:18px}select,input{max-width:280px}.controls{align-items:start;flex-direction:column}}</style>
<main><p><a href="../../docs/arquitetura.html">Arquitetura</a> · <a href="relatorio.html">Resultados</a> · <a href="https://github.com/gabrielnarruda/indexing-methods">Repositório privado</a></p><h1>Grafo de afirmações e fontes</h1><p>Explore relações realmente extraídas dos PDFs. Cada afirmação volta a um trecho com página e citação. A existência da citação não garante que a relação tenha sido interpretada corretamente.</p>
<div class="controls"><label>Documento<select id="corpus"><option value="adpf54">ADPF 54</option><option value="dom-casmurro">Dom Casmurro</option></select></label><label>Filtrar entidades<input id="query" type="search" placeholder="Nome ou expressão"></label><label>Entidade<select id="entity"></select></label><button id="prev" type="button">Anterior</button><button id="next" type="button">Próximas relações</button></div><p class="muted" id="count"></p>
<div class="graph"><svg id="graph" role="group" aria-label="Entidade, afirmações e trechos de suporte"></svg></div>
<section class="detail" aria-live="polite"><h2 id="heading">Selecione uma afirmação</h2><p id="relation"></p><blockquote id="quote"></blockquote><p id="metadata" class="muted"></p><a id="source" target="_blank" rel="noreferrer" hidden>Abrir página do PDF local</a></section>
<p class="muted">Nós verdes representam a entidade selecionada, azuis representam afirmações e cinzas representam trechos. A exploração é uma cópia estática dos dados indexados. O PDF abre se o corpus estiver baixado na estrutura do projeto. Não há conexão com serviços externos.</p></main>
<script id="data" type="application/json">__DATA__</script><script>
const data=JSON.parse(document.getElementById('data').textContent),svg=document.getElementById('graph'),select=document.getElementById('entity');let page=0;
const norm=s=>s.toLocaleLowerCase('pt-BR').replace(/\\s+/g,' ').trim();
function node(name,attrs={},text){const el=document.createElementNS('http://www.w3.org/2000/svg',name);for(const [k,v] of Object.entries(attrs))el.setAttribute(k,v);if(text!==undefined)el.textContent=text;return el;}
function current(){return data[document.getElementById('corpus').value];}
function short(s,n=35){return s.length>n?s.slice(0,n-1)+'…':s;}
function info(f){document.getElementById('heading').textContent=f.predicate;document.getElementById('relation').textContent=f.subject+' → '+f.predicate+' → '+f.object;document.getElementById('quote').textContent=f.quote;document.getElementById('metadata').textContent='Página '+f.page+' · '+f.chunk_id+' · offsets '+f.start+'–'+f.end+' · data '+(f.date||'não informada')+' · autor '+(f.speaker||'não informado');const link=document.getElementById('source');link.hidden=false;link.href='../../data/raw/'+current().source+'#page='+f.page;}
function box(x,y,w,h,title,subtitle,color,f){const g=node('g',{class:'node',tabindex:'0',role:'button','aria-label':title+' '+subtitle});g.append(node('rect',{x,y,width:w,height:h,rx:10,fill:color,stroke:'#9bafb6'}));g.append(node('title',{},title+' · '+subtitle));g.append(node('text',{x:x+14,y:y+29},short(title,w>300?40:24)));g.append(node('text',{x:x+14,y:y+53},short(subtitle,w>300?44:26)));g.onclick=()=>info(f);g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();info(f);}};svg.append(g);}
function draw(){svg.replaceChildren();const all=current().facts.filter(f=>norm(f.subject)===select.value||norm(f.object)===select.value),visible=all.slice(page*8,page*8+8);const height=Math.max(180,visible.length*118+40);svg.setAttribute('viewBox','0 0 1120 '+height);svg.style.height=height+'px';document.getElementById('count').textContent=current().facts.length+' afirmações no documento · '+all.length+' ligadas à entidade · exibindo '+(all.length?page*8+1:0)+'–'+Math.min(page*8+8,all.length);document.getElementById('prev').disabled=page===0;document.getElementById('next').disabled=(page+1)*8>=all.length;if(!visible.length){svg.append(node('text',{x:24,y:50},'Nenhuma entidade encontrada.'));return;}const center=height/2;visible.forEach((f,i)=>{const y=30+i*118;svg.append(node('path',{d:'M270 '+center+' C320 '+center+' 330 '+(y+38)+' 380 '+(y+38),fill:'none',stroke:'#72928d','stroke-width':1.5}));svg.append(node('path',{d:'M770 '+(y+38)+' H860',fill:'none',stroke:'#72928d','stroke-width':1.5}));svg.append(node('text',{x:782,y:y+28},'fonte'));box(380,y,390,78,f.predicate,(norm(f.subject)===select.value?'objeto: '+f.object:'sujeito: '+f.subject),'#e9f1f9',f);box(860,y,230,78,'Página '+f.page,'Trecho '+f.start+'–'+f.end,'#f0f3f3',f);});box(25,center-39,245,78,select.selectedOptions[0].textContent,'entidade selecionada','#e4f3ed',visible[0]);}
function populate(){const previous=select.value,query=norm(document.getElementById('query').value),counts=new Map();for(const fact of current().facts){for(const label of new Set([fact.subject,fact.object])){const key=norm(label);const row=counts.get(key)||{label,n:0};row.n++;counts.set(key,row);}}select.replaceChildren();for(const [key,row] of [...counts].filter(([key])=>key.includes(query)).sort((a,b)=>b[1].n-a[1].n||a[0].localeCompare(b[0]))){const option=document.createElement('option');option.value=key;option.textContent=row.label+' ('+row.n+')';select.append(option);}if([...select.options].some(o=>o.value===previous))select.value=previous;page=0;document.getElementById('heading').textContent='Selecione uma afirmação';for(const id of ['relation','quote','metadata'])document.getElementById(id).textContent='';document.getElementById('source').hidden=true;draw();}
document.getElementById('corpus').onchange=()=>{document.getElementById('query').value='';populate();};document.getElementById('query').oninput=populate;select.onchange=()=>{page=0;draw();};document.getElementById('prev').onclick=()=>{page--;draw();};document.getElementById('next').onclick=()=>{page++;draw();};populate();
</script><style>#source[hidden]{display:none}</style></html>'''
    destination = ROOT/'reports'/name/'grafo.html'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(template.replace('__DATA__', json.dumps(corpora, ensure_ascii=False).replace('<', '\\u003c')), encoding='utf-8')
    return destination


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--name',default='full')
    print(render_graph(parser.parse_args().name))
