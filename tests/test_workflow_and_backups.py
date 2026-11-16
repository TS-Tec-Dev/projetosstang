from datetime import date
from io import BytesIO
import json
import zipfile
import pytest

from src.workflow import SPECIFICATIONS, DEFAULT_SECTION_NAMES, make_template_rows, BY_CODE, doc_categories
from src.backups import make_backup, inspect_backup
from src.ui import icon, metric_card


def test_default_model_is_only_pdf_structure_without_project_x_label():
    tasks=make_template_rows(date(2026,11,16),DEFAULT_SECTION_NAMES)
    assert len(tasks)==13
    assert DEFAULT_SECTION_NAMES==['Documentação','Projetos']
    assert [x['template_code'] for x in tasks]==['1.1','1.2','1.3']+[f'2.{n}' for n in range(1,11)]
    assert set(t['stage_name'] for t in tasks)==set(DEFAULT_SECTION_NAMES)
    assert all('PROJETO X' not in t['stage_name']+' '+t['description'] for t in tasks)
    assert 'Matrícula Atualizada' in BY_CODE['2.7']['docs']
    assert BY_CODE['2.6']['fields'][0][0]=='audiencia_publica'
    assert BY_CODE['2.8']['fields'][0][0]=='jurisdicao'
    assert set(['.xlsx','.pdf']) != set(doc_categories())


def test_custom_svg_icons_are_valid_and_escape_values():
    assert '<svg' in icon('backup') and '<path' in icon('backup')
    html=metric_card('<ALERTA>', '<script>', 'alert')
    assert '&lt;ALERTA&gt;' in html and '&lt;script&gt;' in html
    assert '<script>' not in html


class _Response:
    def __init__(self,data):self.data=data

class _Query:
    def __init__(self,rows): self.rows=rows
    def select(self,*a):return self
    def order(self,*a):return self
    def eq(self,*a):return self
    def range(self,a,b):
        self.start,self.end=a,b;return self
    def execute(self):return _Response(self.rows[self.start:self.end+1])

class _Storage:
    def from_(self,*a):return self
    def download(self,*a):return b'Test PDF bytes\n'

class _Client:
    def __init__(self):
        self._data={'stages':[{'id':'stage1','project_id':'p1','name':'Documentação','sort_order':0}],
          'tasks':[{'id':'t1','project_id':'p1','stage_id':'stage1','title':'1.1 Matrícula','sort_order':0}],
          'documents':[{'id':'d1','task_id':'t1','project_id':'p1','storage_path':'p1/t1/a.pdf',
                       'category':'Matrícula','filename':'matricula.pdf','size_bytes':15,
                       'content_type':'application/pdf'}]}
        self.storage=_Storage()
    def table(self,table):return _Query(self._data.get(table,[]))
    def rpc(self,*args,**kwargs):return self
    def execute(self):return _Response('admin')


def test_complete_backup_carries_private_bytes_and_manifest():
    blob=make_backup(_Client(),[{'id':'p1','title':'Implantação','owner_id':'u1'}],True)
    data=inspect_backup(blob)
    assert data['files_included'] and len(data['projects'])==1
    with zipfile.ZipFile(BytesIO(blob)) as z:
        doc=data['projects'][0]['tables']['documents'][0]
        assert z.read(doc['backup_blob'])==b'Test PDF bytes\n'
    assert data['projects'][0]['tables']['tasks'][0]['title']=='1.1 Matrícula'


def test_metadata_only_backups_are_not_mislabeled_as_full():
    blob=make_backup(_Client(),[{'id':'p1','title':'Implantação'}],False)
    data=inspect_backup(blob)
    assert not data['files_included']
    assert data['projects'][0]['tables']['documents'][0]['backup_blob'] is None


def test_reject_foreign_zip():
    out=BytesIO()
    with zipfile.ZipFile(out,'w') as z:z.writestr('other.txt','oops')
    with pytest.raises(ValueError,match='data.json'):
        inspect_backup(out.getvalue())
