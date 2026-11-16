"""Modelo de acompanhamento extraído de 'PROJETO X.pdf' (2 páginas).

Estrutura e nomes fielmente baseados no esboço, com campos de acompanhamento
adicionais para uso no sistema. A aplicação não presume que toda licença se aplica.
"""
from __future__ import annotations
from datetime import date, timedelta

# Campos: (chave estável, rótulo, tipo) - text, number, choice, date
DOC_SECTION = "1. DOCUMENTAÇÃO"
PROJECT_SECTION = "2. PROJETOS"

SPECIFICATIONS = [
    {"code":"1.1", "name":"Matrícula", "section":DOC_SECTION,
     "fields":[("numero","Número da matrícula","text"),("proprietario","Proprietário (nome)","text"),("area_m2","Área (m²)","number")],
     "docs":["Matrícula","Contrato Social","Documento pessoal","Cadastro Prefeitura"],
     "checklist":["Conferir matrícula do imóvel","Conferir cadastro do imóvel na Prefeitura"]},
    {"code":"1.2", "name":"Proprietário do Empreendimento", "section":DOC_SECTION,
     "fields":[("nome","Nome / razão social","text"),("cnpj","CNPJ","text")],
     "docs":["Documento pessoal","Contrato Social"],
     "checklist":["Conferir documentação do proprietário"]},
    {"code":"1.3", "name":"Contratos e Consultas", "section":DOC_SECTION,
     "fields":[("prefeitura","Consulta à Prefeitura","choice"),("meio_ambiente","Consulta ao Meio Ambiente","choice"),("junta_comercial","Consulta à Junta Comercial","choice")],
     "docs":["Contrato de Locação","Consulta de Viabilidade"],
     "checklist":["Consulta de viabilidade - Prefeitura","Consulta de viabilidade - Meio Ambiente","Consulta de viabilidade - Junta Comercial"]},
    {"code":"2.1", "name":"Topografia", "section":PROJECT_SECTION,
     "fields":[("retificacao","Necessita retificação?","yesno")],
     "docs":["Orçamento","Mapa","Nota Fiscal"], "checklist":["Levantamento topográfico","Verificar necessidade de retificação"]},
    {"code":"2.2", "name":"Arquitetônico", "section":PROJECT_SECTION,
     "docs":["Orçamento","Mapa","Nota Fiscal"], "checklist":["Elaborar projeto arquitetônico","Protocolar / acompanhar aprovação"]},
    {"code":"2.3", "name":"Hidrossanitário", "section":PROJECT_SECTION,
     "docs":["Orçamento","Mapa","Nota Fiscal"], "checklist":["Elaborar projeto hidrossanitário","Protocolar / acompanhar aprovação"]},
    {"code":"2.4", "name":"Projeto Preventivo", "section":PROJECT_SECTION,
     "docs":["Orçamento","Mapa","Nota Fiscal"], "checklist":["Elaborar projeto preventivo","Acompanhar análise do Corpo de Bombeiros"]},
    {"code":"2.5", "name":"Projeto Ambiental", "section":PROJECT_SECTION,
     "docs":["Orçamento","Mapa","Nota Fiscal"], "checklist":["Definir enquadramento ambiental","Acompanhar licenciamento aplicável"]},
    {"code":"2.6", "name":"EIV", "section":PROJECT_SECTION,
     "fields":[("audiencia_publica","Audiência pública necessária?","yesno")],
     "docs":["Orçamento","Mapa","Nota Fiscal"], "checklist":["Avaliar exigência de EIV","Conferir necessidade de audiência pública"]},
    {"code":"2.7", "name":"Alvará de Construção", "section":PROJECT_SECTION,
     "docs":["Documentos","Matrícula Atualizada","CND","Projeto Aprovado"],
     "checklist":["Reunir matrícula atualizada","Obter certidões exigidas","Anexar projetos aprovados","Acompanhar emissão do alvará"]},
    {"code":"2.8", "name":"Projeto de Acesso", "section":PROJECT_SECTION,
     "fields":[("jurisdicao","Rodovia / jurisdição","road")],
     "docs":["Orçamento","Mapa","Nota Fiscal"], "checklist":["Confirmar jurisdição estadual, federal ou concessionária","Protocolar o projeto de acesso, quando aplicável"]},
    {"code":"2.9", "name":"LAI (Condicionantes/LAO)", "section":PROJECT_SECTION,
     "fields":[("lai","Situação da LAI","choice"),("condicionantes","Condicionantes / observações","longtext"),("lao","Situação da LAO","choice")],
     "docs":["Orçamento","Mapa","Nota Fiscal"], "checklist":["Acompanhar LAI","Controlar condicionantes","Acompanhar LAO, quando aplicável"]},
    {"code":"2.10", "name":"Habite-se", "section":PROJECT_SECTION,
     "fields":[("prefeitura","Situação Prefeitura","choice"),("bombeiro","Situação Bombeiros","choice")],
     "docs":["Documentos","Comprovante"], "checklist":["Verificar documentação da Prefeitura","Verificar regularização junto aos Bombeiros"]},
]

BY_CODE = {item["code"]: item for item in SPECIFICATIONS}
DEFAULT_SECTION_NAMES = ["Documentação (PROJETO X)", "Projetos (PROJETO X)"]

# Agrupa os itens sem alterar os fluxos clássicos da v0.1.2.
SPEC_TO_STAGE = {DOC_SECTION: DEFAULT_SECTION_NAMES[0], PROJECT_SECTION: DEFAULT_SECTION_NAMES[1]}


def selected_specs(selected_stages: list[str]):
    return [s for s in SPECIFICATIONS if SPEC_TO_STAGE[s["section"]] in selected_stages]


def make_template_rows(start: date, selected_stages: list[str]):
    """Tarefas e passos do PDF, com datas meramente indicativas editáveis."""
    output = []
    for spec in selected_specs(selected_stages):
        code = spec["code"]
        major, minor = (int(x) for x in code.split("."))
        offset = (major - 1) * 45 + (minor - 1) * 8
        output.append({
            "stage_name": SPEC_TO_STAGE[spec["section"]],
            "stage_order": 0 if major == 1 else 1,
            "sort_order": minor,
            "title": f'{code} {spec["name"]}',
            "description": f'Referência ao item {code} do modelo PROJETO X. Preencha a ficha e os anexos específicos.',
            "start_date": (start + timedelta(days=offset)).isoformat(),
            "due_date": (start + timedelta(days=offset + 21)).isoformat(),
            "template_code": code,
            "checklist": list(spec.get("checklist", [])),
            "execution": (["Coletar / preparar documentação", "Revisão e validação"]
                          if major == 1 else ["Elaboração / levantamento", "Conferência / aprovação"]),
        })
    return output


def code_for_task(task: dict, details: dict | None = None):
    """Usa identificador persistido; fallback para títulos legados."""
    if details and details.get("template_code") in BY_CODE:
        return details["template_code"]
    title = (task.get("title") or "").strip()
    first = title.split(" ",1)[0]
    return first if first in BY_CODE else None


def doc_categories():
    originals = ["Orçamento", "Projeto", "Licença", "Comprovante", "Imagem", "Planilha", "Outro"]
    from_pdf = [d for spec in SPECIFICATIONS for d in spec["docs"]]
    return list(dict.fromkeys(originals + from_pdf))


def checklist_doc_status(spec: dict, documents: list[dict]):
    uploaded = {d.get('category') for d in documents}
    return [(category, category in uploaded) for category in spec['docs']]
