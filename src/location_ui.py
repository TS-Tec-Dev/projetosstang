"""Seção prévia à matrícula para arquivo KML, sem alterar o cadastro da matrícula."""
from __future__ import annotations
from html import escape
from pathlib import Path
from uuid import uuid4

import streamlit as st
from src.db import BUCKET, signed_file_url, upload_document
from src.kml_map import read_kml_geometries, map_for_kml, MAX_KML_PREVIEW_BYTES


def location_kml_panel(sb,project_id,tasks,documents,can_edit,user_id):
    st.markdown('#### 1.0 Localização do empreendimento · Google Earth')
    st.caption('Visualize a localização em mapa, anexe o KML e baixe o arquivo original para abrir no Google Earth. O arquivo fica vinculado à matrícula.')
    matricula=next((t for t in tasks if str(t.get('title','')).strip().startswith('1.1 ')),None)
    if not matricula:
        st.warning('Não foi localizada a etapa 1.1 Matrícula. Adicione as etapas técnicas para vincular o KML.')
        return
    related=[d for d in documents if d.get('task_id')==matricula['id'] and
             (d.get('category')=='Localização KML' or str(d.get('filename','')).lower().endswith('.kml'))]
    if can_edit:
        with st.form('kml_upload_form',clear_on_submit=True):
            file=st.file_uploader('Anexar KML do Google Earth',type=['kml'],help='Arquivo .kml com limite de 10 MB. KMZ não é compatível nesta versão.')
            submit=st.form_submit_button('Salvar localização KML',type='primary')
        if submit:
            if not file:st.warning('Selecione um arquivo KML.')
            else:
                try:
                    raw=file.getvalue()
                    if not raw or len(raw)>MAX_KML_PREVIEW_BYTES:
                        raise ValueError('Arquivo vazio ou maior que 10 MB.')
                    read_kml_geometries(raw)  # XML seguro; algumas sobreposições não têm coordenadas próprias
                    upload_document(sb,project_id,matricula['id'],user_id,file,'Localização KML')
                    st.success('KML anexado ao empreendimento.');st.rerun()
                except Exception as exc:st.error(f'Não foi possível anexar KML: {exc}')
    if not related:
        st.info('Nenhum KML cadastrado. Você poderá anexá-lo aqui quando estiver disponível.')
        return
    for doc in related:
        with st.container(border=True):
            left,right=st.columns([3,2])
            with left:
                st.markdown('**'+escape(doc.get('filename') or 'localizacao.kml')+'**')
                st.caption(f"Arquivo Google Earth · {round(float(doc.get('size_bytes') or 0)/1024,1)} KB")
            with right:
                try:
                    url=signed_file_url(sb,doc['storage_path'])
                    if url:st.link_button('Baixar / abrir KML',url,use_container_width=True)
                except Exception as exc:st.error(f'Link temporário indisponível: {exc}')
            if st.button('Observar no mapa',key='kml_view_'+doc['id']):
                st.session_state['kml_active_view']=None if st.session_state.get('kml_active_view')==doc['id'] else doc['id']
            if st.session_state.get('kml_active_view')==doc['id']:
                try:
                    data=sb.storage.from_(BUCKET).download(doc['storage_path'])
                    geometry=read_kml_geometries(bytes(data))
                    if not geometry['all']:
                        st.warning('Este KML não tem pontos/linhas/polígonos compatíveis com a visualização interna. Baixe e abra no Google Earth.')
                    else:
                        deck=map_for_kml(geometry)
                        st.pydeck_chart(deck,use_container_width=True)
                        st.caption(f"{len(geometry['points'])} ponto(s) · {len(geometry['paths'])} linha(s) · {len(geometry['polygons'])} polígono(s)")
                except Exception as exc:st.error(f'Não foi possível exibir o mapa: {exc}')
