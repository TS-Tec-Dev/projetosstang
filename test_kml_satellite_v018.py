from pathlib import Path
from src.kml_map import map_for_kml, read_kml_geometries

ROOT = Path(__file__).resolve().parents[1]


def test_satellite_map_and_overlay():
    raw = b'''<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>
    <Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>
    -48.65,-26.90 -48.64,-26.90 -48.64,-26.91 -48.65,-26.90
    </coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
    </Document></kml>'''
    geo = read_kml_geometries(raw)
    m = map_for_kml(geo)
    html = m.get_root().render()
    assert 'World_Imagery' in html
    assert 'Sat\\u00e9lite (Esri)' in html or 'Satélite (Esri)' in html
    assert 'Polygon' in html or 'polygon' in html
    assert '[-26.9, -48.65]' in html or '[-26.905' in html
    assert 'OpenStreetMap' in html
    assert 'Esri' in html


def test_admin_only_kml_delete_and_ui():
    sql = (ROOT / 'supabase/migrations/20261117_kml_satellite_admin_delete.sql').read_text()
    ui = (ROOT / 'src/location_ui.py').read_text()
    workflow = (ROOT / 'src/workflow_ui.py').read_text()
    assert "category <> 'Localização KML'" in sql
    assert "right(lower(name), 4) <> '.kml'" in sql
    assert "public.my_platform_role() = 'admin'" in sql
    assert 'DISABLE ROW LEVEL SECURITY' not in sql.upper()
    assert 'if is_admin:' in ui
    assert "'Excluir KML'" in ui
    assert "'Confirmar exclusão'" in ui
    assert 'remove_document(sb, doc)' in ui
    assert 'is_admin=is_admin' in workflow


def test_duplicate_kml_block_and_file_entry_id():
    ui = (ROOT/'src/location_ui.py').read_text()
    assert 'size_bytes' in ui and 'duplicate' in ui
    assert "f'kml_delete_{doc_id}'" in ui
    assert "'kml_active_view'" in ui


def test_package_depends_on_folium():
    requirements = (ROOT/'requirements.txt').read_text()
    assert 'folium>=' in requirements
    assert 'streamlit' in requirements


def test_delete_document_preserves_storage_if_rls_denies():
    """Garante que uma exclusão RLS sem linhas não apaga o objeto."""
    import ast
    from types import SimpleNamespace
    source = (ROOT / 'src/db.py').read_text()
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'remove_document')
    namespace = {'BUCKET': 'project-files'}
    exec(compile(ast.Module(body=[function], type_ignores=[]), '<test>', 'exec'), namespace)
    remove_document = namespace['remove_document']
    events = []

    class Query:
        def delete(self):
            events.append('delete')
            return self

        def eq(self, field, value):
            assert field == 'id' and value == 'doc-1'
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    class Storage:
        def from_(self, name):
            events.append('storage_from')
            return self

        def remove(self, paths):
            events.append('storage_remove')

    class Client:
        storage = Storage()

        def table(self, name):
            assert name == 'documents'
            return Query()

    import pytest
    with pytest.raises(PermissionError):
        remove_document(Client(), {'id': 'doc-1', 'storage_path': 'path.kml'})
    assert events == ['delete']


def test_delete_document_removes_exact_one_object():
    import ast
    from types import SimpleNamespace
    source = (ROOT / 'src/db.py').read_text()
    fn = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'remove_document')
    namespace = {'BUCKET': 'project-files'}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<test>', 'exec'), namespace)
    events = []

    class Query:
        def delete(self):
            return self

        def eq(self, field, value):
            assert (field, value) == ('id', 'doc-1')
            return self

        def execute(self):
            events.append('database_deleted')
            return SimpleNamespace(data=[{'id': 'doc-1'}])

    class Storage:
        def from_(self, bucket):
            assert bucket == 'project-files'
            return self

        def remove(self, paths):
            events.append(('removed', paths))

    class Client:
        storage = Storage()

        def table(self, table):
            assert table == 'documents'
            return Query()

    namespace['remove_document'](Client(), {'id': 'doc-1', 'storage_path': 'project/task/file.kml'})
    assert events == ['database_deleted', ('removed', ['project/task/file.kml'])]
