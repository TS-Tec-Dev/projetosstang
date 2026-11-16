"""Página Backups: exportar, restaurar e limpar projetos sob autorização do proprietário."""
from datetime import datetime
import streamlit as st
from src.backups import make_backup, inspect_backup, restore_backup, purge_project


def backup_page(sb, projects, user_id):
    st.title('Backups e recuperação')
    st.caption('Proteja dados e anexos antes de atualizar o aplicativo. O ZIP é gerado nesta sessão e baixado para seu computador; não fica salvo no GitHub.')
    tab_save,tab_restore,tab_clear=st.tabs(['Exportar backup','Restaurar backup','Excluir projetos antigos'])
    with tab_save:
        st.markdown('#### Criar cópia de segurança')
        options={p['id']:p for p in projects}
        selected=st.multiselect('Projetos para incluir',list(options.keys()),
                                default=list(options.keys())[:1],format_func=lambda id:options[id]['title'])
        include_docs=st.checkbox('Incluir documentos originais (PDF, imagens e planilhas)',value=True)
        st.info('Recomendado: sempre incluir os anexos. Backups sem anexos permitem conferência dos dados, mas não restauração integral.')
        if st.button('Preparar backup ZIP',type='primary',disabled=not bool(selected)):
            try:
                with st.spinner('Preparando arquivos e registros...'):
                    raw=make_backup(sb,[options[pid] for pid in selected],include_docs)
                st.session_state['backup_bytes']=raw
                st.session_state['backup_selection']=selected.copy()
                st.success(f'Cópia preparada: {len(raw)/1024/1024:.1f} MB, {len(selected)} projeto(s).')
            except Exception as exc:st.error(f'Falha ao gerar backup: {exc}')
        if st.session_state.get('backup_bytes'):
            st.download_button('Baixar backup completo (.zip)',data=st.session_state['backup_bytes'],
                file_name=f'cronogramaobras_backup_{datetime.now():%Y%m%d_%H%M}.zip',
                mime='application/zip',use_container_width=True)
            st.caption('Guarde o ZIP em local seguro. Ele contém dados internos e arquivos do empreendimento.')
    with tab_restore:
        st.markdown('#### Restaurar como novo projeto')
        st.caption('A restauração não substitui nem altera os projetos existentes; cria novas cópias com IDs próprios. Membros antigos não são reativados automaticamente.')
        uploaded=st.file_uploader('Selecionar backup ZIP',type=['zip'],key='backup_upload')
        if uploaded:
            try:
                raw=uploaded.getvalue()
                manifest=inspect_backup(raw)
                items=manifest['projects']
                st.success(f'Backup válido · {len(items)} projeto(s) · gerado em {manifest.get("exported_at", "-")[:19]}')
                if not manifest.get('files_included'):
                    st.warning('Este arquivo não contém os anexos originais. Faça novo backup completo para restaurar.')
                selected=st.multiselect('Projetos a restaurar',list(range(len(items))),
                    default=list(range(len(items))),format_func=lambda i:items[i]['project'].get('title','Projeto'))
                confirm=st.checkbox('Confirmo a criação de novas cópias dos projetos selecionados',key='restore_confirm')
                if st.button('Restaurar projetos selecionados',type='primary',
                    disabled=not (selected and confirm and manifest.get('files_included'))):
                    try:
                        with st.spinner('Recriando tarefas, anexos e cronogramas...'):
                            new_ids=restore_backup(sb,raw,user_id,selected)
                        st.session_state.pop('backup_bytes',None)
                        st.success(f'Restauração concluída: {len(new_ids)} projeto(s).')
                        st.info('Os antigos membros da equipe não são restaurados automaticamente: adicione-os na aba Equipe.')
                        st.rerun()
                    except Exception as exc:st.error(f'Falha durante a restauração: {exc}')
            except Exception as exc:st.error(f'Arquivo não reconhecido: {exc}')
    with tab_clear:
        st.markdown('#### Limpeza de projetos antigos')
        st.warning('A exclusão é permanente no Supabase, inclusive os anexos. Faça e baixe um backup integral ANTES desta operação.')
        owned={p['id']:p for p in projects if p.get('owner_id')==user_id}
        if not owned:
            st.info('Não há projetos de sua propriedade disponíveis para exclusão.')
            return
        ids=st.multiselect('Quais projetos excluir?',list(owned.keys()),format_func=lambda pid:owned[pid]['title'],key='projects_to_delete')
        phrase=st.text_input('Digite EXCLUIR para autorizar',key='delete_phrase')
        confirm=st.checkbox('Confirmo que já baixei e conferi o backup',key='delete_confirm')
        allow=bool(ids) and phrase=='EXCLUIR' and confirm
        if st.button('Excluir projetos selecionados definitivamente',disabled=not allow):
            succeeded=[]
            for pid in ids:
                try:
                    purge_project(sb,pid,user_id)
                    succeeded.append(pid)
                except Exception as exc:
                    st.error(f'Falha ao excluir {owned[pid]["title"]}: {exc}')
            if succeeded:
                st.session_state.pop('project_id',None)
                st.session_state.pop('backup_bytes',None)
                st.success(f'{len(succeeded)} projeto(s) excluído(s) do banco. Reinicie ou atualize a página.')
                st.rerun()
