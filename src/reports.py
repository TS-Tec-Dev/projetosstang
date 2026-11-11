"""Exportadores PDF e Excel (XLSX) de cronograma de projetos."""
from collections import defaultdict
from datetime import date, datetime
from io import BytesIO
from html import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
import xlsxwriter

from src.utils import brl, pretty_date

NAVY = colors.HexColor('#0D1B2A')
TEAL = colors.HexColor('#0F766E')
LIGHT = colors.HexColor('#EEF4F6')
GRAY = colors.HexColor('#526273')


def brief_stats(tasks, entries):
    total = len(tasks)
    closed = sum(t['status'] == 'Concluída' for t in tasks)
    planned = sum(float(f.get('planned_amount') or 0) for f in entries)
    paid = sum(float(f.get('paid_amount') or 0) for f in entries if f.get('status') == 'Pago')
    physical = sum(float(t.get("percent_done") or 0) for t in tasks)
    budget = sum(float(t.get("planned_cost") or 0) for t in tasks)
    return {"total": total, "closed": closed, "progress": (physical / total if total else 0),
            "planned": planned, "paid": paid, "budget": budget}


def _footer(canvas, doc):
    canvas.setStrokeColor(colors.HexColor('#DBE3E9'))
    canvas.line(36, 32, doc.pagesize[0]-36, 32)
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(GRAY)
    canvas.drawString(37, 20, 'CronogramaObras Cloud  |  Relatorio gerencial')
    canvas.drawRightString(doc.pagesize[0]-37, 20, f'Pagina {doc.page}')


def pdf_report(project: dict, stages: list, tasks: list, entries: list, docs: list) -> bytes:
    """Relatório formato A4 paisagem: físico, financeiro e relação documental."""
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=37, rightMargin=37,
                            topMargin=34, bottomMargin=43, title='Cronograma e controle de projeto')
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='Cover', fontName='Helvetica-Bold', fontSize=20, leading=25, textColor=NAVY, spaceAfter=8))
    styles.add(ParagraphStyle(name='Sub', fontName='Helvetica', fontSize=9, leading=14, textColor=GRAY))
    styles.add(ParagraphStyle(name='Sec', fontName='Helvetica-Bold', fontSize=12, textColor=TEAL, spaceBefore=15, spaceAfter=9))
    styles.add(ParagraphStyle(name='CellSmall', fontName='Helvetica', fontSize=7, leading=9))
    styles.add(ParagraphStyle(name='CellHeader', fontName='Helvetica-Bold', fontSize=7, leading=9, textColor=colors.white))
    stats = brief_stats(tasks,entries)
    story = [Paragraph(escape(project.get('title','Projeto')), styles['Cover']),
             Paragraph(f"Cliente: {escape(project.get('client_name') or '-')}  |  Local: {escape(project.get('location') or '-')}  |  Gerado em: {date.today().strftime('%d/%m/%Y')}",styles['Sub']),
             Spacer(1, 12)]
    summary = [
        ['TAREFAS', 'CONCLUIDAS', 'AVANCO', 'PREVISTO', 'REALIZADO'],
        [str(stats['total']),str(stats['closed']), f"{stats['progress']:.1f}%", brl(stats['planned']), brl(stats['paid'])],
    ]
    grid = Table(summary,colWidths=[105,105,105,195,195],rowHeights=[25,30])
    grid.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white),
       ('BACKGROUND',(0,1),(-1,1),LIGHT),('TEXTCOLOR',(0,1),(-1,1),NAVY),('FONTNAME',(0,0),(-1,-1),'Helvetica-Bold'),
       ('FONTSIZE',(0,0),(-1,0),8),('FONTSIZE',(0,1),(-1,1),11),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),10)]))
    story += [grid, Paragraph('Cronograma de execução',styles['Sec'])]
    stage_names={s['id']:s['name'] for s in stages}
    ordered_stages=sorted(enumerate(stages),key=lambda x:(x[1].get('sort_order',x[0]),x[0]))
    stage_order={s['id']:i for i,(_,s) in enumerate(ordered_stages)}
    rows=[['Etapa / orgao','Tarefa','Responsavel ID','Inicio','Prazo','Status','Avanco']]
    for t in sorted(tasks,key=lambda x: (stage_order.get(x['stage_id'],999),x.get('start_date') or '')):
        rows.append([stage_names.get(t['stage_id'],'-'),t['title'],
                     (t.get('responsible_id') or '-')[:12],pretty_date(t.get('start_date')),
                     pretty_date(t.get('due_date')), t.get('status',''),str(t.get('percent_done',0))+'%'])
    _table(story,rows,[115,215,87,75,75,91,48],styles)
    story += [Paragraph('Cronograma financeiro',styles['Sec'])]
    r=[['Vencimento','Descricao','Tarefa','Planejado','Pago','Situacao']]
    task_names={t['id']:t['title'] for t in tasks}
    for x in sorted(entries,key=lambda v:v['planned_date']):
        r.append([pretty_date(x['planned_date']),x['description'],task_names.get(x['task_id'],'-'),
                  brl(x['planned_amount']),brl(x['paid_amount']),x['status']])
    _table(story,r,[88,193,219,95,95,72],styles)
    story += [Paragraph('Documentos e comprovantes anexados',styles['Sec'])]
    d=[['Categoria','Documento','Tarefa','Data do anexo']]
    for x in docs:
        d.append([x['category'],x['filename'],task_names.get(x['task_id'],'-'),pretty_date(x.get('uploaded_at'))])
    _table(story,d,[112,293,283,74],styles)
    story += [Spacer(1,8),Paragraph('Os arquivos originais permanecem no armazenamento privado; este PDF contém a relação de anexos.',styles['Sub'])]
    doc.build(story,onFirstPage=_footer,onLaterPages=_footer)
    return buf.getvalue()


