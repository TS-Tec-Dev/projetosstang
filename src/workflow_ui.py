"""Interface do roteiro Cronograma: acompanhamento, fichas e cronograma físico."""
from __future__ import annotations
from datetime import date, timedelta
from html import escape
import pandas as pd
import plotly.express as px
import streamlit as st

from src.db import brl, pretty_date
from src.location_ui import location_kml_panel
from src.workflow import BY_CODE, SPECIFICATIONS, PROJECT_SECTION, DOC_SECTION, code_for_task, checklist_doc_status, make_template_rows, DEFAULT_SECTION_NAMES

OPTIONS = ['A definir', 'Pendente', 'Em andamento', 'Protocolado', 'Aprovado', 'Concluído', 'Não se aplica']


def _date(v, fallback=None):
    try: return date.fromisoformat(str(v)[:10])
    except Exception: return fallback or date.today()


def get_detail_map(sb, project_id: str):
    return {r['task_id']:r for r in (sb.table('task_details').select('*').eq('project_id', project_id).execute().data or [])}


def get_milestones(sb, project_id: str):
    return sb.table('execution_milestones').select('*').eq('project_id',project_id).order('start_date').execute().data or []


def open_task_panel(task: dict, panel: str):
    st.session_state['selected_task_id'] = task['id']
    st.session_state[f"task_panel_{task['id']}"] = panel
    st.session_state['page'] = 'Quadro de tarefas'
    st.rerun()


def overview_plan(sb, project_id, stages, tasks, documents, details_map, entries, milestones, can_edit, user_id, is_admin=False):
    st.subheader('Plano do empreendimento · Cronograma do empreendimento')
    st.caption('Roteiro técnico: 1.1–1.3 (Documentação) e 2.1–2.10 (Projetos). Os prazos são editáveis, não são prazos legais dos órgãos.')
    by_stage = {s['id']:s['name'] for s in stages}
    tagged = []
    for t in tasks:
        code = code_for_task(t, details_map.get(t['id']))
        if code and code in BY_CODE:
            tagged.append((BY_CODE[code], t))
    missing = [s for s in SPECIFICATIONS if s['code'] not in {spec['code'] for spec,_ in tagged}]
    if missing:
        st.info(f'Faltam {len(missing)} item(ns) do roteiro neste projeto. Os itens existentes serão preservados.')
        if is_admin and st.button('Adicionar etapas técnicas faltantes',type='primary'):
            try:
                payload=make_template_rows(date.today(),DEFAULT_SECTION_NAMES)
                result=sb.rpc('add_missing_workflow_steps',{'p_project_id':project_id,'p_tasks':payload}).execute()
                st.success(f'Itens incluídos: {result.data}. Os projetos e documentos anteriores foram mantidos.')
                st.rerun()
            except Exception as exc:
                st.error(f'Não foi possível adicionar etapas. Confira o SQL do Supabase: {exc}')
    if not tagged:
        return
    planned = sum(float(t.get('planned_cost') or 0) for _,t in tagged)
    done = sum(t.get('status') == 'Concluída' for _,t in tagged)
    c1,c2,c3,c4 = st.columns(4)
    c1.metric('Itens do roteiro',len(tagged))
    c2.metric('Concluídos',done)
    c3.metric('Orçamento previsto',brl(planned))
    c4.metric('Parcelas cadastradas',sum(1 for e in entries if e.get('task_id') in {t['id'] for _,t in tagged}))
    with st.expander('Como preencher o plano',expanded=False):
        st.write('**Editar ficha**: campos de matrícula, proprietário, consultas e condições especiais. **Valor / pagamentos**: parcelas e desembolsos. **Execução**: marcos, datas e andamento. **Anexos**: documentos de cada item. **Abrir tarefa**: situação, responsável, checklist e comentários.')
    for section in (DOC_SECTION, PROJECT_SECTION):
        group = [(s,t) for s,t in tagged if s['section'] == section]
        if not group:continue
        st.markdown(f'### {section}')
        if section==DOC_SECTION:
            location_kml_panel(sb,project_id,tasks,documents,can_edit,user_id)
        for spec,t in group:
            related_docs=[d for d in documents if d['task_id']==t['id']]
            documented=sum(ok for _,ok in checklist_doc_status(spec,related_docs))
            total_docs=len(spec['docs'])
            financial=sum(float(e.get('planned_amount') or 0) for e in entries if e['task_id']==t['id'])
            num_milestones=sum(m['task_id']==t['id'] for m in milestones)
            with st.container(border=True):
                a,b=st.columns([2.8,1.2])
                with a:
                    st.markdown('**'+escape(f'{spec["code"]} {spec["name"]}')+'**')
                    st.caption(f'Etapa: {by_stage.get(t["stage_id"],"")} · {t.get("status","A fazer")} · {int(t.get("percent_done") or 0)}% executado')
                with b:
                    st.caption(f'Documentos previstos: {documented}/{total_docs}')
                    st.progress(documented / total_docs if total_docs else 0.)
                detail = details_map.get(t['id'],{}).get('data') or {}
                if section==PROJECT_SECTION:
                    st.caption(f'Profissional: {detail.get("profissional") or "Não informado"}   |   Valor: {brl(t.get("planned_cost"))}   |   Início: {pretty_date(t.get("start_date"))}   |   Parcelas: {brl(financial)}   |   Atividades: {num_milestones}')
                elif detail:
                    display = ', '.join(f'{next((f[1] for f in spec.get("fields",[]) if f[0]==k),k)}: {v}' for k,v in detail.items() if v)
                    if display:st.caption(display[:350])
                st.caption('Documentos: '+', '.join(f'{"✓" if ok else "○"} {name}' for name,ok in checklist_doc_status(spec,related_docs)))
                buttons=st.columns([1,1,1,1])
                with buttons[0]:
                    if st.button('Ficha / dados',key=f'plan_card_{t["id"]}',use_container_width=True):open_task_panel(t,'Ficha técnica')
                with buttons[1]:
                    if st.button('R$ Financeiro',key=f'plan_money_{t["id"]}',use_container_width=True):open_task_panel(t,'Financeiro')
                with buttons[2]:
                    if st.button('📅 Execução',key=f'plan_ex_{t["id"]}',use_container_width=True):open_task_panel(t,'Execução')
                with buttons[3]:
                    if st.button('📎 Anexos',key=f'plan_attach_{t["id"]}',use_container_width=True):open_task_panel(t,'Anexos')
                if is_admin:
                    edit_col,delete_col=st.columns([1,1])
                    with edit_col:
                        if st.button('✎ Editar tarefa',key=f'plan_edit_{t["id"]}',use_container_width=True):
                            open_task_panel(t,'Detalhes')
                    with delete_col:
                        if st.button('✕ Excluir tarefa',key=f'plan_delete_{t["id"]}',use_container_width=True):
                            st.session_state['delete_task_confirm']=t['id']
                            st.rerun()
                    if st.session_state.get('delete_task_confirm')==t['id']:
                        st.warning('A exclusão remove a tarefa, seus pagamentos, fichas, marcos, anexos e checklist. Gere um backup antes de confirmar.')
                        confirm=st.checkbox('Confirmo a exclusão definitiva desta tarefa e dos dados vinculados.',
                                            key=f'confirm_delete_task_{t["id"]}')
                        send=st.button('Confirmar exclusão',key=f'execute_delete_{t["id"]}',
                                       type='primary',disabled=not confirm)
                        if send and confirm:
                            try:
                                paths=sb.rpc('admin_delete_workflow_task',{'p_task_id':t['id']}).execute().data or []
                                st.session_state.pop('delete_task_confirm',None)
                                if paths:
                                    try:sb.storage.from_('project-files').remove(paths)
                                    except Exception as storage_exc:
                                        st.warning('Tarefa excluída, mas alguns arquivos podem continuar no Storage. '
                                                   f'Faça a limpeza manual do bucket: {storage_exc}')
                                st.success('Tarefa excluída.');st.rerun()
                            except Exception as exc:st.error(f'Erro ao excluir tarefa: {exc}')


