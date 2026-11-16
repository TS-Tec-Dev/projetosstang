# CronogramaObras Cloud · v0.1.4

Sistema de gestão de empreendimentos, documentação, projetos técnicos, cronograma físico e financeiro, anexos, equipe, relatórios e backups. Implementado em **Streamlit + Supabase PostgreSQL (Auth/RLS/Storage)**.

## Estrutura principal do cronograma

O roteiro utilizado foi elaborado a partir de um documento de referência de duas páginas. Ele passou a ser a **estrutura única padrão** de novos projetos, sem reutilizar as antigas etapas por órgãos ou mostrar o nome do documento original como módulo.

**1. Documentação:** 1.1 Matrícula (número, proprietário, área e anexos); 1.2 Proprietário do Empreendimento (nome, CNPJ, documentos); 1.3 Contratos e Consultas (locação e viabilidade: Prefeitura, Meio Ambiente, Junta Comercial).

**2. Projetos:** 2.1 Topografia (retificação sim/não); 2.2 Arquitetônico; 2.3 Hidrossanitário; 2.4 Projeto Preventivo; 2.5 Projeto Ambiental; 2.6 EIV (audiência pública sim/não); 2.7 Alvará de Construção; 2.8 Projeto de Acesso (estadual/federal/concessionária); 2.9 LAI, Condicionantes e LAO; 2.10 Habite-se (Prefeitura e Bombeiros). Em cada item técnico há ficha do profissional, orçamento, pagamento, cronograma de execução, checklist, anexos e comentários.

## Interface

- Dashboard executivo com **8 KPIs** e gráficos de status, progresso físico por área e fluxo financeiro mensal.
- Sidebar com ícones vetoriais originais em `assets/icons/`, tema corporativo claro e barra lateral em azul-petróleo.
- Portfólio de Projetos, Etapas detalhadas, Quadro de Tarefas, Gantt, Financeiro, Documentos, Equipe, Relatórios, Backups.
- Exportação gerencial em PDF/XLSX e suporte a arquivos PDF, imagens, Excel, Word, DWG/DXF, ZIP e TXT.
- Login Supabase, permissões proprietário/editor/leitor e RLS ativo.

**Nota técnica:** o limite de upload HTTP do Streamlit é 225 MB apenas para permitir restaurar ZIPs completos. Cada anexo individual continua limitado pelo código e pelo Supabase a 25 MB.

## Backup e recuperação

A aba **Backups** permite criar ZIP com registros + anexos privados para baixar, restaurar como novas cópias com IDs próprios e eliminar projetos antigos com confirmação. Sem chaves administrativas; RLS continua ativo. Perfis do Auth, permissões antigas de equipe e responsáveis de outros usuários não são importados; o usuário que restaura é o novo proprietário. Cada backup deve ser guardado fora do Streamlit.

## Implantação

Leia `ATUALIZAR_v0.1.4.md` para atualizar a instalação existente com segurança. Para instalação nova, execute `supabase/schema.sql` no Supabase, copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` localmente (não enviar ao GitHub), configure o Streamlit Cloud e rode `streamlit run app.py`.

Secrets necessários:

```toml
SUPABASE_URL = "https://SEU-PROJETO.supabase.co"
SUPABASE_ANON_KEY = "SUA_CHAVE_PUBLICA_ANON_OU_PUBLISHABLE"
```

**Importante:** senhas/chaves privadas nunca devem ir para o GitHub; não use `service_role` no Streamlit. As datas de tarefa são estimativas editáveis, não prazos oficiais de órgãos licenciadores.

## Testes locais

`python -m pytest -q`

Testes cobrem a criação do roteiro principal, estrutura documental, SVGs originais, exportadores PDF/XLSX, regras SQL e verificação de arquivo ZIP de backup. Os testes não substituem integração e testes com dados reais no Supabase.
