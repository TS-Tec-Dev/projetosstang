# CronogramaObras Cloud

Sistema online de gestão de projetos, licenciamentos, tarefas e cronogramas, feito em **Streamlit + Supabase PostgreSQL/Auth/Storage**, pronto para ser versionado no **GitHub** e implantado no **Streamlit Community Cloud**.

> **Versão inicial (MVP)**: inclui login, projetos, fluxo-modelo de etapas, quadro de tarefas, checklist, documentos, financeiro, relatórios e colaboração. É um sistema próprio, inspirado no conceito de gestão de tarefas, **não é uma cópia do Bitrix24 nem uma integração com o Bitrix24**.


## Correção RLS — erro 42501 ao criar projeto (v0.1.1)

Se aparecer `new row violates row-level security policy for table "projects"` ao clicar em **Criar projeto e tarefas**, execute **uma vez** no **Supabase SQL Editor** o conteúdo do arquivo:

`supabase/migrations/20261111_fix_projects_rls.sql`

A política de leitura agora autoriza o proprietário diretamente, além dos membros do projeto. Isso é necessário porque o projeto é inserido com `RETURNING` e a associação automática do proprietário na tabela `project_members` depende de um trigger posterior. A alteração **não desabilita RLS** e **não remove dados**. Depois, atualize a página do Streamlit e tente novamente. Não cole o SQL no Microsoft SQL Server Management Studio.

## 1. Recursos

- Projetos por empreendimento, empresa e local, com datas de início e prazo global.
- Fluxos automáticos e editáveis: planejamento, prefeitura, Bombeiros, ambiental, acesso a rodovia estadual (SIE/SC), acesso a rodovia federal (DNIT) e execução.
- Tarefas com responsável, descrição, prioridade, status, data de início, prazo, avanço físico e orçamento previsto.
- Kanban com 5 situações; Gantt da execução; alertas de atividades atrasadas.
- Checklist e registro de comentários por tarefa.
- Cada tarefa aceita arquivos em **PDF, PNG, JPG, JPEG, WEBP, XLS, XLSX, XLSM, CSV, DOC, DOCX, DWG, DXF, ZIP ou TXT** (máximo de 25 MB/arquivo). Os arquivos ficam em Storage **privado**.
- Conclusão de tarefa exige ao menos **um anexo na categoria "Orçamento"** (regra de banco, não só da interface).
- Cronograma financeiro por atividade: vencimentos, pagamentos realizados, totais e resumo mensal.
- Exportação gerencial em **PDF** e **Excel .xlsx**, e links temporários de download dos anexos originais.
- Acesso por **proprietário**, **editor** e **leitor**, com Row Level Security (RLS) no PostgreSQL e nas operações Storage.

## 2. Estrutura do repositório

```text
CronogramaObras_Cloud/
├── app.py                           # interface Streamlit
├── src/
│   ├── db.py                        # consultas/auth Storage
│   ├── templates.py                 # fluxos de órgãos e tarefas
│   └── reports.py                   # exportação PDF e XLSX
├── supabase/schema.sql              # tabelas, funções, gatilhos, RLS e bucket
├── tests/                           # testes sem acesso à nuvem
├── examples/                        # modelos PDF e Excel de demonstração
├── INICIAR_LOCAL_WINDOWS.bat        # execução local guiada no Windows
├── .streamlit/config.toml           # aparência e limite de upload
├── .streamlit/secrets.toml.example  # modelo para credenciais
├── requirements.txt
├── .gitignore
└── README.md
```

## 3. Primeiro: criar seu Supabase

