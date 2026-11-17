from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_project_select_policy_allows_owner_and_members():
    sql = (ROOT / "supabase/schema.sql").read_text(encoding="utf-8").lower()
    policy = sql.split('create policy "project read members"', 1)[1].split('drop policy if exists "project create self"', 1)[0]
    assert 'owner_id=(select auth.uid())' in policy
    assert 'public.is_member(id)' in policy


def test_fix_migration_keeps_rls_enabled_and_restricts_insert_owner():
    sql = (ROOT / "supabase/migrations/20261111_fix_projects_rls.sql").read_text(encoding="utf-8").lower()
    assert 'disable row level security' not in sql
    assert 'drop table' not in sql
    assert 'with check (owner_id=(select auth.uid()))' in sql
