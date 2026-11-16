"""Pequeno design system próprio: SVGs vetoriais originais e cards acessíveis."""
from html import escape

INK = '#123041'
TEAL = '#087F80'
# Símbolos vetoriais próprios, sem fonte externa ou imagens hospedadas.
_PATHS = {
 'dashboard':'<rect x="3" y="3" width="8" height="8" rx="2"/><rect x="13" y="3" width="8" height="5" rx="2"/><rect x="13" y="10" width="8" height="11" rx="2"/><rect x="3" y="13" width="8" height="8" rx="2"/>',
 'folder':'<path d="M3 8V6a2 2 0 0 1 2-2h5l2.2 2.4H19a2 2 0 0 1 2 2V19a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 10h18"/>',
 'check':'<rect x="3" y="4" width="18" height="17" rx="3"/><path d="M8 10l2 2 4-4M8 17h8"/>',
 'calendar':'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v5m10-5v5M3 10h18m-13 5h3m3 0h3"/>',
 'wallet':'<rect x="3" y="6" width="18" height="15" rx="3"/><path d="M7 6V4h12M16 13h5m-5 3h5"/><circle cx="16" cy="14.5" r=".5" fill="currentColor"/>',
 'files':'<path d="M7 3h9l5 5v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"/><path d="M15 3v6h6M9 13h8M9 17h8"/>',
 'people':'<circle cx="9" cy="8" r="3"/><path d="M3 21v-2a6 6 0 0 1 12 0v2M17 6a3 3 0 0 1 0 6m2 9v-2a5 5 0 0 0-3-4.6"/>',
 'chart':'<path d="M3 21V4M3 21h18M7 17v-5m5 5V7m5 10v-8" stroke-width="3" stroke-linecap="round"/>',
 'backup':'<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M12 13v6m-3-3 3 3 3-3M8 3h8"/>',
 'alert':'<path d="m12 3 10 18H2L12 3Z"/><path d="M12 9v5m0 3v.1"/>',
 'progress':'<circle cx="12" cy="12" r="9"/><path d="M12 12 19 7M12 12v-8"/>',
 'map':'<path d="M3 5 9 3l6 2 6-2v16l-6 2-6-2-6 2V5Z"/><path d="M9 3v16m6-14v16"/>',
 'building':'<path d="M4 21V6l8-3 8 3v15H4Z"/><path d="M9 8h1m4 0h1M9 12h1m4 0h1M9 16h1m4 0h1M10 21v-4h4v4"/>',
}

def icon(name, color=TEAL, size=22):
    return (f'<svg width="{int(size)}" height="{int(size)}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{escape(color,quote=True)}" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true">{_PATHS.get(name,_PATHS["dashboard"])}</svg>')

def metric_card(label, value, kind='chart', note='', tone='teal'):
    cls='co-metric '+('co-danger' if tone=='danger' else 'co-gold' if tone=='gold' else '')
    return (f'<div class="{cls}"><div class="co-metric-head"><span>{escape(label)}</span>'
            f'{icon(kind)}</div><div class="co-metric-number">{escape(str(value))}</div>'
            f'<div class="co-metric-foot">{escape(note or "Indicador atualizado")}</div></div>')

