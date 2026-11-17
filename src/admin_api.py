"""API de usuários: envia o JWT do usuário, nunca a service_role."""
from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _http_message(code: int, data: bytes) -> str:
    """Apresenta código HTTP e motivo, inclusive o payload padrão da gateway.

    Respostas como {"code":401,"message":"Invalid JWT"} não têm a chave
    'error'; a v0.1.6 escondia esses erros de configuração.
    """
    try:
        body = json.loads(data.decode('utf-8', 'replace'))
    except (ValueError, UnicodeDecodeError):
        body = {}
    if not isinstance(body, dict):
        body = {}
    reason = str(body.get('error_description') or body.get('message') or body.get('error') or '').strip()
    reason = reason[:220] if reason else 'A função retornou um erro sem detalhes.'
    prefix = f'Edge Function admin-users: HTTP {code} — {reason}'
    if code == 401:
        return prefix + (' Verifique a opção Verify JWT with legacy secret e publique novamente a função com --no-verify-jwt; a função valida o usuário internamente.'
                         if 'jwt' in reason.lower() or 'authorization' in reason.lower() else
                         ' Entre novamente com uma conta de administrador e confira o token da sessão.')
    if code == 404:
        return prefix + ' Confira se admin-users foi publicada no projeto Supabase correto.'
    if code == 403:
        return prefix + ' Confira se sua conta tem o perfil Administrador ativo no Supabase.'
    if code in (500, 502, 503):
        return prefix + ' Consulte Edge Functions > admin-users > Logs e as variáveis de ambiente da função.'
    return prefix


def admin_users(client, url: str, public_key: str, payload: dict) -> dict:
    session = client.auth.get_session()
    if not session or not session.access_token:
        raise RuntimeError('Sessão expirada. Entre novamente como administrador.')
    endpoint = url.rstrip('/') + '/functions/v1/admin-users'
    req = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
        method='POST',
        headers={
            'Authorization': 'Bearer ' + session.access_token,
            'apikey': public_key,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        },
    )
    try:
        with urlopen(req, timeout=25) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(_http_message(exc.code, exc.read())) from None
    except URLError as exc:
        raise RuntimeError('Falha de rede/DNS ao acessar admin-users. Confira SUPABASE_URL e o deploy da função.') from exc
    if not isinstance(data, dict):
        raise RuntimeError('Resposta inválida da Edge Function (era esperado JSON).')
    if data.get('error'):
        raise RuntimeError(str(data['error']))
    return data


def admin_users_health(url: str, public_key: str) -> dict:
    """Verifica somente se a função publicada é a versão esperada. Não usa credenciais administrativas."""
    endpoint = url.rstrip('/') + '/functions/v1/admin-users'
    req = Request(endpoint, method='GET', headers={'apikey': public_key, 'Accept': 'application/json'})
    try:
        with urlopen(req, timeout=12) as response:
            data = json.load(response)
    except HTTPError as exc:
        raise RuntimeError(_http_message(exc.code, exc.read())) from None
    except URLError as exc:
        raise RuntimeError('Não foi possível acessar a URL da função; confira DNS, projeto e conexão.') from exc
    if not isinstance(data, dict) or data.get('function') != 'admin-users':
        raise RuntimeError('A URL não retornou o diagnóstico esperado da função admin-users v0.1.7.')
    return data
