# Atualização CronogramaObras Cloud v0.1.6 — administração de usuários

Esta atualização corrige a leitura do nome do **Empreendimento ativo**, remove o cadastro público e restringe edição e exclusão de tarefas ao Administrador. Não apaga projetos, anexos, senhas, cronogramas ou contas existentes.

## Antes de atualizar

1. Entre como administrador na versão atual e gere um **backup ZIP completo**. Guarde a cópia em local seguro.
2. Confirme que a v0.1.5 e o administrador inicial estão ativos. Não execute `schema.sql` no banco existente para fazer apenas essa atualização.

## 1. SQL da migração (obrigatório)

Abra o **Supabase Dashboard → SQL Editor → New query** e execute todo o conteúdo do arquivo:

`supabase/migrations/20261116_admin_users_expiry_tasks.sql`

O SQL:
- adiciona `profiles.account_enabled` e `profiles.account_expires_at` (NULL = acesso vitalício);
- fornece `my_account_access()` e `account_is_active()`;
- atualiza RLS para bloquear a conta desativada/vencida de projetos, etapas e arquivos privados;
- restringe **UPDATE/DELETE** em tarefas e edição de fichas/checklists/marcos ao Administrador;
- acrescenta o RPC `admin_delete_workflow_task()` com exclusão transacional.

Uma conta com validade vencida ainda poderá obter token do Supabase Auth, mas o **Streamlit recusará sua entrada e o RLS bloqueará todos os dados e anexos**, mesmo que um token antigo persista. Links de arquivo assinados anteriormente permanecem válidos até a própria expiração (na aplicação, normalmente 15 minutos).

## 2. Publicar a Edge Function (obrigatório para criar/editar usuários)

A criação de usuários do Supabase Auth exige privilégio de servidor. Por isso foi criada a Edge Function **admin-users**. O arquivo `supabase/functions/admin-users/index.ts` contém o código. Sua chave de serviço fica somente no Supabase, **nunca** no Streamlit ou GitHub.

Via Supabase CLI (com o projeto já conectado):

```bash
supabase login
supabase link --project-ref REF_DO_SEU_PROJETO
supabase functions deploy admin-users
```

O arquivo `supabase/config.toml` já mantém `verify_jwt = true`. A função confere o JWT do usuário e se seu perfil está ativo e é Administrador **antes** de usar a API administrativa do Supabase. Nos projetos com chaves novas, confira as variáveis de ambiente padrão da Edge Function (`SUPABASE_URL`, `SUPABASE_ANON_KEY` ou `SUPABASE_PUBLISHABLE_KEY`, e `SUPABASE_SERVICE_ROLE_KEY`). A chave de serviço é configurada **somente no ambiente da função**.

Alternativa: no painel Supabase, abra **Edge Functions**, crie uma função `admin-users` e use o conteúdo de `index.ts`, mantendo a verificação JWT ativada. Confirme que o deploy aparece como ativo.

Se `admin-users` ainda não estiver publicada, o login e a visualização de empreendimentos funcionam, mas a tela de administração informará que precisa da função.

## 3. Desabilitar cadastro público no Supabase

No painel Supabase, abra **Authentication → Providers → Email** (ou **Sign In / Providers** conforme a versão) e **desative a opção que permite novos cadastros públicos**. A interface Streamlit não oferece mais “Criar conta”; porém, para impedir inscrições por chamada direta da API, também é importante bloquear o cadastro público no Supabase. A função administrativa continua podendo criar contas pelo serviço autorizado.

## 4. Atualizar Streamlit / GitHub

- Envie os arquivos deste ZIP ao repositório GitHub, preservando sua configuração de Secrets no Streamlit. **Não publique `.streamlit/secrets.toml`**.
- No Streamlit, mantenha `SUPABASE_URL` e `SUPABASE_ANON_KEY`; **não acrescente service_role**.
- Reinicie o aplicativo.

## 5. Utilização

- Na tela **Entrar**, existe o botão **Administrar usuários**. Clique e entre com uma conta Administrador; ele abre a central administrativa. O menu lateral também contém **Administrar usuários**, visível apenas aos Administradores.
- Cadastro: nome, e-mail, senha inicial (mínimo 10 caracteres), nível (**Administrador / Padrão / Visualizador**) e validade (**Vitalício** ou **Com vencimento**).
- Edição de contas: alterar nível, nome, ativar/desativar, mudar validade/vitalício. Contas existentes são mantidas; nenhum prazo é colocado automaticamente (por padrão todas são vitalícias).
- Selecione o empreendimento no menu lateral. Um rótulo de alto contraste abaixo da caixa garante a visualização do nome mesmo se o navegador aplicar estilos à caixa de seleção.
- Na aba **Etapas** somente o Administrador vê **Editar tarefa** e **Excluir tarefa**. A exclusão exige confirmação explícita e remove dados vinculados. Gere backup antes.
- Padrão segue podendo incluir tarefas, movimentar finanças e enviar documentos, mas **não pode editar nem excluir tarefas existentes**. Visualizador apenas consulta e baixa arquivos.

## Testar após instalar

Teste com três contas: (1) Administrador vê, edita e exclui tarefa; (2) Padrão vê e cria, mas não edita/exclui tarefa; (3) Visualizador não modifica. Teste depois um usuário vencido ou desativado: o login deve ser recusado e o acesso a dados/Storage negado. Teste um usuário vitalício e uma troca de vencimento. Verifique o contraste do empreendimento ativo.

**Validação local**: compilação Python, sintaxe da função TypeScript e testes de estrutura. A conexão ao Supabase real deve ser validada no ambiente publicado. Sem apagar nenhum projeto nesta atualização.