CSS = """
<style>
:root{--co-ink:#143143;--co-teal:#087F80;--co-soft:#e8f6f4;--co-border:#dce8ed;}
.block-container{padding-top:1.25rem!important;max-width:1620px!important;padding-bottom:3rem!important;}
[data-testid="stAppViewContainer"]{background:linear-gradient(165deg,#f4f8fa 0%,#eef5f6 100%);}
[data-testid="stSidebar"]{background:#102935!important;border-right:1px solid #244353!important;}
[data-testid="stSidebar"] *{color:#eaf5f7!important;}
/* Contraste do seletor de empreendimento: fundo claro + textos escuros (inclusive lista flutuante). */
[data-testid="stSidebar"] [data-baseweb="select"]>div{background-color:#f8fcff!important;border:1px solid #9db6c2!important;}
[data-testid="stSidebar"] [data-baseweb="select"] input,
[data-testid="stSidebar"] [data-baseweb="select"] span,
[data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"],
[data-testid="stSidebar"] [data-baseweb="select"] [role="combobox"] *{color:#143143!important;-webkit-text-fill-color:#143143!important;}
[data-baseweb="popover"] [role="listbox"],
[data-baseweb="popover"] [role="option"]{background:#f8fbfd!important;color:#143143!important;}
[data-baseweb="popover"] [role="option"] *{color:#143143!important;-webkit-text-fill-color:#143143!important;}
[data-baseweb="popover"] [role="option"]:hover{background:#d8ecee!important;}
[data-testid="stSidebar"] [data-baseweb="select"] svg{fill:#173e50!important;}
[data-testid="stSidebar"] .stButton button{background:transparent!important;border:1px solid transparent!important;min-height:40px;text-align:left!important;justify-content:flex-start!important;border-radius:10px!important;}
[data-testid="stSidebar"] .stButton button:hover{background:#234956!important;border-color:#345965!important;}
[data-testid="stSidebar"] .stButton button[kind="primary"]{background:#0b817e!important;border-color:#22a5a1!important;}
h1,h2,h3{color:#143143!important;letter-spacing:-.025em!important;}
h1{font-size:2.1rem!important;font-weight:760!important;}
h2{font-size:1.53rem!important;}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--co-border);padding:14px;border-radius:15px;}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:16px!important;border-color:var(--co-border)!important;background:#fff;}
[data-testid="stPlotlyChart"]{background:#fff;border:1px solid var(--co-border);padding:8px;border-radius:17px;}
[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:14px;}
[data-testid="stTabs"] button[role="tab"]{font-size:.92rem;font-weight:650;}
.stButton button, .stDownloadButton button{border-radius:10px!important;min-height:39px!important;font-weight:650!important;}
.stButton button[kind="primary"],.stDownloadButton button[kind="primary"]{background:var(--co-teal)!important;border-color:var(--co-teal)!important;color:#fff!important;}
.co-banner{display:flex;gap:20px;align-items:center;background:linear-gradient(110deg,#0f2d3d,#12676b);color:#fff!important;border-radius:20px;padding:24px 28px;margin-bottom:18px;box-shadow:0 8px 24px #12304113;}
.co-banner h1{margin:0!important;color:#fff!important;font-size:1.75rem!important;}
.co-banner p{margin:5px 0 0;color:#c7e6e8!important;font-size:.88rem;}
.co-kpi-row{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin:15px 0 20px;}
.co-metric{border:1px solid var(--co-border);background:#fff;border-radius:17px;padding:18px 19px;min-width:0;box-shadow:0 4px 20px #163a4210;}
.co-metric-head{display:flex;align-items:center;justify-content:space-between;color:#647b88;font-size:.81rem;font-weight:700;gap:10px;}
.co-metric-number{font-size:1.67rem;font-weight:800;color:var(--co-ink);margin:10px 0 4px;letter-spacing:-.03em;white-space:normal;overflow-wrap:anywhere;}
.co-metric-foot{font-size:.76rem;color:#78909a;}
.co-danger .co-metric-head svg{stroke:#cb5461}.co-gold .co-metric-head svg{stroke:#c98b27}
.co-section{font-size:1rem;font-weight:800;letter-spacing:-.01em;color:#183849;margin:16px 0 10px;}
.co-eyebrow{font-size:.73rem;letter-spacing:.09em;text-transform:uppercase;font-weight:750;color:#168784;}
.co-stage-tag{background:#e6f4f3;border:1px solid #cae6e4;border-radius:8px;padding:4px 9px;color:#0e7572;font-size:.75rem;}
@media(max-width:1100px){.co-kpi-row{grid-template-columns:repeat(2,minmax(0,1fr));}}
@media(max-width:620px){.co-kpi-row{grid-template-columns:repeat(1,minmax(0,1fr));}.co-banner{padding:18px;}}
</style>
"""
