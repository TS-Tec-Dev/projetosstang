"""Regressões observadas no Chrome/Streamlit após o deploy da v0.1.6."""
from pathlib import Path
from io import BytesIO
from urllib.error import HTTPError
from urllib.request import Request
import sys
import types

ROOT = Path(__file__).resolve().parents[1]


def test_selector_uses_dark_background_with_white_foreground():
    css = (ROOT / 'src/ui.py').read_text(encoding='utf-8')
    assert 'st-key-active_enterprise_select' in css
    assert 'background-color:#164653!important;' in css
    assert '-webkit-text-fill-color:#ffffff!important;' in css
    assert 'co-active-enterprise' in css
    assert '[data-testid="stSelectboxVirtualDropdown"]' in css
    assert 'background:#ffffff!important; color:#153446' not in css


def test_admin_http_401_surfaces_gateway_message():
    from src.admin_api import _http_message
    msg = _http_message(401, b'{"code":401,"message":"Invalid JWT"}')
    assert 'HTTP 401' in msg
    assert 'Invalid JWT' in msg
    assert '--no-verify-jwt' in msg


def test_admin_http_404_and_500_have_actionable_clues():
    from src.admin_api import _http_message
    assert 'publicada' in _http_message(404, b'{"message":"not found"}')
    assert 'Logs' in _http_message(500, b'{"error":"Function error"}')
    assert 'sem detalhes' in _http_message(502, b'')


def test_admin_api_forwards_user_token_not_server_key(monkeypatch):
    from src import admin_api
    captured = {}

    class Client:
        auth = types.SimpleNamespace(get_session=lambda: types.SimpleNamespace(access_token='JWT-DE-TESTE'))

    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return False
        def read(self):
            return b'{"users":[]}'

    def fake_urlopen(request, timeout):
        captured['request'] = request
        captured['timeout'] = timeout
        return FakeResponse()

    # `json.load` calls read(); we don't make any real HTTP requests.
    monkeypatch.setattr(admin_api, 'urlopen', fake_urlopen)
    data = admin_api.admin_users(Client(), 'https://test.supabase.co/', 'pub-key', {'action':'list'})
    assert data['users'] == []
    assert captured['request'].get_header('Authorization') == 'Bearer JWT-DE-TESTE'
    assert captured['request'].get_header('Apikey') == 'pub-key'
    assert captured['request'].get_method() == 'POST'


def test_edge_function_checks_real_user_and_role_before_admin_client():
    code = (ROOT / 'supabase/functions/admin-users/index.ts').read_text(encoding='utf-8')
    config = (ROOT / 'supabase/config.toml').read_text(encoding='utf-8')
    assert 'verify_jwt = false' in config
    ix_get = code.index('auth.getUser(match[1])')
    ix_role = code.index("access?.role !== 'admin'")
    ix_admin = code.index('createClient(url, serviceKey')
    assert ix_get < ix_role < ix_admin
    assert 'if (!match)' in code
    assert "if (req.method === 'GET') return json({ status: 'online'" in code