def _table(story, rows, widths, styles):
    if len(rows)==1:
        story.append(Paragraph('Nenhum registro nesta secao.',styles['Sub']))
        return
    p=lambda v: Paragraph(escape(str(v)),styles['CellSmall'])
    data=[[Paragraph(escape(str(v)),styles['CellHeader']) if i==0 else p(v) for v in row] for i,row in enumerate(rows)]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white),
      ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),
      ('BOTTOMPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),
      ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),1,TEAL)]))
    story.append(t)


def xlsx_report(project, stages, tasks, entries, docs) -> bytes:
    """Pasta de trabalho XLSX, com abas de tarefas, financeiro, documentos e resumo."""
    buf=BytesIO()
    wb=xlsxwriter.Workbook(buf, {'in_memory':True})
    title_fmt=wb.add_format({'bold':True,'font_color':'#FFFFFF','bg_color':'#0D1B2A','font_size':15,'valign':'vcenter'})
    head=wb.add_format({'bold':True,'font_color':'#FFFFFF','bg_color':'#0F766E','border':0,'text_wrap':True})
    money=wb.add_format({'num_format':'R$ #,##0.00'})
    pct=wb.add_format({'num_format':'0"%"'})
    for sheet_name in ['Resumo','Execução','Financeiro','Documentos']:
        ws=wb.add_worksheet(sheet_name)
        ws.set_tab_color('#0F766E')
        ws.hide_gridlines(2)
        ws.set_row(0,29)
        ws.merge_range(0,0,0,7,project.get('title','Projeto'),title_fmt)
    summary=wb.get_worksheet_by_name('Resumo')
    stats=brief_stats(tasks,entries)
    for idx,(name,value) in enumerate([
        ('Cliente',project.get('client_name','')),('Local',project.get('location','')),
        ('Total de tarefas',stats['total']),('Tarefas concluídas',stats['closed']),
        ('Avanço (%)',stats['progress']),('Previsão financeira',stats['planned']),
        ('Financeiro realizado',stats['paid']),('Gerado em',datetime.now().strftime('%d/%m/%Y %H:%M')),
    ],start=2):
        summary.write(idx,0,name,head)
        summary.write(idx,1,value, money if idx in (7,8) else None)
    summary.set_column('A:A',28);summary.set_column('B:B',34)
    def section(sheet,headers,data,widths,money_cols=()):
        ws=wb.get_worksheet_by_name(sheet)
        for j,h in enumerate(headers):ws.write(2,j,h,head)
        for i,row in enumerate(data,start=3):
            for j,value in enumerate(row):
                fmt=money if j in money_cols and isinstance(value,(float,int)) else None
                ws.write(i,j,value if value is not None else '',fmt)
        ws.autofilter(2,0,max(3,len(data)+2),len(headers)-1)
        ws.freeze_panes(3,0)
        for j,w in enumerate(widths):ws.set_column(j,j,w)
        ws.set_landscape();ws.fit_to_pages(1,0)
    stage_names={s['id']:s['name'] for s in stages}
    task_names={t['id']:t['title'] for t in tasks}
    section('Execução',['Órgão / Etapa','Tarefa','Descrição','Status','Prioridade','Início','Prazo','Avanço %','Orçamento R$'],[
        [stage_names.get(t['stage_id'],''),t['title'],t.get('description',''),t['status'],t['priority'],
         t.get('start_date'),t.get('due_date'),t['percent_done'],float(t['planned_cost'])] for t in tasks],
        [26,38,60,18,14,16,16,12,20], money_cols=(8,))
    section('Financeiro',['Vencimento','Descrição','Tarefa','Previsão R$','Pagamento R$','Data pagto.','Status'],[
        [e['planned_date'],e['description'],task_names.get(e['task_id'],''),float(e['planned_amount']),
         float(e['paid_amount']),e.get('paid_date'),e['status']] for e in entries],
        [17,42,42,22,22,17,15],money_cols=(3,4))
    section('Documentos',['Categoria','Arquivo','Tarefa','Tamanho bytes','Enviado em'],[
        [d['category'],d['filename'],task_names.get(d['task_id'],''),d['size_bytes'],d['uploaded_at'][:19]] for d in docs],
        [19,55,48,23,23])
    wb.close()
    return buf.getvalue()
