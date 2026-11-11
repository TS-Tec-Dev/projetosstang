from datetime import date
from src.templates import WORKFLOWS, DEFAULT_WORKFLOW, generate_template


def test_default_stages_have_permitting_tasks():
    tasks=generate_template(date(2026,11,11),DEFAULT_WORKFLOW)
    names={t['title'] for t in tasks}
    assert 'Projeto arquitetônico' in names
    assert 'Projeto hidrossanitário' in names
    assert any('PPCI' in x for x in names)
    assert 'LAP - Licença Ambiental Prévia' in names
    assert 'LAI - Licença Ambiental de Instalação' in names
    assert len(tasks) >= 16


def test_roadway_flow_by_choice():
    tasks=generate_template(date(2026,11,11),['Acesso rodovia estadual','Acesso rodovia federal'])
    assert {x['stage_name'] for x in tasks}=={'Acesso rodovia estadual','Acesso rodovia federal'}
    assert all(x['due_date'] >= x['start_date'] for x in tasks)
