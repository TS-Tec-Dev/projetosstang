"""Chamada ao Edge Function com JWT da sessão (nunca com service_role)."""
from __future__ import annotations
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def admin_users(client, url: str, public_key: str, payload: dict) -> dict:
    session = client.auth.get_session()
    if not session or not session.access_token:
        raise RuntimeError('Sessão expirada. Entre novamente como administrador.')
    endpoint = url.rstrip('/') + '/functions/v1/admin-users'
    req = Request(endpoint, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                  method='POST', headers={
                    'Authorization': 'Bearer ' + session.access_token,
                    'apikey': public_key,
                    'Content-Type': 'application/json',
                  })
    try:
        with urlopen(req, timeout=25) as response:
            data = json.load(response)
    except HTTPError as exc:
        try: message=json.loads(exc.read().decode('utf-8')).get('error')
        except Exception: message='Erro HTTP ' + str(exc.code)
        raise RuntimeError(message or 'Não foi possível acessar a administração') from None
    except URLError as exc:
        raise RuntimeError('Sem conexão com Edge Function. Verifique o deploy admin-users.') from exc
    if 'error' in data:
        raise RuntimeError(str(data['error']))
    return data
