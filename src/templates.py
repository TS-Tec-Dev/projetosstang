"""Modelos configuráveis de etapas. Não substituem a análise técnica dos órgãos."""
from datetime import date, timedelta

# Seções aparecem no quadro conforme o escopo marcado na abertura do projeto.
WORKFLOWS = {
    "Planejamento": [
        ("Levantamento e viabilidade técnica", "Identificar localização, parâmetros urbanísticos, matrícula, sondagens e condicionantes."),
        ("Orçamento geral e contratação dos projetistas", "Receber propostas, comparar escopo e formalizar contratação técnica."),
    ],
    "Prefeitura": [
        ("Projeto arquitetônico", "Elaborar projeto arquitetônico, memorial, plantas e ART/RRT aplicável."),
        ("Projeto hidrossanitário", "Elaborar redes de água, esgoto, drenagem e demais memoriais/ART/RRT aplicáveis."),
        ("Protocolo dos projetos na Prefeitura", "Reunir requisitos municipais, taxas e comprovante de protocolo."),
        ("Exigências e aprovação municipal", "Responder diligências e anexar parecer/alvará ou aprovação emitida."),
    ],
    "Corpo de Bombeiros": [
        ("Levantamento de requisitos de incêndio", "Verificar enquadramento, ocupação, risco e medidas de segurança aplicáveis."),
        ("Projeto preventivo contra incêndio (PPCI)", "Elaborar PPCI, plantas, memoriais, ART/RRT e demais elementos exigidos."),
        ("Análise e aprovação do PPCI", "Protocolar, acompanhar exigências e anexar comprovante de aprovação."),
        ("Execução das medidas e vistoria", "Executar medidas aprovadas e acompanhar vistoria, quando aplicável."),
    ],
    "Ambiental": [
        ("Enquadramento e estudos ambientais", "Confirmar órgão competente, modalidade e estudos exigidos para o empreendimento."),
        ("LAP - Licença Ambiental Prévia", "Preparar estudos e documentos, protocolar e acompanhar a etapa prévia, se aplicável."),
        ("LAI - Licença Ambiental de Instalação", "Protocolar o pedido e acompanhar condicionantes, se aplicável."),
        ("LAO - Licença Ambiental de Operação", "Preparar requerimento de operação e comprovação de condicionantes, se aplicável."),
    ],
    "Acesso rodovia estadual": [
        ("Consulta e viabilidade de acesso - SIE", "Consultar faixa de domínio e documentação estadual, verificar viabilidade e taxas."),
        ("Topografia e projeto de acesso - SC", "Elaborar levantamento, projeto de geometria, drenagem, sinalização e ART aplicável."),
        ("Protocolo e análise do acesso - SIE", "Protocolar projeto, atender exigências e arquivar aprovação."),
        ("Autorização e execução do acesso - SC", "Obter autorização e executar conforme projeto aprovado e fiscalização."),
    ],
    "Acesso rodovia federal": [
        ("Consulta e viabilidade de acesso - DNIT", "Consultar faixa de domínio e regulamentação atual; confirmar titularidade/concessão."),
        ("Projeto técnico do acesso - DNIT", "Elaborar estudos e projeto de engenharia de acesso com responsabilidade técnica."),
        ("Protocolo e análise do acesso - DNIT", "Encaminhar documentação, acompanhar análise e atender exigências."),
        ("Autorização e execução do acesso - BR", "Obter autorização antes de intervir; executar segundo as condições aprovadas."),
    ],
    "Execução": [
        ("Cronograma executivo e mobilização", "Detalhar frentes de obra, responsáveis, medições e marcos de entrega."),
        ("Execução e medições de serviços", "Acompanhar avanço físico, registrar evidências, medições e custos realizados."),
        ("Comissionamento e entrega final", "Conferir pendências, laudos, aprovações e documentos de encerramento."),
    ],
}

DEFAULT_WORKFLOW = ["Planejamento", "Prefeitura", "Corpo de Bombeiros", "Ambiental", "Execução"]


def generate_template(start: date, selected: list[str]) -> list[dict]:
    """Distribui tarefas em datas iniciais editáveis; não infere prazos oficiais."""
    out = []
    for stage_index, stage_name in enumerate(selected):
        for task_index, (title, description) in enumerate(WORKFLOWS[stage_name]):
            offset = stage_index * 12 + task_index * 7
            out.append({
                "stage_name": stage_name,
                "stage_order": stage_index,
                "sort_order": task_index,
                "title": title,
                "description": description,
                "start_date": (start + timedelta(days=offset)).isoformat(),
                "due_date": (start + timedelta(days=offset + 14)).isoformat(),
            })
    return out
