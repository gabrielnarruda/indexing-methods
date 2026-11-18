"""Build versioned example forms and a separate, source-linked evaluation set."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from poc.common import ROOT, write_json

STRING={'type':'string'}
LIST={'type':'array','items':STRING,'uniqueItems':True}
INTEGER={'type':'integer'}
BOOLEAN={'type':'boolean'}

judicial=[
 ('identificacao','/processo/identificacao','Qual é a classe e o número do processo principal deste acórdão?',STRING,'ADPF 54',[1],['ADPF 54','descumprimento de preceito fundamental 54']),
 ('tribunal','/processo/tribunal','Qual tribunal proferiu o acórdão?',STRING,'Supremo Tribunal Federal',[1],['STF','Supremo Tribunal Federal']),
 ('relator','/processo/relator','Quem é o ministro relator da ADPF 54?',STRING,'Marco Aurélio',[1],[]),
 ('requerente','/partes/requerente','Qual entidade é a requerente da ADPF 54?',STRING,'Confederação Nacional dos Trabalhadores na Saúde',[1],['CNTS']),
 ('advogado_requerente','/partes/advogado_requerente','Quem é o advogado da requerente indicado no cabeçalho da ADPF 54?',STRING,'Luís Roberto Barroso',[1],[]),
 ('interessado','/partes/interessado','Quem consta como interessado no cabeçalho da ADPF 54?',STRING,'Presidente da República',[1],[]),
 ('advogado_interessado','/partes/advogado_interessado','Quem representa o interessado no cabeçalho da ADPF 54?',STRING,'Advogado-Geral da União',[1],[]),
 ('data_julgamento','/decisao/data','Qual é a data do julgamento final de mérito da ADPF 54? Use AAAA-MM-DD.',STRING,'2012-04-12',[1,433],[]),
 ('orgao','/decisao/orgao','Qual órgão julgador do STF proferiu o julgamento de mérito?',STRING,'Plenário',[1],[]),
 ('resultado','/decisao/resultado','A ação principal foi julgada procedente ou improcedente no resultado final?',STRING,'procedente',[1,433],[]),
 ('maioria','/decisao/por_maioria','O julgamento final foi decidido por maioria? Responda booleano.',BOOLEAN,True,[1,433],[]),
 ('presidente','/decisao/presidente','Quem presidiu a sessão final de julgamento da ADPF 54?',STRING,'Cezar Peluso',[1,433],[]),
 ('artigos','/decisao/artigos_codigo_penal','Quais números de artigos do Código Penal aparecem no dispositivo do acórdão? Retorne strings com os números.',LIST,['124','126','128'],[1,433],[]),
 ('origem','/processo/origem','Qual unidade da federação consta como origem da ADPF 54?',STRING,'Distrito Federal',[1],['DF']),
 ('ajuizamento','/cronologia/ajuizamento','Em que data a CNTS formalizou a arguição, segundo o relatório? Use AAAA-MM-DD.',STRING,'2004-06-17',[2],[]),
 ('ano_audiencia','/cronologia/ano_audiencia','Em que ano ocorreram as sessões da audiência pública descritas no relatório?',INTEGER,2008,[20],[]),
 ('datas_audiencia','/cronologia/datas_audiencia','Quais foram as quatro datas das sessões da audiência pública descritas no relatório? Use AAAA-MM-DD.',LIST,['2008-08-26','2008-08-28','2008-09-04','2008-09-16'],[20],[]),
 ('improcedentes','/decisao/ministros_pela_improcedencia','Quais ministros votaram pela improcedência no resultado final, segundo a ata?',LIST,['Ricardo Lewandowski','Cezar Peluso'],[433],[]),
 ('impedido','/decisao/ministro_impedido','Qual ministro aparece como impedido na ata da sessão de 11 de abril de 2012?',STRING,'Dias Toffoli',[253,433],[]),
 ('condicoes','/decisao/ministros_com_condicoes','Quais ministros julgaram procedente acrescentando condições de diagnóstico, segundo a ata final?',LIST,['Gilmar Mendes','Celso de Mello'],[433],[]),
 ('pgr','/decisao/procurador_geral','Qual é o nome do Procurador-Geral da República presente no julgamento final, segundo a ata?',STRING,'Roberto Monteiro Gurgel Santos',[433],['Roberto Gurgel']),
 ('primeira_sessao','/cronologia/sessao_suspensa','Em qual data ocorreu a sessão em que o julgamento de mérito foi suspenso depois do voto de Ricardo Lewandowski? Use AAAA-MM-DD.',STRING,'2012-04-11',[253,433],[]),
 ('multa','/decisao/multa_diaria','Qual valor de multa diária o dispositivo deste acórdão fixou contra a requerente?',{'type':'number'},None,[],[]),
 ('conta','/partes/conta_bancaria_requerente','Qual número de conta bancária da requerente é informado no cabeçalho do processo?',STRING,None,[],[])
]

literature=[
 ('titulo','/obra/titulo','Qual é o título da obra?',STRING,'Dom Casmurro',[1],[]),
 ('autor','/obra/autor','Quem é o autor da obra?',STRING,'Machado de Assis',[1],[]),
 ('pai','/familia/pai','Qual é o nome completo do pai do narrador, mencionado no capítulo D. Glória?',STRING,'Pedro de Albuquerque Santiago',[5],[]),
 ('mae','/familia/mae','Como se chama a mãe de Bentinho?',STRING,'Glória',[5],[]),
 ('tio','/familia/tio','Qual é o nome do tio de Bentinho que trabalhava no crime como advogado?',STRING,'Cosme',[5],[]),
 ('profissao_tio','/familia/profissao_tio','Qual é a profissão de tio Cosme?',STRING,'advogado',[5],[]),
 ('prima','/familia/prima','Qual é o nome da prima viúva que morava na casa da mãe do narrador?',STRING,'Justina',[5],[]),
 ('amigo','/relacoes/nome_amigo','Qual é o nome completo do seminarista Escobar quando ele é apresentado no capítulo Um seminarista?',STRING,'Ezequiel de Sousa Escobar',[46],[]),
 ('filho','/familia/filho','Qual nome foi dado ao filho do narrador na pia batismal?',STRING,'Ezequiel',[82],[]),
 ('homenagem','/relacoes/homenagem_filhos','O nome dado ao filho do narrador homenageia qual amigo?',STRING,'Escobar',[82],[]),
 ('olhos_autor','/relacoes/autor_descricao_olhos','Quem descreveu os olhos de Capitu como de cigana oblíqua e dissimulada?',STRING,'José Dias',[20,26],[]),
 ('casa','/lugares/casa_reconstruida','Em que bairro o narrador construiu a casa que reproduz a casa da infância?',STRING,'Engenho Novo',[1,33],[]),
 ('escobar_desejo','/eventos/desejo_escobar','Qual atividade Escobar desejava seguir em vez de terminar o curso do seminário?',STRING,'comércio',[61,74],[]),
 ('idade_mae','/familia/idade_mae_viuvez','Quantos anos tinha a mãe do narrador quando morreu o marido?',INTEGER,31,[5],[]),
 ('viuvos','/familia/tres_viuvos','Quais eram os três viúvos da casa descrita no capítulo Tio Cosme?',LIST,['Cosme','Justina','Glória'],[5],[]),
 ('cpf','/familia/cpf_narrador','Qual é o número de CPF do narrador registrado no livro?',STRING,None,[],[])
]


def build():
    cases=[]
    for corpus,rows in [('adpf54',judicial),('dom-casmurro',literature)]:
        fields=[]
        for index,(identifier,path,question,schema,expected,pages,aliases) in enumerate(rows):
            fields.append({'id':identifier,'path':path,'question':question,'value_schema':schema,
                           'absence_policy':'null_with_status','scope':'provided_corpus_only'})
            cases.append({'corpus_id':corpus,'field_id':identifier,'expected':expected,'aliases':aliases,
                          'reference_pages':pages,'split':'held_out' if index%3==2 else 'development',
                          'annotation':'assistant_prepared_source_linked','reference_status':'provisional',
                          'rubric':'Match the requested value with attributable supporting evidence. Reference pages are alternatives unless explicitly marked as jointly required.'})
        write_json(ROOT/'forms'/f'{corpus}.json',{'version':1,'corpus_id':corpus,'fields':fields})
    write_json(ROOT/'evaluation/cases.json',{'version':1,'human_reviewed':False,'cases':cases})


if __name__=='__main__':
    build()
