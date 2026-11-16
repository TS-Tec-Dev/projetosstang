from pathlib import Path
import sys
import types
# Os testes de contrato não exigem instalar a biblioteca online do Supabase.
try:
    from supabase import create_client
except ImportError:
    fake = types.ModuleType("supabase")
    fake.create_client = lambda *a, **kw: None
    sys.modules["supabase"] = fake
from src.db import add_project_with_workflow

ROOT = Path(__file__).resolve().parents[1]

class Result:
    data = "aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa"

class RPC:
    def execute(self):
        return Result()

class Client:
    def __init__(self):
        self.name = None
        self.payload = None
    def rpc(self, name, payload):
        self.name = name
        self.payload = payload
        return RPC()

def test_calls_transactional_rpc_without_sending_owner_id():
    client = Client()
    result = add_project_with_workflow(client, "user-id", {"title": "Projeto Novo"}, [{"stage_name": "Prefeitura", "title":"Planta"}])
    assert client.name == "create_project_workflow"
    assert client.payload["p_project"] == {"title": "Projeto Novo"}
    assert "owner_id" not in client.payload["p_project"]
    assert result["id"] == Result.data

def test_private_security_definer_wrapper_privileges():
    sql = (ROOT / "supabase/migrations/20261111_atomic_project_creation.sql").read_text(encoding="utf-8").lower()
    assert "security definer" in sql
    assert "security invoker" in sql
    assert "v_owner uuid := auth.uid()" in sql
    assert "revoke all on function public.create_project_workflow(jsonb,jsonb) from anon" in sql
    assert "insert into public.project_members" in sql
    assert "disable row level security" not in sql
    assert "drop table" not in sql

def test_rpc_has_atomic_stages_and_tasks():
    sql = (ROOT / "supabase/migrations/20261111_atomic_project_creation.sql").read_text(encoding="utf-8")
    assert "insert into public.projects" in sql
    assert "insert into public.stages" in sql
    assert "insert into public.tasks" in sql
