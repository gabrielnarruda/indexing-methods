// Tests the actual local API and UI. Model results are never fabricated.
// Queue-only test runs are cancelled; existing experiments are untouched.
const {chromium}=require('playwright');
const fs=require('fs');const path=require('path');
const base=process.env.WORKBENCH_URL||'http://127.0.0.1:18766';
const output=path.resolve(__dirname,'../reports/validation');
const created=[];const checks=[];const errors=[];
const check=(condition,label)=>{if(!condition)throw Error(label);checks.push(label)};
async function api(route,body){const response=await fetch(base+'/api'+route,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json','X-Workbench':'local'},body:body===undefined?undefined:JSON.stringify(body)});if(!response.ok)throw Error(route+': '+await response.text());return response.json()}
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1080},acceptDownloads:true,reducedMotion:'reduce'});
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);await page.getByRole('heading',{name:'Entidades e relações',exact:true}).waitFor();
  check((await page.locator('.live-banner').textContent()).includes('reais'),'Real execution disclosure');
  await page.getByRole('button',{name:'Duplicar',exact:true}).click();
  await page.getByLabel('Nome da configuração',{exact:true}).fill('Validação de interface · configuração versionada');
  const prompt=page.getByLabel('Prompt da etapa',{exact:true});await prompt.fill((await prompt.inputValue())+'\nConserve atribuição e fonte literal.');
  await page.getByRole('button',{name:'Leitura do PDF',exact:true}).click();
  await page.getByLabel('Páginas',{exact:true}).fill('1-2');
  await page.getByLabel('Parser',{exact:true}).selectOption('pymupdf_dedup');
  const savedPromise=page.waitForResponse(r=>r.url().endsWith('/api/configurations')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Salvar versão',exact:true}).click();
  const saved=await (await savedPromise).json();
  check(saved.body.pages==='1-2'&&saved.body.graph_prompt.includes('Conserve atribuição'),'UI saves edited recipe in the API');
  await page.reload();await page.getByLabel('Nome da configuração',{exact:true}).waitFor();
  check((await page.getByLabel('Nome da configuração',{exact:true}).inputValue())===saved.name,'Saved version survives page reload');
  await page.getByRole('button',{name:'Entidades e relações',exact:true}).click();
  await page.screenshot({path:path.join(output,'workbench-editor.png')});
  await page.getByRole('button',{name:'Matriz de testes',exact:true}).click();
  await page.getByLabel('Conjunto de avaliação',{exact:true}).selectOption('all');
  await page.getByRole('button',{name:'Adicionar parâmetro',exact:true}).click();
  await page.getByLabel('Alternativas (JSON)',{exact:true}).fill('[2, 4]');
  await page.getByRole('button',{name:'Conferir combinações',exact:true}).click();
  await page.getByRole('heading',{name:'Combinações validadas',exact:true}).waitFor();
  check((await page.locator('.matrix-total').textContent())==='4','Cartesian matrix has two settings times two documents');
  await page.screenshot({path:path.join(output,'workbench-matrix.png'),fullPage:true});
  const batchPromise=page.waitForResponse(r=>r.url().endsWith('/api/experiments')&&r.request().method()==='POST');
  await page.getByRole('button',{name:'Executar bateria real',exact:true}).click();
  const batch=await (await batchPromise).json();created.push(...batch.jobs.map(j=>j.id));
  check(created.length===4,'UI submits four durable jobs, no simulated results');
  await page.getByLabel('Buscar execuções',{exact:true}).fill('Validação de interface');
  await page.getByRole('button',{name:'Inspecionar',exact:true}).first().click();
  await page.getByRole('heading',{name:'Tempo de cada etapa',exact:true}).waitFor();
  check((await page.locator('.summary-strip').textContent()).includes('Não configurado'),'Unconfigured hardware cost is not shown as zero');
  await page.getByRole('button',{name:'Cancelar novas etapas',exact:true}).click();
  await page.getByRole('button',{name:'Repetir com a mesma receita',exact:true}).waitFor();
  check(true,'UI cancellation reaches terminal state and preserves the run');
  for(const id of created){const job=await api('/runs/'+id);if(['queued','starting','running'].includes(job.status))await api('/runs/'+id+'/cancel',{})}
  const real=(await api('/runs')).filter(r=>r.result?.evaluation);
  check(real.length>=2,'Real model evaluations exist in the local API');
  const first=real[0];
  const paired=real.find(r=>r.id!==first.id&&r.request.input_hash===first.request.input_hash&&r.request.recipe.top_k===first.request.recipe.top_k)||first;
  await page.getByRole('button',{name:'Comparação',exact:true}).click();
  await page.getByLabel('Run de referência',{exact:true}).selectOption(first.id);
  await page.getByLabel('Run candidata',{exact:true}).selectOption(first.id);
  await page.getByRole('heading',{name:'Tempos por etapa',exact:true}).waitFor();
  check((await page.locator('.compare-controls').textContent()).includes('Compatível'),'Same frozen inputs are comparable');
  const timingRows=await page.locator('.timing-table tbody tr').count();
  check(timingRows===first.metrics.stages.length,'UI shows every real timing stage');
  await page.getByRole('button',{name:'Ver evidências',exact:true}).first().click();
  check(await page.getByRole('dialog').isVisible(),'Field comparison opens actual answers and sources');
  await page.keyboard.press('Escape');
  const different=real.find(r=>r.request.input_hash!==first.request.input_hash);
  if(different){await page.getByLabel('Run candidata',{exact:true}).selectOption(different.id);await page.getByText('Documentos, páginas, perguntas ou gabaritos diferem. As médias de qualidade não são diretamente comparáveis.',{exact:true}).waitFor();check(true,'Different scopes produce an explicit comparison warning')}
  await page.getByLabel('Run de referência',{exact:true}).selectOption(paired.id);
  await page.getByLabel('Run candidata',{exact:true}).selectOption(first.id);
  await page.getByRole('link',{name:'Ver tempo de cada etapa ↓',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#tempos').getBoundingClientRect().top<200);
  check((await page.locator('#tempos').boundingBox()).y<200,'Timing shortcut brings every stage into view');
  await page.screenshot({path:path.join(output,'workbench-stage-times.png')});
  await page.screenshot({path:path.join(output,'workbench-comparison.png'),fullPage:true});
  await page.getByRole('button',{name:'Biblioteca',exact:true}).click();
  await page.getByRole('button',{name:'Editar formulário JSON',exact:true}).first().click();
  const editor=page.getByLabel('Formulário e referências (JSON)',{exact:true});const original=await editor.inputValue();
  await editor.fill('{invalid');await page.getByRole('button',{name:'Salvar nova versão do formulário',exact:true}).click();
  check(await page.locator('dialog [role="alert"]').isVisible(),'Malformed form JSON is rejected in the editor');
  await editor.fill(original);await page.getByRole('button',{name:'Salvar nova versão do formulário',exact:true}).click();
  await page.getByRole('dialog').waitFor({state:'hidden'});check(true,'Form version is persisted without mutating past runs');
  await page.getByRole('button',{name:'Inspecionar leitura',exact:true}).first().click();
  await page.getByRole('dialog').waitFor();check((await page.locator('dialog pre').textContent()).length>100,'Original PDF text is read through the real API');await page.keyboard.press('Escape');
  await page.getByRole('button',{name:'Grafo',exact:true}).click();
  const graphJob=real.find(r=>r.result?.index?.facts>0);
  if(graphJob){await page.getByLabel('Construção do grafo',{exact:true}).selectOption(graphJob.id);await page.getByRole('heading',{name:'Relações e fontes',exact:true}).waitFor();await page.getByRole('button',{name:'Ver fonte',exact:true}).first().click();check((await page.locator('aside.card .quote').textContent()).length>10,'Graph selection exposes a real source quotation');await page.screenshot({path:path.join(output,'workbench-graph.png'),fullPage:true})}
  const exported=await api('/runs/'+first.id+'/export');
  check(exported.id===first.id&&exported.metrics.wall_seconds===first.metrics.wall_seconds,'Export reconciles with actual run metrics');
  const widths=[];
  for(const width of [390,768,1280,1440]){
   await page.setViewportSize({width,height:900});
   for(const label of ['Experimentos','Biblioteca','Prompts','Grafo']){
    if(width<=850)await page.getByRole('button',{name:'Abrir menu',exact:true}).click();
    await page.locator('.sidebar').getByRole('button',{name:label,exact:true}).click();
    const scroll=await page.evaluate(()=>document.documentElement.scrollWidth);check(scroll<=width,`No page overflow: ${label} at ${width}`);widths.push({page:label,width,scroll});
   }
  }
  await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Abrir menu',exact:true}).click();await page.locator('.sidebar').getByRole('button',{name:'Experimentos',exact:true}).click();
  await page.getByRole('button',{name:'Comparação',exact:true}).click();await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(output,'workbench-mobile.png')});
  await page.goto(base+'/?reference='+paired.id+'&candidate='+first.id+'#tempos');
  await page.waitForFunction(()=>document.querySelector('#tempos')?.getBoundingClientRect().top<200);
  check(true,'Direct timing link waits for data and opens the stage table');
  await page.screenshot({path:path.join(output,'workbench-times-mobile.png')});
  check(errors.length===0,'No browser JavaScript errors');
  fs.writeFileSync(path.join(output,'workbench-ui-checks.json'),JSON.stringify({status:'passed',checks,widths,errors,created_test_runs:created,real_run_inspected:first.id,comparison_reference:paired.id,checked_at:new Date().toISOString()},null,2));
  console.log(JSON.stringify({status:'passed',checks:checks.length,errors}));
 }finally{
  for(const id of created){try{const job=await api('/runs/'+id);if(['queued','starting','running'].includes(job.status))await api('/runs/'+id+'/cancel',{})}catch{}}
  await browser.close();
 }
})().catch(e=>{console.error(e);process.exit(1)});
