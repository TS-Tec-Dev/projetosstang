"""Validações locais da fidelidade ao modelo PROJETO X e da segurança SQL."""
from datetime import date
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
from src.project_x import (
    SPECIFICATIONS, BY_CODE, DEFAULT_SECTION_NAMES, make_template_rows,
    checklist_doc_status, code_for_task, doc_categories,
)
from src.reports import pdf_report, xlsx_report


def test_structure_matches_pdf_sections():
    assert len(SPECIFICATIONS)==13
    assert list(BY_CODE)==['1.1','1.2','1.3'] + [f'2.{n}' for n in range(1,11)]
    assert [x['name'] for x in SPECIFICATIONS[:3]] == [
        'Matrícula','Proprietário do Empreendimento','Contratos e Consultas']
    assert BY_CODE['2.6']['fields'][0][0]=='audiencia_publica'
    assert BY_CODE['2.1']['fields'][0][0]=='retificacao'
    assert set(('Matrícula Atualizada','CND','Projeto Aprovado')).issubset(BY_CODE['2.7']['docs'])
    assert BY_CODE['2.10']['name']=='Habite-se'


def test_workflow_model_has_atomic_details_and_execution():
    rows=make_template_rows(date(2026,11,16),DEFAULT_SECTION_NAMES)
    assert len(rows)==13
    assert {r['stage_name'] for r in rows}==set(DEFAULT_SECTION_NAMES)
    assert all(r['template_code'] in BY_CODE for r in rows)
    assert all(len(r['checklist'])>0 and len(r['execution'])==2 for r in rows)
    assert rows[0]['title']=='1.1 Matrícula'
    assert rows[-1]['title']=='2.10 Habite-se'


def test_old_model_tasks_remain_separate():
    rows=make_template_rows(date(2026,11,16),['Execução'])
    assert rows==[]
    assert code_for_task({'title':'Projeto preventivo'}) is None
    assert code_for_task({'title':'Alterei o nome'}, {'template_code':'2.4'})=='2.4'


def test_requirements_and_category_list():
    assert checklist_doc_status(BY_CODE['2.2'],[{'category':'Orçamento'},{'category':'Nota Fiscal'}])==[
        ('Orçamento',True),('Mapa',False),('Nota Fiscal',True)]
    assert set(('Planilha','Matrícula','Contrato Social','Nota Fiscal','CND')).issubset(doc_categories())


def test_migration_rls_and_atomic_rpc():
    sql=Path('supabase/migrations/20261116_projeto_x.sql').read_text(encoding='utf-8')
    assert 'enable row level security' in sql.lower()
    assert 'to authenticated' in sql
    assert 'public.is_member(project_id)' in sql
    assert 'public.can_edit(project_id)' in sql
    assert 'insert into public.task_details' in sql
    assert 'insert into public.execution_milestones' in sql
    assert 'create or replace function private.create_project_workflow_impl' in sql
    assert 'v_owner uuid := auth.uid()' in sql
    assert 'service_role' not in sql


def test_exports_projeto_x_include_additional_tabs():
    project={'id':'p1','title':'Projeto X - Exemplo','client_name':'Exemplo','location':'Itajaí'}
    stage=[{'id':'s','name':'Projetos (PROJETO X)','sort_order':0}]
    tasks=[{'id':'t','title':'2.2 Arquitetônico','stage_id':'s','description':'',
          'status':'A fazer','priority':'Normal','start_date':'2026-11-16','due_date':'2026-11-30',
          'percent_done':25,'planned_cost':1500}]
    details={'t':{'task_id':'t','template_code':'2.2','data':{'profissional':'Técnico Exemplo'}}}
    m=[{'task_id':'t','title':'Elaboração','start_date':'2026-11-16','due_date':'2026-11-25',
        'status':'Em andamento','percent_done':25}]
    xlsx=xlsx_report(project,stage,tasks,[],[],detail_map=details,milestones=m)
    with ZipFile(BytesIO(xlsx)) as f:
        xml=f.read('xl/workbook.xml').decode('utf-8')
        assert 'Fichas PROJETO X' in xml
        assert 'Atividades' in xml
    pdf=pdf_report(project,stage,tasks,[],[],detail_map=details,milestones=m)
    assert pdf.startswith(b'%PDF')
