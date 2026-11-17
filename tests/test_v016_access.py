from pathlib import Path
import importlib
import sys
import types
from datetime import date, datetime, timezone

ROOT=Path(__file__).resolve().parents[1]


def test_login_admin_and_no_public_signup():
    app=(ROOT/'app.py').read_text()
    assert 'Criar conta' not in app
    assert 'auth.sign_up' not in app
    assert "st.button('⚙ Administrar usuários'" in app
    assert "access.get('active')" in app
    assert "page=='Administrar usuários'" in app


def test_sidebar_enterprise_and_contrast():
    app=(ROOT/'app.py').read_text()
    css=(ROOT/'src/ui.py').read_text()
    assert 'co-active-enterprise' in app
    assert 'co-active-enterprise' in css
    assert 'opacity:1!important' in css
    assert '-webkit-text-fill-color:#153446!important' in css


def test_admin_task_edit_and_delete():
    app=(ROOT/'app.py').read_text()
    stages=(ROOT/'src/workflow_ui.py').read_text()
    sql=(ROOT/'supabase/migrations/20261116_admin_users_expiry_tasks.sql').read_text()
    assert 'disabled=not is_admin' in app
    assert "show_checklist(project_id,task,is_admin)" in app
    assert "execution_detail(current_client(),project_id,task,is_admin)" in app
    assert "if is_admin:" in stages
    assert "'admin_delete_workflow_task'" in stages
    assert 'Confirmo a exclusão definitiva' in stages
    assert 'USING (public.is_owner(project_id))' in sql
    assert 'DELETE FROM public.tasks WHERE id=p_task_id;' in sql


def test_expiry_rls_and_privileged_edge():
    sql=(ROOT/'supabase/migrations/20261116_admin_users_expiry_tasks.sql').read_text()
    edge=(ROOT/'supabase/functions/admin-users/index.ts').read_text()
    app=(ROOT/'app.py').read_text()
    assert 'account_expires_at timestamptz' in sql
    assert 'public.account_is_active()' in sql
    assert 'my_account_access()' in sql
    assert 'public.is_member(uuid)' in sql
    assert 'DISABLE ROW LEVEL SECURITY' not in sql.upper()
    assert "access?.role !== 'admin'" in edge
    assert "auth.getUser(match[1])" in edge
    assert 'auth.admin.createUser' in edge
    assert 'SUPABASE_SERVICE_ROLE_KEY' in edge
    assert 'SUPABASE_SERVICE_ROLE_KEY' not in app


def test_expires_at_ends_sao_paulo_day(monkeypatch):
    monkeypatch.setitem(sys.modules,'streamlit',types.ModuleType('streamlit'))
    sys.modules.pop('src.admin_ui',None)
    module=importlib.import_module('src.admin_ui')
    moment=datetime.fromisoformat(module.end_of_day_iso(date(2026,11,16)))
    assert moment.astimezone(module.ZONE).date()==date(2026,11,16)
    assert moment.astimezone(module.ZONE).hour==23
    assert module.local_expiry_day('2026-11-17T02:59:59+00:00')==date(2026,11,16)
    assert moment.utcoffset()==timezone.utc.utcoffset(moment)
