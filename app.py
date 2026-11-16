"""CronogramaObras Cloud - gestão de projetos, aprovações e cronogramas.

Execução: streamlit run app.py | Python 3.12+
Não usar chave service_role. Cada sessão possui cliente próprio para respeitar RLS.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from PIL import Image

import pandas as pd
import plotly.express as px
import streamlit as st

from src.db import (
    ALLOWED_EXTENSIONS, add_project_with_workflow, brl, delete, insert, members,
    new_client, pretty_date, query, remove_document, signed_file_url, update, upload_document,
)
from src.reports import brief_stats, pdf_report, xlsx_report
from src.workflow import DEFAULT_SECTION_NAMES, make_template_rows, doc_categories, BY_CODE, code_for_task, checklist_doc_status
from src.workflow_ui import technical_form, execution_detail, get_detail_map, get_milestones, overview_plan
from src.ui import icon, metric_card, CSS
from src.backup_ui import backup_page

st.set_page_config(page_title="CronogramaObras Cloud", page_icon=Image.open(Path(__file__).parent / "assets/cronograma-favicon.png"), layout="wide", initial_sidebar_state="expanded")

STATUS = ["A fazer", "Em andamento", "Em aprovação", "Concluída", "Bloqueada"]
PRIORITY = ["Baixa", "Normal", "Alta", "Urgente"]
CATEGORIES = doc_categories()
NAV = ["Dashboard", "Projetos", "Etapas", "Quadro de tarefas", "Cronograma", "Financeiro", "Documentos", "Equipe", "Relatórios", "Backups"]
NAV_ICONS = {"Dashboard":"dashboard", "Projetos":"folder", "Etapas":"check", "Quadro de tarefas":"check", "Cronograma":"calendar", "Financeiro":"wallet", "Documentos":"files", "Equipe":"people", "Relatórios":"chart", "Backups":"backup"}

st.markdown(CSS, unsafe_allow_html=True)


def fail(err, prefix="Operação não concluída"):
    msg = str(err)
    if len(msg) > 400: msg = msg[:400] + "…"
    st.error(f"{prefix}: {msg}")


def client_from_secrets():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_ANON_KEY"]
        if "SEU-PROJETO" in url or "SUA_CHAVE" in key:
            st.warning("Configure .streamlit/secrets.toml com a URL e chave pública do Supabase.")
            st.stop()
        return new_client(url, key)
    except KeyError:
        st.error("Credenciais ausentes. Copie secrets.toml.example para secrets.toml e informe as chaves públicas.")
        st.stop()
    except Exception as exc:
        fail(exc,"Não foi possível conectar ao Supabase")
        st.stop()


def current_client():
    return st.session_state.get("supabase_client")


def login_page():
    a,b,c = st.columns([1,1.5,1])
    with b:
        st.markdown('<div class="co-banner"><h1>CronogramaObras Cloud</h1><p>Projetos, tarefas, aprovações e orçamento em um só lugar.</p></div>',unsafe_allow_html=True)
        login_tab,signup_tab = st.tabs(["Entrar", "Criar conta"])
        with login_tab:
            with st.form("login_form"):
                email = st.text_input("E-mail",placeholder="voce@empresa.com")
                password = st.text_input("Senha",type="password")
                submit = st.form_submit_button("Entrar no sistema",type="primary",use_container_width=True)
            if submit:
                try:
                    sb=client_from_secrets()
                    response=sb.auth.sign_in_with_password({"email":email.strip(),"password":password})
                    if not response.user or not response.session:
                        raise RuntimeError("Não foi possível obter sessão autenticada.")
                    st.session_state["supabase_client"]=sb
                    st.session_state["user_id"]=str(response.user.id)
                    st.session_state["user_email"]=response.user.email or email
                    st.rerun()
                except Exception as exc: fail(exc,"Login recusado")
        with signup_tab:
            with st.form("signup_form"):
                name=st.text_input("Nome completo")
                email2=st.text_input("E-mail profissional")
                pw2=st.text_input("Senha",type="password")
                create=st.form_submit_button("Cadastrar",use_container_width=True)
            if create:
                if len(name.strip()) < 3 or len(pw2) < 8:
                    st.warning("Informe nome completo e senha com pelo menos 8 caracteres.")
                else:
                    try:
                        sb=client_from_secrets()
                        res=sb.auth.sign_up({"email":email2.strip(),"password":pw2,
                             "options":{"data":{"full_name":name.strip()}}})
                        if res.session and res.user:
                            st.session_state["supabase_client"]=sb
                            st.session_state["user_id"]=str(res.user.id)
                            st.session_state["user_email"]=res.user.email
                            st.rerun()
                        st.success("Cadastro iniciado. Confirme o e-mail e depois entre no sistema.")
                    except Exception as exc: fail(exc,"Falha no cadastro")
        st.caption("Seus dados e arquivos ficam protegidos pelas permissões do empreendimento no Supabase.")


def api(table, project_id=None, sort="created_at", asc=False):
    return query(current_client(),table,project_id,sort,asc)


def do_insert(table,row):return insert(current_client(),table,row)
def do_update(table,row_id,changes):return update(current_client(),table,row_id,changes)
def do_delete(table,row_id):return delete(current_client(),table,row_id)


def date_value(text,fallback=None):
    try:return date.fromisoformat(str(text)[:10])
    except Exception:return fallback or date.today()


def top_banner(project):
    st.markdown('<div class="co-banner">'+icon('building','#d1f9f4',45)+
        '<div><h1>'+escape(project['title'])+'</h1><p>'+escape(project.get('location') or 'Local a definir')+
        ' &nbsp; · &nbsp; '+escape(project.get('client_name') or 'Empresa não informada')+
        ' &nbsp; · &nbsp; Previsão '+escape(pretty_date(project.get('target_date')))+
        '</p></div></div>',unsafe_allow_html=True)


def show_new_project():
    st.title("Cadastrar empreendimento")
    st.caption("O planejamento começa com as etapas de Documentação (1.1–1.3) e Projetos (2.1–2.10). Todas as tarefas, datas e valores são editáveis.")
    with st.form("new_project",clear_on_submit=False):
        c1,c2=st.columns(2)
        with c1:
            title=st.text_input("Nome do projeto *",placeholder="Implantação de unidade operacional")
            client_name=st.text_input("Cliente / empresa")
            location=st.text_input("Município / endereço de referência")
            start=st.date_input("Data de início",date.today())
        with c2:
            target=st.date_input("Previsão de conclusão",date.today()+timedelta(days=180))
            description=st.text_area("Descrição do escopo",height=116)
        st.info("13 itens automáticos em duas áreas: matrícula, proprietário e contratos; topografia, projetos, EIV, licenças, acesso e Habite-se. Prazos são somente estimativas internas.")
        send=st.form_submit_button("Criar projeto e cronograma completo",type="primary",use_container_width=True)
    if send:
        if len(title.strip())<3:
            st.warning("Informe um nome com pelo menos 3 caracteres.")
        elif target<start:
            st.warning("A conclusão não pode anteceder o início.")
        else:
            try:
                templates=make_template_rows(start,DEFAULT_SECTION_NAMES)
                project=add_project_with_workflow(current_client(),st.session_state['user_id'],{
                    "title":title.strip(),"client_name":client_name.strip(),"location":location.strip(),
                    "description":description.strip(),"start_date":start.isoformat(),"target_date":target.isoformat(),
                },templates)
                st.session_state['project_id']=project['id']
                st.session_state['page']='Dashboard'
                st.success("Empreendimento e 13 etapas criados.")
                st.rerun()
            except Exception as exc:
                fail(exc,"Falha na criação do empreendimento. Verifique o SQL de migração do Supabase")


def show_projects(projects):
    st.title('Portfólio de projetos')
    st.caption('Escolha o empreendimento para acompanhar o andamento, ou crie um novo com o roteiro completo de documentação e projetos.')
    a,b=st.columns([2,1])
    with b:
        if st.button('Criar novo empreendimento',type='primary',use_container_width=True):
            st.session_state['page']='Novo projeto';st.rerun()
    if not projects:
        st.info('Nenhum projeto cadastrado ainda.')
        return
    cards=st.columns(3)
    for n,p in enumerate(projects):
        with cards[n%3]:
            with st.container(border=True):
                st.markdown('**'+escape(p['title'])+'**')
                st.caption((p.get('client_name') or 'Empresa não informada')+' · '+(p.get('location') or 'Local não informado'))
                st.caption('Previsão: '+pretty_date(p.get('target_date')))
                if st.button('Abrir painel',key='choose_project_'+p['id'],use_container_width=True):
                    st.session_state['project_id']=p['id']
                    st.session_state['page']='Dashboard'
                    st.rerun()


def task_snapshot(project_id):
    stages=api("stages",project_id,"sort_order",True)
    tasks=api("tasks",project_id,"sort_order",True)
    finance=api("finance_entries",project_id,"planned_date",True)
    docs=api("documents",project_id,"uploaded_at",False)
    return stages,tasks,finance,docs


def get_task_label(task,stage_names):
    return f"{task['title']} · {stage_names.get(task['stage_id'],'') }"


def dashboard(project,stages,tasks,entries,docs):
    st.markdown('<div class="co-eyebrow">CENTRAL DE INTELIGÊNCIA DO EMPREENDIMENTO</div>',unsafe_allow_html=True)
    st.subheader('Painel executivo')
    stats=brief_stats(tasks,entries)
    today=date.today()
    overdue=[t for t in tasks if t['status']!='Concluída' and t.get('due_date') and date_value(t['due_date'])<today]
    # Considera o checklist documental associado ao roteiro de implantação.
    found_docs=[]
    for t in tasks:
        spec=BY_CODE.get(code_for_task(t))
        if spec:
            own=[d for d in docs if d['task_id']==t['id']]
            found_docs.extend(checklist_doc_status(spec,own))
    docs_ok=sum(done for _,done in found_docs)
    doc_total=len(found_docs)
    doc_pending=doc_total-docs_ok
    kpis=[
        ('Tarefas do projeto',str(stats['total']),'check','Roteiro de implantação','teal'),
        ('Avanço geral',f"{stats['progress']:.1f}%",'progress','Execução das atividades','teal'),
        ('Atividades atrasadas',str(len(overdue)),'alert','Prazos vencidos','danger'),
        ('Documentos pendentes',str(doc_pending),'files',f'{docs_ok}/{doc_total} requisitos recebidos','gold'),
        ('Orçamento estimado',brl(stats['budget']),'wallet','Soma dos custos das tarefas','teal'),
        ('Financeiro planejado',brl(stats['planned']),'calendar','Parcelas lançadas','teal'),
        ('Financeiro realizado',brl(stats['paid']),'chart','Pagamentos registrados','teal'),
        ('Tarefas concluídas',str(stats['closed']),'dashboard','Etapas finalizadas','teal'),
    ]
    for offset in (0,4):
        html=''.join(metric_card(*item) for item in kpis[offset:offset+4])
        st.markdown('<div class="co-kpi-row">'+html+'</div>',unsafe_allow_html=True)
    a,b=st.columns([1.1,1],gap='medium')
    with a:
        st.markdown('<div class="co-section">Situação das tarefas</div>',unsafe_allow_html=True)
        summary=pd.DataFrame([{'Situação':s,'Quantidade':sum(t['status']==s for t in tasks)} for s in STATUS])
        summary=summary[summary['Quantidade']>0]
        if not summary.empty:
            fig=px.pie(summary,names='Situação',values='Quantidade',hole=.7,
                color='Situação',color_discrete_map={'A fazer':'#96aabb','Em andamento':'#087F80',
                'Em aprovação':'#5487d1','Concluída':'#43a477','Bloqueada':'#c95c61'})
            fig.update_traces(textposition='outside',textinfo='percent+label',sort=False)
            fig.update_layout(height=310,margin=dict(t=12,l=12,r=12,b=8),showlegend=False,
                paper_bgcolor='rgba(0,0,0,0)',font=dict(family='Arial',size=12))
            st.plotly_chart(fig,use_container_width=True)
        else:st.info('Nenhuma tarefa no projeto.')
    with b:
        st.markdown('<div class="co-section">Progresso por área</div>',unsafe_allow_html=True)
        by_stage=[]
        for stage in stages:
            stage_tasks=[t for t in tasks if t['stage_id']==stage['id']]
            p=round(sum(float(t.get('percent_done') or 0) for t in stage_tasks)/len(stage_tasks),1) if stage_tasks else 0.
            by_stage.append({'Área':stage['name'],'Avanço (%)':p})
        if by_stage:
            fig=px.bar(pd.DataFrame(by_stage),x='Avanço (%)',y='Área',orientation='h',text='Avanço (%)',
                color_discrete_sequence=['#087F80'])
            fig.update_traces(texttemplate='%{x:.0f}%',textposition='outside',marker_cornerradius=7)
            fig.update_layout(height=310,xaxis_range=[0,110],margin=dict(l=5,r=35,t=16,b=8),
                showlegend=False,paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig,use_container_width=True)
    a,b=st.columns([1.2,1],gap='medium')
    with a:
        st.markdown('<div class="co-section">Fluxo financeiro · planejado x pago</div>',unsafe_allow_html=True)
        monthly=defaultdict(lambda:{'Planejado':0.0,'Realizado':0.0})
        for e in entries:
            monthly[str(e['planned_date'])[:7]]['Planejado']+=float(e.get('planned_amount') or 0)
            if e.get('status')=='Pago':
                monthly[str(e.get('paid_date') or e['planned_date'])[:7]]['Realizado']+=float(e.get('paid_amount') or 0)
        if monthly:
            rows=[{'Mês':m,'Tipo':k,'Valor':v} for m,data in sorted(monthly.items()) for k,v in data.items()]
            fig=px.bar(pd.DataFrame(rows),x='Mês',y='Valor',color='Tipo',barmode='group',
                color_discrete_map={'Planejado':'#087F80','Realizado':'#dca64b'})
            fig.update_layout(height=308,margin=dict(t=15,l=5,r=5,b=8),legend_title_text='',
                paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig,use_container_width=True)
        else:st.info('Registre parcelas nas tarefas para acompanhar o fluxo de caixa.')
    with b:
        st.markdown('<div class="co-section">Agenda e prazos prioritários</div>',unsafe_allow_html=True)
        pending=sorted([t for t in tasks if t['status']!='Concluída'],key=lambda t:t.get('due_date') or '9999-12-31')[:5]
        for t in pending:
            with st.container(border=True):
                c1,c2=st.columns([4,1])
                with c1:
                    st.markdown('**'+escape(t['title'])+'**')
                    st.caption(pretty_date(t.get('due_date'))+' · '+t['status'])
                with c2:
                    if st.button('Abrir',key=f'next_{t["id"]}'):
                        open_task(t['id'])
        if not pending:st.success('Sem pendências de execução.')
    if overdue:
        st.warning(f'{len(overdue)} tarefa(s) com prazo vencido. Abra o quadro de tarefas para tratar.')


def export_buttons(project,stages,tasks,entries,docs):
    c1,c2=st.columns(2)
    try:
        extras = {}
        try:
            extras = {'detail_map':get_detail_map(current_client(),project['id']),
                      'milestones':get_milestones(current_client(),project['id'])}
        except Exception:
            st.caption('Relatório detalhado indisponível até aplicar o SQL de atualização. O relatório anterior permanece utilizável.')
        with c1:
            st.download_button("📄 Baixar relatório PDF",pdf_report(project,stages,tasks,entries,docs,**extras),
              file_name="relatorio_cronograma.pdf",mime="application/pdf",use_container_width=True)
        with c2:
            st.download_button("📊 Baixar relatório Excel",xlsx_report(project,stages,tasks,entries,docs,**extras),
              file_name="relatorio_cronograma.xlsx",
              mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)
    except Exception as exc: fail(exc,"Falha ao gerar relatório")


def open_task(task_id):
    st.session_state["selected_task_id"]=task_id
    st.session_state["page"]="Quadro de tarefas"
    st.rerun()


def kanban(project_id,stages,tasks,docs,can_edit,team):
    if st.session_state.get('selected_task_id'):
        task=next((x for x in tasks if x['id']==st.session_state['selected_task_id']),None)
        if task:
            task_detail(project_id,task,stages,docs,can_edit,team)
            return
        st.session_state['selected_task_id']=None
    st.subheader("Quadro de tarefas")
    c1,c2,c3=st.columns([1.2,1.2,1.1])
    stage_names={s['id']:s['name'] for s in stages}
    with c1:stage_filter=st.selectbox("Área / etapa",['Todos']+[s['name'] for s in stages])
    with c2:search=st.text_input("Buscar tarefa",placeholder="projeto, licença, aprovação...")
    with c3:
        if can_edit and st.button("➕ Nova tarefa",type='primary',use_container_width=True):
            st.session_state['show_new_task']=not st.session_state.get('show_new_task',False)
    if can_edit and st.session_state.get('show_new_task'):
        with st.expander("Criar nova tarefa",expanded=True):
            with st.form("task_create"):
                name=st.text_input('Título *')
                desc=st.text_area('Descrição / requisitos')
                org=st.selectbox('Etapa',options=stages,format_func=lambda x:x['name'])
                x,y=st.columns(2)
                with x:start=st.date_input('Início',date.today(),key='create_start')
                with y:due=st.date_input('Fim previsto',date.today()+timedelta(days=14),key='create_due')
                cost=st.number_input('Orçamento previsto (R$)',min_value=0.0,step=100.0)
                save=st.form_submit_button('Salvar tarefa',type='primary')
            if save:
                try:
                    do_insert('tasks',{'project_id':project_id,'stage_id':org['id'],
                        'title':name.strip(),'description':desc.strip(),
                        'start_date':start.isoformat(),'due_date':due.isoformat(),'planned_cost':cost})
                    st.session_state['show_new_task']=False;st.rerun()
                except Exception as exc:fail(exc)
    visible=[t for t in tasks if (stage_filter=='Todos' or stage_names.get(t['stage_id'])==stage_filter)
            and (not search or search.casefold() in (t['title']+' '+t.get('description','')).casefold())]
    cols=st.columns(5,gap='small')
    for col,status in zip(cols,STATUS):
        with col:
            count=sum(t['status']==status for t in visible)
            st.markdown(f"**{status}**  ·  {count}")
            for task in visible:
                if task['status']!=status:continue
                with st.container(border=True):
                    st.markdown('**'+escape(task['title'])+'**')
                    st.caption(stage_names.get(task['stage_id'],'')+' · '+task.get('priority','Normal'))
                    st.caption('📅 '+pretty_date(task.get('due_date')))
                    st.progress(int(task.get('percent_done') or 0)/100)
                    if not any(d['task_id']==task['id'] and d['category']=='Orçamento' for d in docs):
                        st.caption('⚠️ Orçamento pendente')
                    if st.button('Abrir detalhes',key=f"kanban_{task['id']}",use_container_width=True):
                        open_task(task['id'])
    if not visible:st.info('Nenhuma tarefa com os filtros selecionados.')


def task_detail(project_id,task,stages,all_docs,can_edit,team):
    if st.button('← Voltar ao quadro'):
        st.session_state['selected_task_id']=None;st.rerun()
    st.title(task['title'])
    st.caption(task.get('description') or 'Detalhes, documentos, checklist e fluxo financeiro da tarefa.')
    related_docs=[d for d in all_docs if d['task_id']==task['id']]
    own_budget=any(d['category']=='Orçamento' for d in related_docs)
    if not own_budget:st.warning('Esta tarefa ainda não possui orçamento anexado. A conclusão só será liberada após o envio.')
    panels=['Ficha técnica','Detalhes','Checklist','Financeiro','Execução','Anexos','Comentários']
    pane=st.radio('Área da tarefa',panels,key=f'task_panel_{task["id"]}',horizontal=True)
    if pane=='Detalhes':
        with st.form('task_edit'):
            title=st.text_input('Título',value=task['title'],disabled=not can_edit)
            desc=st.text_area('Descrição e requisitos',value=task.get('description') or '',height=145,disabled=not can_edit)
            r1,r2,r3=st.columns(3)
            with r1:
                org_idx=next((i for i,s in enumerate(stages) if s['id']==task['stage_id']),0)
                stage=st.selectbox('Área / fase',stages,index=org_idx,format_func=lambda s:s['name'],disabled=not can_edit)
                status=st.selectbox('Situação',STATUS,index=STATUS.index(task['status']),disabled=not can_edit)
                priority=st.selectbox('Prioridade',PRIORITY,index=PRIORITY.index(task['priority']),disabled=not can_edit)
            with r2:
                start=st.date_input('Início previsto',date_value(task.get('start_date')),disabled=not can_edit)
                due=st.date_input('Conclusão prevista',date_value(task.get('due_date')),disabled=not can_edit)
                progress=st.slider('Execução (%)',0,100,int(task.get('percent_done') or 0),1,disabled=not can_edit)
            with r3:
                choices=[('', 'Sem responsável')]+[(m['user_id'],m['profile'].get('full_name') or m['profile'].get('email','Usuário')) for m in team]
                vals=[x[0] for x in choices]
                try:pos=vals.index(task.get('responsible_id') or '')
                except ValueError:pos=0
                assignee=st.selectbox('Responsável',vals,index=pos,format_func=lambda x:dict(choices).get(x,x),disabled=not can_edit)
                planned=st.number_input('Valor previsto (R$)',min_value=0.0,value=float(task.get('planned_cost') or 0),step=100.0,disabled=not can_edit)
                st.caption('O valor previsto da tarefa pode ser diferente do desembolso mensal do cronograma financeiro.')
            save=st.form_submit_button('Salvar alterações',type='primary',disabled=not can_edit)
        if save:
            if due<start:st.warning('Prazo final anterior à data inicial.')
            elif status=='Concluída' and not own_budget:st.error('Primeiro anexe um orçamento na aba Anexos.')
            else:
                try:
                    do_update('tasks',task['id'],{
                        'title':title.strip(),'description':desc.strip(),'stage_id':stage['id'],
                        'status':status,'priority':priority,'responsible_id':assignee or None,
                        'start_date':start.isoformat(),'due_date':due.isoformat(),
                        'percent_done':100 if status=='Concluída' else progress,'planned_cost':planned,
                    });st.success('Tarefa atualizada.');st.rerun()
                except Exception as exc:fail(exc)
    if pane=='Ficha técnica':
        try:
            details=current_client().table('task_details').select('*').eq('task_id',task['id']).limit(1).execute().data or []
            technical_form(current_client(),project_id,task,can_edit,details[0] if details else None)
        except Exception as exc:fail(exc,'Execute o SQL de atualização do Supabase para habilitar as fichas técnicas')
    elif pane=='Checklist':show_checklist(project_id,task,can_edit)
    elif pane=='Financeiro':show_finance_task(project_id,task,can_edit)
    elif pane=='Execução':
        try:execution_detail(current_client(),project_id,task,can_edit)
        except Exception as exc:fail(exc,'Execute o SQL de atualização do Supabase para habilitar as atividades de execução')
    elif pane=='Anexos':attachments(project_id,task,related_docs,can_edit)
    elif pane=='Comentários':comments(project_id,task,team)


def show_checklist(project_id,task,can_edit):
    rows=current_client().table('task_checklist').select('*').eq('task_id',task['id']).order('sort_order').execute().data or []
    st.markdown('#### Passo a passo da etapa')
    for item in rows:
        c1,c2=st.columns([10,1])
        with c1:
            checked=st.checkbox(item['title'],value=item['completed'],key=f"check_{item['id']}",disabled=not can_edit)
            if checked!=item['completed']:
                try:do_update('task_checklist',item['id'],{'completed':checked});st.rerun()
                except Exception as exc:fail(exc)
        with c2:
            if can_edit and st.button('✕',key=f"remove_check_{item['id']}"):
                try:do_delete('task_checklist',item['id']);st.rerun()
                except Exception as exc:fail(exc)
    if can_edit:
        with st.form('add_check',clear_on_submit=True):
            text=st.text_input('Nova atividade do checklist')
            save=st.form_submit_button('Adicionar passo')
        if save and text.strip():
            try:
                do_insert('task_checklist',{'project_id':project_id,'task_id':task['id'],
                   'title':text.strip(),'sort_order':len(rows)})
                st.rerun()
            except Exception as exc:fail(exc)
    if not rows:st.info('Adicione conferências, vistorias ou entregas específicas desta etapa.')


def show_finance_task(project_id,task,can_edit):
    rows=current_client().table('finance_entries').select('*').eq('task_id',task['id']).order('planned_date').execute().data or []
    st.markdown('#### Parcelas e desembolsos desta tarefa')
    st.metric('Orçamento da tarefa',brl(task.get('planned_cost')))
    if rows:
        st.dataframe(pd.DataFrame([{'Vencimento':pretty_date(e['planned_date']),'Descrição':e['description'],
          'Previsto':brl(e['planned_amount']),'Pago':brl(e['paid_amount']),
          'Quitação':pretty_date(e.get('paid_date')),'Situação':e['status']} for e in rows]),
          hide_index=True,use_container_width=True)
        if can_edit:
            for e in rows:
                c1,c2,c3=st.columns([5,2,1])
                with c1:st.caption(f"{e['description']} · {pretty_date(e['planned_date'])}")
                with c2:
                    if e['status']!='Pago' and st.button('Marcar pago',key=f"pay_{e['id']}"):
                        try:do_update('finance_entries',e['id'],{'status':'Pago','paid_date':date.today().isoformat(),
                         'paid_amount':e['planned_amount']});st.rerun()
                        except Exception as exc:fail(exc)
                with c3:
                    if st.button('Excluir',key=f"del_fin_{e['id']}"):
                        try:do_delete('finance_entries',e['id']);st.rerun()
                        except Exception as exc:fail(exc)
    if can_edit:
        with st.expander('➕ Lançar nova parcela / pagamento',expanded=not bool(rows)):
            with st.form('new_fin'):
                descr=st.text_input('Descrição *',placeholder='Ex.: 1ª parcela do projeto executivo')
                a,b,c=st.columns(3)
                with a:planned_date=st.date_input('Vencimento previsto',date.today())
                with b:amount=st.number_input('Valor previsto (R$)',min_value=0.0,step=100.0)
                with c:paid=st.checkbox('Já foi pago')
                actual=st.number_input('Valor efetivamente pago (R$)',min_value=0.0,step=100.0) if paid else 0.0
                paid_date=st.date_input('Data do pagamento',date.today()) if paid else None
                send=st.form_submit_button('Adicionar lançamento',type='primary')
            if send:
                if not descr.strip():st.warning('Informe a descrição da parcela.')
                else:
                    try:
                        do_insert('finance_entries',{'project_id':project_id,'task_id':task['id'],
                          'description':descr.strip(),'planned_date':planned_date.isoformat(),
                          'planned_amount':amount,'paid_date':paid_date.isoformat() if paid else None,
                          'paid_amount':actual if paid else 0,'status':'Pago' if paid else 'Previsto'})
                        st.rerun()
                    except Exception as exc:fail(exc)


def attachments(project_id,task,docs,can_edit):
    st.markdown('#### Documentos da tarefa')
    code=code_for_task(task)
    spec=BY_CODE.get(code)
    if spec:
        st.markdown('**Documentos previstos para a etapa**')
        for category,found in checklist_doc_status(spec,docs):
            st.caption(('✅' if found else '⬜')+' '+category)
    st.caption('PDF, imagens (PNG/JPG/WEBP), Excel (XLS/XLSX/XLSM), CSV, Word, DWG, DXF, ZIP e TXT. Até 25 MB por arquivo.')
    if can_edit:
        with st.form('upload_form',clear_on_submit=True):
            category=st.selectbox('Tipo de documento',CATEGORIES)
            upload=st.file_uploader('Anexar um ou vários documentos',type=sorted(x[1:] for x in ALLOWED_EXTENSIONS),accept_multiple_files=True)
            send=st.form_submit_button('Enviar documentos',type='primary')
        if send:
            if not upload:st.warning('Selecione pelo menos um arquivo.')
            else:
                errors=[]
                for uploaded in upload:
                    try:upload_document(current_client(),project_id,task['id'],st.session_state['user_id'],uploaded,category)
                    except Exception as exc:errors.append(f"{uploaded.name}: {exc}")
                if errors:
                    for e in errors:st.error(e)
                else:st.success('Todos os anexos foram enviados.');st.rerun()
    if not docs:st.info('Nenhum arquivo anexado a esta tarefa.')
    for d in docs:
        with st.container(border=True):
            c1,c2,c3=st.columns([5,2,1])
            with c1:
                st.markdown('**'+escape(d['filename'])+'**')
                st.caption(f"{d['category']} · {d['size_bytes']/1024:.1f} KB · {pretty_date(d['uploaded_at'])}")
            with c2:
                try:
                    url=signed_file_url(current_client(),d['storage_path'])
                    if url:st.link_button('Abrir / baixar ↗',url,use_container_width=True)
                except Exception as exc:fail(exc,'Falha ao abrir arquivo')
            with c3:
                if can_edit and st.button('Excluir',key=f"remove_doc_{d['id']}"):
                    try:remove_document(current_client(),d);st.rerun()
                    except Exception as exc:fail(exc,'Arquivo preservado')
            if d['filename'].lower().endswith(('.png','.jpg','.jpeg','.webp')):
                with st.expander('Visualizar imagem'):
                    try:
                        url=signed_file_url(current_client(),d['storage_path'])
                        if url:st.image(url,caption=d['filename'],width=500)
                    except Exception as exc:fail(exc,'Pré-visualização indisponível')


def comments(project_id,task,team):
    st.markdown('#### Comentários e acompanhamento')
    rows=current_client().table('task_comments').select('*').eq('task_id',task['id']).order('created_at',desc=True).execute().data or []
    names={x['user_id']:x['profile'].get('full_name') or x['profile'].get('email','Equipe') for x in team}
    for item in rows:
        with st.container(border=True):
            st.caption((names.get(item['author_id']) or 'Colaborador')+' · '+item['created_at'][:16].replace('T',' '))
            st.write(item['content'])
    with st.form('comment_form',clear_on_submit=True):
        message=st.text_area('Registrar atualização / parecer / pendência',max_chars=2000)
        submit=st.form_submit_button('Publicar comentário')
    if submit and message.strip():
        try:
            do_insert('task_comments',{'project_id':project_id,'task_id':task['id'],
              'author_id':st.session_state['user_id'],'content':message.strip()})
            st.rerun()
        except Exception as exc:fail(exc)


def execution_schedule(stages,tasks):
    st.subheader('Planejamento físico · Gantt')
    stage_names={s['id']:s['name'] for s in stages}
    rows=[]
    for t in tasks:
        if not t.get('start_date') or not t.get('due_date'):continue
        rows.append({'Tarefa':t['title'],'Etapa':stage_names.get(t['stage_id'],''),
          'Início':t['start_date'],'Fim':t['due_date'],'Status':t['status'],'Avanço (%)':t['percent_done']})
    if not rows:st.info('Adicione datas às tarefas para desenhar o cronograma.');return
    df=pd.DataFrame(rows)
    df['Início']=pd.to_datetime(df['Início']);df['Fim']=pd.to_datetime(df['Fim'])
    stages_available=['Todas']+sorted(df['Etapa'].unique().tolist())
    selected=st.selectbox('Filtrar etapa',stages_available,key='gantt_stage')
    if selected!='Todas':df=df[df['Etapa']==selected]
    fig=px.timeline(df,x_start='Início',x_end='Fim',y='Tarefa',color='Status',hover_data=['Etapa','Avanço (%)'],
       color_discrete_map={'A fazer':'#94A3B8','Em andamento':'#0F766E','Em aprovação':'#3B82F6',
                           'Concluída':'#22A06B','Bloqueada':'#EF4444'})
    fig.update_yaxes(autorange='reversed')
    fig.update_layout(height=max(360,90+len(df)*35),margin=dict(l=5,r=5,t=15,b=10),legend_title_text='',
                      paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)')
    st.plotly_chart(fig,use_container_width=True)
    st.dataframe(pd.DataFrame([{'Etapa':r['Etapa'],'Tarefa':r['Tarefa'],'Início':r['Início'].date(),
       'Prazo':r['Fim'].date(),'Status':r['Status'],'Avanço':str(r['Avanço (%)'])+'%'} for _,r in df.iterrows()]),
       hide_index=True,use_container_width=True)
    try:
        milestones=get_milestones(current_client(),st.session_state['project_id'])
    except Exception:
        milestones=[]
    if milestones:
        st.markdown('#### Atividades detalhadas por item')
        names={t['id']:t['title'] for t in tasks}
        md=pd.DataFrame([{'Tarefa':names.get(m['task_id'],'-'),'Atividade':m['title'],
               'Início':m['start_date'],'Prazo':m['due_date'],
               'Status':m['status'],'Avanço (%)':m['percent_done']} for m in milestones])
        st.dataframe(md,hide_index=True,use_container_width=True)


def finance_dashboard(tasks,entries):
    st.subheader('Cronograma financeiro')
    stats=brief_stats(tasks,entries)
    a,b,c=st.columns(3)
    with a:st.metric('Previsão do cronograma',brl(stats['planned']))
    with b:st.metric('Valores já pagos',brl(stats['paid']))
    with c:st.metric('Saldo do cronograma',brl(stats['planned']-stats['paid']))
    if not entries:
        st.info('Crie lançamentos na aba **Orçamento e financeiro** de cada tarefa.')
        return
    months=defaultdict(lambda:{'Planejado':0.,'Realizado':0.})
    for item in entries:
        month=str(item['planned_date'])[:7]
        months[month]['Planejado']+=float(item['planned_amount'] or 0)
        if item['status']=='Pago':
            paid_month=str(item.get('paid_date') or item['planned_date'])[:7]
            months[paid_month]['Realizado']+=float(item['paid_amount'] or 0)
    df=pd.DataFrame([{'Mês':month,'Tipo':kind,'Valor':value}
           for month,data in sorted(months.items()) for kind,value in data.items()])
    fig=px.bar(df,x='Mês',y='Valor',color='Tipo',barmode='group',
        color_discrete_map={'Planejado':'#0F766E','Realizado':'#F59E0B'})
    fig.update_layout(height=390,margin=dict(l=5,r=5,t=18,b=4),legend_title_text='')
    st.plotly_chart(fig,use_container_width=True)
    names={t['id']:t['title'] for t in tasks}
    st.dataframe(pd.DataFrame([{'Competência':str(e['planned_date'])[:7],
      'Tarefa':names.get(e['task_id'],''),'Descrição':e['description'],
      'Valor previsto':brl(e['planned_amount']),'Pago':brl(e['paid_amount']),
      'Situação':e['status']} for e in entries]),hide_index=True,use_container_width=True)


def all_documents(project_id,stages,tasks,docs):
    st.subheader('Central de documentos')
    st.caption('Biblioteca de anexos do projeto. O link temporário é gerado somente para o arquivo selecionado.')
    if not docs:st.info('Sem anexos no projeto. Abra uma tarefa e use a guia Anexos.');return
    task_names={t['id']:t['title'] for t in tasks}
    category=st.selectbox('Categoria', ['Todas']+CATEGORIES)
    filtered=[d for d in docs if category=='Todas' or d['category']==category]
    st.dataframe(pd.DataFrame([{'Categoria':d['category'],'Documento':d['filename'],
         'Tarefa':task_names.get(d['task_id'],'Tarefa'),
         'Data':pretty_date(d['uploaded_at'])} for d in filtered]),
         hide_index=True,use_container_width=True)
    if not filtered:return
    chosen=st.selectbox('Arquivo para visualizar ou baixar',filtered,
        format_func=lambda x:x['filename']+' · '+task_names.get(x['task_id'],''))
    if chosen:
        try:
            url=signed_file_url(current_client(),chosen['storage_path'])
            if url:st.link_button('Visualizar / baixar arquivo selecionado',url,type='primary')
        except Exception as exc:fail(exc)


def team_management(project,team):
    st.subheader('Equipe e permissões')
    st.caption('Somente o proprietário pode adicionar colaboradores. O novo usuário precisa estar cadastrado no sistema.')
    for m in team:
        p=m['profile']
        left,right=st.columns([7,2])
        with left:
            st.write(f"**{p.get('full_name') or p.get('email') or m['user_id']}** — {m['role']}")
            st.caption(p.get('email',''))
        with right:
            if project['owner_id']==st.session_state['user_id'] and m['role'] != 'owner':
                if st.button('Remover acesso',key=f"member_remove_{m['user_id']}"):
                    try:
                        current_client().table('project_members').delete().eq('project_id',project['id']).eq('user_id',m['user_id']).execute()
                        st.rerun()
                    except Exception as exc:fail(exc,'Não foi possível remover a pessoa')
    if project['owner_id'] != st.session_state['user_id']:
        st.info('Você não é o proprietário deste projeto.');return
    with st.form('add_member'):
        email=st.text_input('E-mail de colaborador já cadastrado')
        role=st.selectbox('Perfil de acesso',['editor','viewer'],format_func=lambda x:
           {'editor':'Editor: altera tarefas e documentos','viewer':'Leitor: acompanha o projeto'}[x])
        send=st.form_submit_button('Adicionar à equipe',type='primary')
    if send:
        try:
            result=current_client().rpc('add_project_member',{'p_project_id':project['id'],
                 'p_email':email.strip(),'p_role':role}).execute()
            st.success(result.data or 'Colaborador incluído.');st.rerun()
        except Exception as exc:fail(exc,'Não foi possível incluir colaborador')


def reports_page(project,stages,tasks,entries,docs):
    st.title('Central de relatórios')
    st.caption('Exportação gerencial da execução, fichas técnicas, pagamentos e inventário documental.')
    stats=brief_stats(tasks,entries)
    a,b,c=st.columns(3)
    a.metric('Atividades',stats['total'])
    b.metric('Conclusão',f"{stats['progress']:.1f}%")
    c.metric('Pago',brl(stats['paid']))
    st.markdown('#### Relatório do empreendimento')
    export_buttons(project,stages,tasks,entries,docs)
    st.caption('O PDF e o Excel trazem os dados cadastrados. Para cópia recuperável com os arquivos originais, utilize Backups.')


def run():
    if not current_client():
        login_page()
        return
    try:
        auth_session=current_client().auth.get_session()
        if not auth_session:raise RuntimeError('Sessão inválida')
        last=st.session_state.get('last_auth_validation')
        if last is None or (datetime.now()-last).total_seconds()>600:
            verified=current_client().auth.get_user()
            if not verified.user or str(verified.user.id)!=st.session_state.get('user_id'):
                raise RuntimeError('Sessão inválida')
            st.session_state['last_auth_validation']=datetime.now()
        projects=api('projects',sort='created_at')
    except Exception:
        st.session_state.pop('supabase_client',None)
        st.session_state.pop('user_id',None)
        st.warning('Sessão expirada ou indisponível. Entre novamente.')
        login_page()
        return
    with st.sidebar:
        st.markdown('<div style="display:flex;align-items:center;gap:12px;margin:10px 0 8px">'
            +icon('building','#79dfd4',34)+'<div><div style="font-size:1.25rem;font-weight:800">CronogramaObras</div>'
            '<div style="font-size:.73rem;color:#a4c5d0">Cloud · Gestão de empreendimentos</div></div></div>',
            unsafe_allow_html=True)
        st.caption('Versão 0.1.4 · Gestão integrada')
        if st.button('Sair da conta',use_container_width=True):
            try:current_client().auth.sign_out()
            except Exception:pass
            for key in ['supabase_client','user_id','user_email','project_id','selected_task_id','backup_bytes']:
                st.session_state.pop(key,None)
            st.rerun()
        if projects:
            choices={p['id']:p['title'] for p in projects}
            previous=st.session_state.get('project_id')
            if previous not in choices:previous=projects[0]['id']
            project_id=st.selectbox('Empreendimento ativo',list(choices),
                index=list(choices).index(previous),format_func=lambda x:choices[x])
            if st.session_state.get('project_id')!=project_id:
                st.session_state['project_id']=project_id
                st.session_state['selected_task_id']=None
        else:project_id=None
        st.markdown('<div class="co-eyebrow" style="color:#7bd5ca;margin:18px 0 6px">NAVEGAÇÃO</div>',unsafe_allow_html=True)
        page=st.session_state.get('page','Dashboard')
        for label in NAV:
            row=st.columns([.16,.84],vertical_alignment='center',gap='small')
            with row[0]:st.markdown(icon(NAV_ICONS[label],'#72cec7' if page==label else '#a8c1c9',20),unsafe_allow_html=True)
            with row[1]:
                if st.button(label,key='nav_'+label,type='primary' if page==label else 'secondary',use_container_width=True):
                    st.session_state['page']=label
                    st.rerun()
        if st.button('＋ Novo projeto',type='primary',use_container_width=True,key='sidebar_new'):
            st.session_state['page']='Novo projeto';st.rerun()
        st.divider()
        st.caption('Acesso individual · Supabase RLS · documentos privados')
    page=st.session_state.get('page','Dashboard')
    if page=='Backups':
        backup_page(current_client(),projects,st.session_state['user_id'])
        return
    if page=='Novo projeto' or (not projects and page not in ('Projetos','Backups')):
        show_new_project()
        return
    if page=='Projetos':
        show_projects(projects)
        return
    if not projects:
        show_projects([])
        return
    project=next(p for p in projects if p['id']==project_id)
    try:
        stages,tasks,entries,docs=task_snapshot(project_id)
        team=members(current_client(),project_id)
    except Exception as exc:
        fail(exc,'Não foi possível carregar os dados do projeto')
        return
    myrole=next((m['role'] for m in team if m['user_id']==st.session_state['user_id']),
                'owner' if project.get('owner_id')==st.session_state['user_id'] else 'viewer')
    can_edit=myrole in ('owner','editor')
    top_banner(project)
    if page=='Dashboard':dashboard(project,stages,tasks,entries,docs)
    elif page=='Etapas':
        try:
            detail_map=get_detail_map(current_client(),project_id)
            milestones=get_milestones(current_client(),project_id)
            overview_plan(current_client(),project_id,stages,tasks,docs,detail_map,entries,milestones,can_edit)
        except Exception as exc:
            fail(exc,'Verifique se a atualização das tabelas técnicas foi aplicada no Supabase')
    elif page=='Quadro de tarefas':kanban(project_id,stages,tasks,docs,can_edit,team)
    elif page=='Cronograma':execution_schedule(stages,tasks)
    elif page=='Financeiro':finance_dashboard(tasks,entries)
    elif page=='Documentos':all_documents(project_id,stages,tasks,docs)
    elif page=='Equipe':team_management(project,team)
    elif page=='Relatórios':reports_page(project,stages,tasks,entries,docs)

if __name__=='__main__':run()