def technical_form(sb, project_id: str, task: dict, can_edit: bool, details: dict | None):
    code=code_for_task(task, details)
    if not code or code not in BY_CODE:
        st.info('Tarefa sem ficha técnica padrão. Utilize os detalhes normais da tarefa.')
        return
    spec=BY_CODE[code]
    state=(details or {}).get('data') or {}
    st.markdown(f'#### Ficha {code} · {spec["name"]}')
    st.caption('Campos do cadastro técnico. Informações complementares ficam no campo de observações.')
    with st.form(f'technical_form_{task["id"]}'):
        fields={}
        if spec['section']==PROJECT_SECTION and code not in ('2.10',):
            fields['profissional']=st.text_input('Profissional responsável (nome)',value=str(state.get('profissional') or ''),disabled=not can_edit)
        for key,label,ftype in spec.get('fields',[]):
            value=state.get(key)
            if ftype=='number':
                fields[key]=st.number_input(label,min_value=0.,value=float(value or 0),format='%.2f',disabled=not can_edit)
            elif ftype in ('choice','yesno','road'):
                opts={'choice':OPTIONS,'yesno':['A definir','Sim','Não'],'road':['A definir','Não se aplica','Rodovia estadual','Rodovia federal','Concessionária']}[ftype]
                fields[key]=st.selectbox(label,opts,index=opts.index(value) if value in opts else 0,disabled=not can_edit)
            elif ftype=='longtext':
                fields[key]=st.text_area(label,value=str(value or ''),disabled=not can_edit)
            else:
                fields[key]=st.text_input(label,value=str(value or ''),disabled=not can_edit)
        fields['observacoes']=st.text_area('Observações e pendências',value=str(state.get('observacoes') or ''),disabled=not can_edit)
        submit=st.form_submit_button('Salvar ficha técnica',type='primary',disabled=not can_edit)
    if submit:
        data={'project_id':project_id,'task_id':task['id'],'template_code':code,'data':fields}
        try:
            sb.table('task_details').upsert(data,on_conflict='task_id').execute()
            st.success('Ficha registrada no Supabase.')
            st.rerun()
        except Exception as exc:
            st.error(f'Não foi possível gravar os dados: {exc}')
    st.markdown('**Documentos previstos para este item**')
    st.write(', '.join(spec['docs']))
    if spec['section']==PROJECT_SECTION:
        st.info('O valor e a data de início da tarefa são editados em **Detalhes**. As parcelas estão em **Financeiro** e as atividades planejadas em **Execução**.')


