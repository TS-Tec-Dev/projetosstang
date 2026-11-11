from datetime import date
from io import BytesIO
from zipfile import ZipFile

from src.reports import pdf_report, xlsx_report, brief_stats

PROJECT={'title':'Exemplo de Implantação','client_name':'Empresa Modelo','location':'Itajaí/SC'}
STAGES=[{'id':'stage1','name':'Prefeitura'}]
TASKS=[{'id':'task1','stage_id':'stage1','title':'Projeto arquitetônico','description':'Memorial e planta',
        'responsible_id':None,'status':'A fazer','priority':'Normal','start_date':'2026-11-11',
        'due_date':'2026-11-25','percent_done':10,'planned_cost':4500}]
FINANCE=[{'task_id':'task1','description':'Projeto','planned_date':'2026-11-25',
          'planned_amount':4500,'paid_amount':0,'paid_date':None,'status':'Previsto'}]
DOCS=[{'category':'Orçamento','filename':'proposta.xlsx','task_id':'task1',
        'size_bytes':1234,'uploaded_at':'2026-11-11T10:00:00'}]


def test_stats():
    result=brief_stats(TASKS,FINANCE)
    assert result['total']==1 and result['planned']==4500 and result['paid']==0


def test_pdf_report_is_valid():
    output=pdf_report(PROJECT,STAGES,TASKS,FINANCE,DOCS)
    assert output.startswith(b'%PDF')
    assert len(output)>2000


def test_xlsx_report_has_four_sheets():
    output=xlsx_report(PROJECT,STAGES,TASKS,FINANCE,DOCS)
    with ZipFile(BytesIO(output)) as z:
        assert 'xl/workbook.xml' in z.namelist()
        assert len([x for x in z.namelist() if x.startswith('xl/worksheets/sheet')])==4
