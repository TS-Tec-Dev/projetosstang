"""Cadastro e gestão de contas por administrador já autenticado."""
from __future__ import annotations
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo
import streamlit as st
from src.admin_api import admin_users, admin_users_health

ZONE = ZoneInfo('America/Sao_Paulo')
ROLE_NAMES = {'admin':'Administrador','standard':'Padrão','viewer':'Visualizador'}


def end_of_day_iso(day: date) -> str:
    """Data-limite inclusiva no fuso de São Paulo, enviada ao banco em UTC."""
    local = datetime.combine(day, time(23, 59, 59, 999999), tzinfo=ZONE)
    return local.astimezone(timezone.utc).isoformat()


def local_expiry_day(value: str | None) -> date:
    if not value:return date.today()
    return datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(ZONE).date()


def admin_panel(sb, url: str, anon_key: str):
    st.title('Administrar usuários')
    st.caption('Somente administradores podem cadastrar usuários e alterar nível, validade ou situação de acesso. '
               'Sem data de vencimento, o acesso é vitalício até ser desativado.')
    try:
        users = admin_users(sb, url, anon_key, {'action': 'list'}).get('users', [])
    except Exception as exc:
        st.error(f'Falha ao consultar usuários: {exc}')
        st.info('Use o diagnóstico abaixo para diferenciar uma função não publicada de um problema de token ou de permissão.')
        if st.button('Testar disponibilidade da Edge Function', key='check_admin_fn'):
            try:
                status = admin_users_health(url, anon_key)
                version = status.get('version') or 'não informada'
                st.success(f"Edge Function online. Versão publicada: {version}. Se a listagem falhar, verifique a permissão Administrador e os logs.")
            except Exception as health_exc:
                st.error(f'Diagnóstico da função: {health_exc}')
        return
    st.metric('Contas cadastradas',len(users))
    st.dataframe([{
        'Nome': u.get('full_name') or '', 'E-mail':u.get('email') or '',
        'Perfil': ROLE_NAMES.get(u.get('platform_role'),u.get('platform_role')),
        'Situação':'Ativo' if u.get('account_enabled') else 'Desativado',
        'Validade':local_expiry_day(u['account_expires_at']).strftime('%d/%m/%Y') if u.get('account_expires_at') else 'Vitalício',
    } for u in users],use_container_width=True,hide_index=True)

    with st.expander('➕ Cadastrar novo usuário',expanded=not bool(users)):
        mode=st.radio('Validade de acesso',['Vitalício','Com vencimento'],horizontal=True,key='managed_new_mode')
        with st.form('create_managed_user',clear_on_submit=False):
            name=st.text_input('Nome completo *',key='managed_new_name')
            email=st.text_input('E-mail de acesso *',key='managed_new_email')
            password=st.text_input('Senha inicial (mínimo 10 caracteres) *',type='password',key='managed_new_password')
            role=st.selectbox('Perfil',list(ROLE_NAMES),index=2,format_func=lambda x:ROLE_NAMES[x],key='managed_new_role')
            expiry=st.date_input('Data final de acesso',value=date.today(),min_value=date.today(),disabled=mode=='Vitalício',key='managed_new_expiry',format='DD/MM/YYYY')
            submitted=st.form_submit_button('Criar usuário',type='primary',use_container_width=True)
        if submitted:
            if len(password) < 10 or len(name.strip()) < 3 or '@' not in email:
                st.warning('Confira nome, e-mail e senha (mínimo 10 caracteres).')
            else:
                try:
                    res=admin_users(sb,url,anon_key,{
                        'action':'create','full_name':name.strip(),'email':email.strip().lower(),
                        'password':password,'role':role,
                        'expires_at':None if mode=='Vitalício' else end_of_day_iso(expiry),
                    })
                    st.success(res.get('message','Conta criada com sucesso.'))
                    st.rerun()
                except Exception as exc:st.error(f'Erro ao criar usuário: {exc}')

    if users:
        with st.expander('✎ Alterar perfil, validade ou acesso',expanded=False):
            selected=st.selectbox('Usuário a administrar',users,
                format_func=lambda u:f"{u.get('full_name','')} · {u.get('email','')}",key='managed_select_user')
            mode=st.radio('Prazo de acesso',['Vitalício','Com vencimento'],horizontal=True,
                index=0 if selected.get('account_expires_at') is None else 1,key=f"managed_existing_mode_{selected['id']}")
            with st.form(f"update_managed_user_{selected['id']}"):
                name=st.text_input('Nome',value=selected.get('full_name') or '',key=f"managed_name_{selected['id']}")
                role=st.selectbox('Nível',list(ROLE_NAMES),
                    index=list(ROLE_NAMES).index(selected.get('platform_role') or 'viewer'),
                    format_func=lambda x:ROLE_NAMES[x],key=f"managed_role_{selected['id']}")
                enabled=st.checkbox('Usuário habilitado',value=bool(selected.get('account_enabled',True)),key=f"managed_enabled_{selected['id']}")
                expiry=st.date_input('Válido até (inclusive)',
                    value=local_expiry_day(selected.get('account_expires_at')),
                    disabled=mode=='Vitalício',format='DD/MM/YYYY',key=f"managed_expiry_{selected['id']}")
                st.caption('Desativar bloqueia imediatamente os dados da conta pelas regras RLS. '
                           'Não exclui seu histórico ou documentos.')
                submitted=st.form_submit_button('Salvar alterações de acesso',type='primary')
            if submitted:
                try:
                    result=admin_users(sb,url,anon_key,{
                        'action':'update','id':selected['id'], 'full_name':name.strip(),
                        'role':role,'enabled':enabled,
                        'expires_at':None if mode=='Vitalício' else end_of_day_iso(expiry),
                    })
                    st.success(result.get('message','Acesso atualizado.'))
                    st.rerun()
                except Exception as exc:st.error(f'Erro ao atualizar acesso: {exc}')
