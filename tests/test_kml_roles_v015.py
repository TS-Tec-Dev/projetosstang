from pathlib import Path
import pytest
from src.kml_map import read_kml_geometries
from src.db import ALLOWED_EXTENSIONS

BASE=Path(__file__).resolve().parents[1]


def test_kml_point_polygon_line():
    raw=b'''<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>
    <Placemark><Point><coordinates>-48.6,-26.9,12</coordinates></Point></Placemark>
    <Placemark><LineString><coordinates>-48.6,-26.9 -48.61,-26.91</coordinates></LineString></Placemark>
    <Placemark><Polygon><outerBoundaryIs><LinearRing><coordinates>-48.6,-26.9 -48.61,-26.9 -48.61,-26.91 -48.6,-26.9</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>
    </Document></kml>'''
    g=read_kml_geometries(raw)
    assert len(g['points'])==1 and len(g['paths'])==1 and len(g['polygons'])==1
    assert g['points'][0]==[-48.6,-26.9]


def test_kml_does_not_expand_xml_entities():
    raw=b'<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><kml><name>&xxe;</name></kml>'
    with pytest.raises(Exception):read_kml_geometries(raw)


def test_kml_invalid_coords_are_skipped_and_upload_extension_allowed():
    data=b'<kml><Placemark><Point><coordinates>999,999</coordinates></Point></Placemark></kml>'
    assert not read_kml_geometries(data)['all']
    assert '.kml' in ALLOWED_EXTENSIONS


def test_security_role_migration_and_ui_permissions():
    sql=(BASE/'supabase/migrations/20261116_global_roles_kml.sql').read_text()
    source=(BASE/'app.py').read_text()
    assert "platform_role IN ('admin','standard','viewer')" in sql
    assert "public.my_platform_role()='admin'" in sql
    assert "public.my_platform_role() IN ('admin','standard')" in sql
    assert "public.can_edit(project_id) AND author_id=auth.uid()" in sql
    assert 'DISABLE ROW LEVEL SECURITY' not in sql.upper()
    assert 'NAV = ["Dashboard", "Etapas"' in source
    assert "can_edit=myrole in ('admin','standard')" in source
    assert 'add_missing_workflow_steps' in sql
    assert 'location_kml_panel' in (BASE/'src/workflow_ui.py').read_text()
    assert 'PRIMEIRO_ADMINISTRADOR.sql' in (BASE/'README.md').read_text()