def execution_detail(sb, project_id: str, task: dict, can_edit: bool):
    st.markdown('#### Cronograma de execução por atividade')
    st.caption(f'Período geral da tarefa: {pretty_date(task.get("start_date"))} até {pretty_date(task.get("due_date"))}. Altere as datas gerais em Detalhes.')
    rows=sb.table('execution_milestones').select('*').eq('task_id',task['id']).order('start_date').execute().data or []
    if rows:
        df=pd.DataFrame([{'Atividade':x['title'],'Início':x['start_date'],'Fim':x['due_date'],
                'Avanço':x['percent_done'],'Situação':x['status']} for x in rows])
        st.dataframe(df,hide_index=True,use_container_width=True)
        chart=df.copy()
        chart['Início']=pd.to_datetime(chart['Início']);chart['Fim']=pd.to_datetime(chart['Fim'])
        chart['Fim desenho']=chart['Fim']+pd.Timedelta(days=1)
        fig=px.timeline(chart,x_start='Início',x_end='Fim desenho',y='Atividade',color='Situação',
                  hover_data=['Avanço'],color_discrete_map={'A fazer':'#94A3B8','Em andamento':'#0F766E','Concluída':'#22A06B','Bloqueada':'#DC2626'})
        fig.update_yaxes(autorange='reversed');fig.update_layout(height=max(270,len(chart)*54+95),margin=dict(l=5,r=5,t=12,b=8),legend_title_text='')
        st.plotly_chart(fig,use_container_width=True)
        if can_edit:
            for row in rows:
                with st.expander(f"Editar · {row['title']}"):
                    with st.form(f'execution_edit_{row["id"]}'):
                        title=st.text_input('Atividade',value=row['title'])
                        a,b,c=st.columns(3)
                        with a:begin=st.date_input('Início',_date(row['start_date']))
                        with b:end=st.date_input('Conclusão',_date(row['due_date']))
                        with c:pct=st.slider('Avanço %',0,100,int(row.get('percent_done') or 0))
                        status=st.selectbox('Situação',['A fazer','Em andamento','Concluída','Bloqueada'],index=['A fazer','Em andamento','Concluída','Bloqueada'].index(row['status']))
                        save=st.form_submit_button('Salvar alterações')
                        remove=st.form_submit_button('Excluir atividade')
                    try:
                        if save:
                            if not title.strip() or end<begin:st.error('Verifique o título e as datas.')
                            else:
                                sb.table('execution_milestones').update({'title':title.strip(),'start_date':begin.isoformat(),
                                    'due_date':end.isoformat(),'percent_done':100 if status=='Concluída' else pct,'status':status}).eq('id',row['id']).execute();st.rerun()
                        elif remove:
                            sb.table('execution_milestones').delete().eq('id',row['id']).execute();st.rerun()
                    except Exception as exc:st.error(f'Falha ao salvar atividade: {exc}')
    else:st.info('Nenhuma atividade de execução registrada. Adicione os marcos previstos abaixo.')
    if can_edit:
        with st.expander('➕ Adicionar atividade ao cronograma',expanded=not bool(rows)):
            with st.form(f'new_execution_{task["id"]}'):
                title=st.text_input('Nome da atividade / marco',placeholder='Ex.: levantamento, revisão, protocolo, aprovação')
                a,b=st.columns(2)
                with a:begin=st.date_input('Data de início',_date(task.get('start_date')))
                with b:end=st.date_input('Data final',_date(task.get('due_date'),date.today()+timedelta(days=14)))
                progress=st.slider('Avanço (%)',0,100,0)
                status=st.selectbox('Situação',['A fazer','Em andamento','Concluída','Bloqueada'])
                send=st.form_submit_button('Registrar atividade',type='primary')
            if send:
                if not title.strip() or end<begin:st.error('Informe um título e datas válidas.')
                else:
                    try:
                        sb.table('execution_milestones').insert({'project_id':project_id,'task_id':task['id'],
                            'title':title.strip(),'start_date':begin.isoformat(),'due_date':end.isoformat(),
                            'percent_done':100 if status=='Concluída' else progress,'status':status}).execute()
                        st.rerun()
                    except Exception as exc:st.error(f'Não foi possível incluir a atividade: {exc}')
