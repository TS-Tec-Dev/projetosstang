> **v0.1.6**: siga [ATUALIZAR_v0.1.6.md](ATUALIZAR_v0.1.6.md). A criação e gestão de contas usa a Edge Function `admin-users`.

# CronogramaObras Cloud v0.1.6 — Administração de usuários

Sistema Streamlit + Supabase. O roteiro de implantação segue as seções **Documentação (1.1 a 1.3)** e **Projetos Técnicos (2.1 a 2.10)**, com painel gerencial, Gantt, custos, tarefas, anexos, equipe, relatórios e backup. A interface não usa o nome do documento que originou o roteiro.

## Alterações desta versão

- **1.0 Localização do empreendimento:** antes de 1.1 Matrícula, anexar KML do Google Earth (até 10 MB), visualizar pontos, linhas e polígonos no mapa e abrir/baixar o original. O KML fica arquivado como documento privado vinculado à Matrícula; arquivos com recursos não suportados continuam disponíveis para abrir no Google Earth.
- **Navegação:** removida a aba Projetos; selecionar o empreendimento apenas em **Empreendimento ativo**, com cores de texto e de fundo corrigidas. Novo empreendimento tem botão separado para Administradores e usuários Padrão.
- **Compartilhamento:** todos os usuários autenticados veem todos os projetos, suas etapas, tarefas e documentos; o repositório GitHub não recebe arquivos do Supabase.
- **Perfis globais:** Administrador (cria, edita, define funções de usuários, restaura backups e exclui qualquer projeto); Padrão (cria, edita, envia anexos); Visualizador (somente leitura, mapa, relatórios e download de anexos). **A partir da v0.1.6, novas contas são criadas pelo Administrador** (não existe autoinscrição pela interface).
- **Segurança:** o RLS permanece ativo no banco e no Storage privado; os botões também respeitam as permissões. Chaves privadas/service_role não fazem parte do aplicativo.
- **Backups:** exportação, restauração e exclusão somente para administradores. Antes de excluir, baixe e confira uma cópia de segurança.

## Atualizar instalação existente (passo a passo)

1. Faça download do backup completo **na versão atual** antes da atualização, se possível.
2. Supabase → **SQL Editor**: execute `supabase/migrations/20261116_global_roles_kml.sql`. Não execute `schema.sql` sobre o banco existente apenas para aplicar esta versão. O script não apaga tabelas/projetos.
3. **Obrigatório:** atribua o primeiro administrador manualmente no SQL Editor usando `supabase/PRIMEIRO_ADMINISTRADOR.sql`. Substitua `SEU_EMAIL_CADASTRADO@EXEMPLO.COM` pelo e-mail real da conta já criada e confira o resultado. **Até fazer isso, todos os usuários existentes terão nível Visualizador** (por segurança).
4. GitHub: atualize o código do repositório `TS-Tec-Dev/projetosstang` com os arquivos deste ZIP. **Não envie `.streamlit/secrets.toml`**.
5. Streamlit: Secrets continuam com `SUPABASE_URL` e `SUPABASE_ANON_KEY`; faça Reboot e entre novamente.
6. Em **Administrar usuários**, o Administrador cadastra usuários, define níveis de acesso e vencimentos. Em **Backups**, o Administrador tem a opção de excluir qualquer projeto com confirmação.

### Primeira instalação

Execute **somente** `supabase/schema.sql` (que já inclui a migração global) e depois `supabase/PRIMEIRO_ADMINISTRADOR.sql`. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` local, não publique secrets no GitHub. Inicie `streamlit run app.py`.

### Segurança e limites

- O acesso compartilhado significa que **todos os usuários autenticados** conseguem ver projetos e arquivos. Cadastros no Supabase devem ser controlados pela organização. Se não quiser permitir autoinscrição, desative o cadastro público no painel **Authentication** e convide contas por processo administrativo.
- Backup completo contém informações e anexos; guarde seus ZIPs em local protegido. Visualizadores podem baixar anexos conforme solicitado.
- KML: somente `.kml`, não `.kmz`; o visualizador interno mostra geometria simples, não conteúdo 3D, modelos e overlays. O original pode ser aberto no Google Earth.
- Tabelas, documentos e usuários existentes não são excluídos pela migração. Rótulos antigos de etapas são normalizados quando não houver conflito de nomes.
- Não foi executado teste integrado no banco Supabase real. Valide as três permissões usando contas separadas após implantação.

### Verificação local

`python -m pytest -q`