1. Crie conta/projeto no **[Supabase](https://supabase.com/dashboard)**.
2. Vá a **SQL Editor → New query**. Cole o arquivo `supabase/schema.sql` e clique em **Run** **uma vez** para inicializar as tabelas, funções e políticas. **Este script foi preparado para um projeto Supabase novo**; se já existir um banco em produção, avalie as alterações/migração antes.
3. Em **Storage**, verifique que o bucket `project-files` foi criado como **Private** e limite de 25 MB. Não torne público.
4. Em **Authentication → Providers → Email**, configure as inscrições de novos usuários. Para ambiente corporativo, restrinja cadastramento livre quando todos já tiverem conta.
5. Se a confirmação de e-mail estiver ativada, faça a confirmação antes do primeiro login. Ajuste **Authentication → URL Configuration → Site URL** para o endereço do seu app publicado.
6. Em **Project Settings / API Keys**, copie **Project URL** e **anon key / publishable key**. **Nunca copie service_role / secret key para este app!**

### Segurança

- A interface utiliza o token individual de cada usuário. A chave pública não concede acesso a dados sem o token: as regras de banco e arquivos validam a associação ao projeto.
- A chave privada `service_role` contorna as políticas RLS; **não a coloque no Streamlit**.
- O arquivo `.streamlit/secrets.toml` **não deve ir ao GitHub** (já está no `.gitignore`).
- O servidor da aplicação pode armazenar as sessões Streamlit na memória; não se utiliza cache global do cliente autenticado.
- As URLs de documentos expiram após 15 minutos; não são permanentes.
- Existe validação de extensão/tamanho, **não há antivírus nem conversão segura de arquivos** na versão inicial. Adote análise de malware, políticas de retenção e backup para uso em produção crítica.
- Os PDFs/XLSX exportados são documentos administrativos; verifique as exigências do órgão licenciador antes de protocolar qualquer material.

## 4. Rodar no computador

Requer **Python 3.12** ou superior e acesso à internet (Supabase é hospedado na nuvem).

```powershell
cd CronogramaObras_Cloud
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .streamlit\secrets.toml.example .streamlit\secrets.toml
notepad .streamlit\secrets.toml
streamlit run app.py
```

No `secrets.toml`, substitua pelos valores reais:

```toml
SUPABASE_URL = "https://seuprojeto.supabase.co"
SUPABASE_ANON_KEY = "sua_chave_publica"
```

Acesse `http://localhost:8501`. No Windows, também é possível executar **`INICIAR_LOCAL_WINDOWS.bat`**, que cria o ambiente e instala as dependências na primeira execução.

Os relatórios de demonstração ficam em `examples/` e não representam documentos reais de licenciamentos.

## 5. Criar repositório GitHub

1. Crie repositório privado chamado `cronogramaobras-cloud` em **[GitHub](https://github.com/new)**.
2. Descompacte este projeto em uma pasta local. Abra PowerShell nesta pasta.
3. Execute:

```powershell
git init
git add .
git commit -m "MVP CronogramaObras Cloud"
git branch -M main
git remote add origin https://github.com/SEU-USUARIO/cronogramaobras-cloud.git
git push -u origin main
```

Se o repositório tiver README inicial, a estratégia de push deverá ser ajustada para mesclar os históricos. Recomenda-se repositório vazio.

## 6. Publicar no Streamlit Cloud

1. Acesse **[share.streamlit.io](https://share.streamlit.io/)**, faça login com GitHub e escolha **Create app**.
2. Selecione repositório `cronogramaobras-cloud`, branch `main`, main file path `app.py`.
3. Em **Advanced settings**, selecione **Python 3.12** e configure **Secrets** com o texto de `.streamlit/secrets.toml` (URL e chave pública reais).
4. Conclua o deploy. Seu app terá um endereço como `https://seu-cronograma.streamlit.app/`.
5. Configure a URL do app em **Supabase Authentication → URL Configuration** para redirecionamentos de cadastro.
6. Crie a primeira conta, confirme por e-mail, entre e clique em **Novo projeto**.

O deploy da aplicação não cria automaticamente seu projeto Supabase: é necessário executar a etapa 3 antes. Uma aplicação criada a partir de um **repositório privado** pode exigir que os usuários sejam convidados como visualizadores do Streamlit Community Cloud. Confirme os limites de apps privados do seu plano. Este pacote **não está publicado nem conectado à sua conta**.

## 7. Como usar

**Exemplo — base operacional:**

1. Novo projeto → informe empresa, local e prazo global.
2. Marque: `Prefeitura`, `Corpo de Bombeiros`, `Ambiental`, e a opção de rodovia se necessária.
3. A plataforma criará etapas e tarefas; acesse **Quadro de tarefas**.
4. Abra **Projeto arquitetônico**; ajuste prazos, responsável, descrição e orçamento.
5. Na aba **Anexos**, marque `Orçamento` e envie a proposta em PDF/Excel.
6. Na aba **Orçamento e financeiro**, registre parcelas e vencimentos.
7. Na aba **Checklist**, registre levantamento, memória de cálculo, protocolo e exigências.
8. Atualize o percentual de execução e o status; ao tentar **Concluída**, o banco exige orçamento anexado.
9. Em **Cronograma**, acompanhe o Gantt; em **Financeiro**, as previsões e pagamentos.
10. Em **Visão geral**, baixe PDF e Excel; na **Central de documentos**, abra os anexos com links temporários.
11. Em **Equipe**, o proprietário pode adicionar por e-mail pessoas já cadastradas, atualizar a permissão e remover o acesso.

## 8. Responsabilidade técnica e parametrização dos órgãos

Os nomes e passos são **modelos gerenciais**, não um checklist regulatório exaustivo. Os requisitos concretos dependem da natureza, local, risco e impacto do empreendimento.

- **Ambiental SC**: consulte o IMA e o SINFatWeb. As modalidades de licença e a necessidade de LAP, LAI e LAO variam por enquadramento; existem modalidades alternativas. [IMA - orientações](https://in.ima.sc.gov.br/instrucaoNormativa/visualizar/331).
- **Bombeiros SC**: classifique o risco e confira os procedimentos atuais do CBMSC para PPCI, análises e vistorias. [Documentos CBMSC](https://documentoscbmsc.cbm.sc.gov.br/).
- **Rodovias estaduais SC**: SIE regulamenta faixa de domínio e acessos. [SIE - Faixa de Domínio](https://www.sie.sc.gov.br/faixa-de-dominio).
- **Rodovias federais**: DNIT disponibiliza checklists e manual de projetos de acesso. Consulte também a concessionária, se aplicável. [DNIT - normas atuais](https://www.gov.br/dnit/pt-br/rodovias/operacoes-rodoviarias/faixa-de-dominio/regulamentacao-atual/regulamentacao-atual).

## 9. Limitações da versão inicial e melhorias futuras

- **Sem publicação automatizada no GitHub**: para conectar sua conta e publicar, efetue o push indicado. O código já está estruturado para isso.
- **Sem e-mails automáticos, notificações push ou tarefas recorrentes**. Para avisos de vencimento, pode-se integrar Supabase Cron/Edge Functions e um serviço de e-mail.
- **Sem drag-and-drop no Kanban**: o status é alterado dentro da tarefa.
- **Sem dependências entre tarefas**: as datas são geridas manualmente; uma fase não bloqueia automaticamente a seguinte.
- **Sem histórico imutável de alterações das permissões**; a inclusão, alteração de função e remoção de membros são permitidas somente ao proprietário.
- **Sem trilha de auditoria imutável e workflow formal de aprovações digitais**; para utilização regulada, implementar antes de colocar em produção.
- Documentos são listados e imagens têm prévia; PDFs/Excel podem ser abertos no visualizador externo do navegador ou baixados pelo link. Não existe editor interno de Excel.
- Exclusão de projetos/tarefas via API pode deixar arquivos órfãos no Storage, pois a exclusão em cascata do banco não remove automaticamente objetos binários. Para produção, desenvolver limpeza coordenada com jobs e auditoria.
- A aplicação depende da conexão com Supabase (não possui modo offline).

## 10. Testar

```powershell
pip install -r requirements-dev.txt
python -m pytest -q
python -m py_compile app.py src\db.py src\templates.py src\reports.py
```

> Os testes incluídos validam modelos e exportadores **sem banco online**. Testes de autenticação, Storage, políticas RLS e SQL devem ser realizados em **projeto Supabase de homologação**, com usuários owner/editor/viewer antes do uso real.

---

Criado como projeto independente para adaptação e uso interno. Versão MVP 0.1.0, novembro de 2026.
