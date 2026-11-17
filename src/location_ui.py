"""Seção 1.0: localização em KML, visualização por satélite e exclusão administrativa."""
from __future__ import annotations
from collections import Counter
from html import escape

import streamlit as st
from src.db import BUCKET, remove_document, signed_file_url, upload_document
from src.kml_map import read_kml_geometries, map_for_kml, MAX_KML_PREVIEW_BYTES


def location_kml_panel(sb, project_id, tasks, documents, can_edit, user_id, is_admin=False):
    st.markdown('#### 1.0 Localização do empreendimento · Google Earth')
    st.caption(
        'Anexe o KML, visualize seu perímetro sobre imagens de satélite e baixe o original '
        'para abrir no Google Earth. O mapa utiliza imagens Esri e requer internet.'
    )
    matricula = next(
        (t for t in tasks if str(t.get('title', '')).strip().startswith('1.1 ')), None
    )
    if not matricula:
        st.warning('Não foi localizada a etapa 1.1 Matrícula para vincular o KML.')
        return

    related = [
        d for d in documents
        if d.get('task_id') == matricula['id']
        and (d.get('category') == 'Localização KML'
             or str(d.get('filename', '')).lower().endswith('.kml'))
    ]

    if can_edit:
        with st.form('kml_upload_form', clear_on_submit=True):
            file = st.file_uploader(
                'Anexar KML do Google Earth', type=['kml'],
                help='Arquivo .kml com limite de 10 MB. KMZ não é compatível nesta versão.',
            )
            submit = st.form_submit_button('Salvar localização KML', type='primary')
        if submit:
            if not file:
                st.warning('Selecione um arquivo KML.')
            else:
                try:
                    raw = file.getvalue()
                    if not raw or len(raw) > MAX_KML_PREVIEW_BYTES:
                        raise ValueError('Arquivo vazio ou maior que 10 MB.')
                    # XML protegido; nenhum conteúdo remoto do KML é executado.
                    read_kml_geometries(raw)
                    # Bloqueio simples para evitar novos envios acidentais repetidos.
                    duplicate = any(
                        str(d.get('filename', '')).casefold() == file.name.casefold()
                        and int(d.get('size_bytes') or 0) == len(raw)
                        for d in related
                    )
                    if duplicate:
                        st.warning(
                            'Um KML com o mesmo nome e tamanho já está cadastrado. '
                            'Se quiser substituí-lo, exclua o anterior primeiro.'
                        )
                    else:
                        upload_document(sb, project_id, matricula['id'], user_id, file, 'Localização KML')
                        st.success('KML anexado ao empreendimento.')
                        st.rerun()
                except Exception as exc:
                    st.error(f'Não foi possível anexar KML: {exc}')

    st.caption('Visualizador KML 0.1.9 · Mapa de satélite Esri · Exclusão restrita ao administrador')

    if not related:
        st.info('Nenhum KML cadastrado. Você poderá anexá-lo aqui quando estiver disponível.')
        return

    repeated = Counter(str(d.get('filename', '')).casefold() for d in related)
    for i, doc in enumerate(related, start=1):
        doc_id = str(doc['id'])
        name = str(doc.get('filename') or 'localizacao.kml')
        with st.container(border=True):
            title_col, buttons_col = st.columns([3, 2], vertical_alignment='center')
            with title_col:
                st.markdown('**' + escape(name) + '**')
                extra = ' · registro ' + str(i) if repeated[name.casefold()] > 1 else ''
                st.caption(
                    f"Arquivo Google Earth · {float(doc.get('size_bytes') or 0)/1024:.1f} KB"
                    + extra
                )
            with buttons_col:
                if is_admin:
                    download_col, delete_col = st.columns([2, 1], gap='small')
                else:
                    download_col = st.container()
                    delete_col = None
                with download_col:
                    try:
                        url = signed_file_url(sb, doc['storage_path'])
                        if url:
                            st.link_button('Baixar / abrir KML', url, use_container_width=True)
                        else:
                            st.warning('Link temporário não disponível.')
                    except Exception as exc:
                        st.error(f'Link temporário indisponível: {exc}')
                if delete_col is not None:
                    with delete_col:
                        if st.button('Excluir KML', key=f'kml_delete_{doc_id}', use_container_width=True):
                            st.session_state['kml_delete_confirm'] = doc_id
                            st.rerun()

            if is_admin and st.session_state.get('kml_delete_confirm') == doc_id:
                st.warning(
                    f'Excluir definitivamente “{name}”? Esta ação remove o anexo '
                    'da matrícula e do armazenamento Supabase. Os demais KMLs serão preservados.'
                )
                confirmation = st.checkbox(
                    'Confirmo a exclusão deste KML.', key=f'kml_confirm_{doc_id}'
                )
                yes_col, no_col = st.columns([1, 1])
                with yes_col:
                    if st.button(
                        'Confirmar exclusão', key=f'kml_confirm_delete_{doc_id}',
                        disabled=not confirmation, type='primary',
                    ):
                        try:
                            # O banco exige perfil admin para apagar KMLs.
                            # remove_document verifica também a exclusão do registro.
                            remove_document(sb, doc)
                            st.session_state.pop('kml_delete_confirm', None)
                            if st.session_state.get('kml_active_view') == doc_id:
                                st.session_state.pop('kml_active_view', None)
                            st.success('KML excluído com sucesso.')
                            st.rerun()
                        except Exception as exc:
                            st.error(f'Não foi possível excluir o arquivo: {exc}')
                with no_col:
                    if st.button('Cancelar', key=f'kml_cancel_delete_{doc_id}'):
                        st.session_state.pop('kml_delete_confirm', None)
                        st.rerun()

            if st.button('Observar no mapa', key=f'kml_view_{doc_id}'):
                st.session_state['kml_active_view'] = (
                    None if st.session_state.get('kml_active_view') == doc_id else doc_id
                )
            if st.session_state.get('kml_active_view') == doc_id:
                try:
                    data = sb.storage.from_(BUCKET).download(doc['storage_path'])
                    geometry = read_kml_geometries(bytes(data))
                    if not geometry['all']:
                        st.warning(
                            'Este KML não contém pontos, linhas ou polígonos '
                            'compatíveis com o visualizador. Abra o original no Google Earth.'
                        )
                    else:
                        map_view = map_for_kml(geometry)
                        # Folium/Leaflet fornece imagens satelitais e zoom sem token Mapbox.
                        st.components.v1.html(
                            map_view.get_root().render(), height=540, scrolling=False
                        )
                        st.caption(
                            f"{len(geometry['points'])} ponto(s) · "
                            f"{len(geometry['paths'])} linha(s) · "
                            f"{len(geometry['polygons'])} polígono(s) · "
                            'Satélite: Esri World Imagery'
                        )
                except Exception as exc:
                    st.error(f'Não foi possível exibir o mapa: {exc}')
