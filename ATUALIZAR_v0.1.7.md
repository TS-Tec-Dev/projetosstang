# CronogramaObras Cloud v0.1.7 — correção de seletor e administração

## O que esta atualização corrige

1. **Empreendimento ativo:** o seletor agora utiliza **fundo azul-petróleo escuro e texto branco**, inclusive no Streamlit que já não usa o mecanismo BaseWeb antigo. O rótulo legível abaixo do seletor foi preservado.
2. **Administrar usuários:** a v0.1.6 exibia a mensagem genérica “Não foi possível acessar a administração” para erros HTTP retornados como `{"code":401,"message":"Invalid JWT"}`. A versão nova mostra o **status HTTP e o motivo**.
3. **Autenticação da Edge Function:** `supabase/config.toml` define `verify_jwt = false` para contornar a verificação JWT legada do gateway Supabase, que pode não aceitar tokens de projetos com chaves novas. **Isso não remove a autenticação do aplicativo.** O código `admin-users/index.ts` exige token de usuário validado com `auth.getUser(token)` e confirma o papel **Administrador ativo** via `my_account_access()` *antes* de usar o cliente de serviço. Jamais retire essas validações.
4. **Diagnóstico:** a tela Administrar usuários apresenta o botão **Testar disponibilidade da Edge Function** se a listagem falhar. Uma chamada `GET /functions/v1/admin-users` pode retornar `{"status":"online","function":"admin-users","version":"0.1.7"}`. Não retorna contas ou dados privados.

## Atualização segura (não apaga nenhum empreendimento)

**Antes:** faça backup pela aba Backups, caso seu sistema esteja funcionando. Não altere `SUPABASE_URL` ou `SUPABASE_ANON_KEY` se já estão corretas. Não publique chaves privadas ou o arquivo `.streamlit/secrets.toml` no GitHub.

### 1. Atualizar os arquivos no GitHub

Envie para `TS-Tec-Dev/projetosstang` os arquivos do ZIP completo, substituindo a versão antiga, ou utilize somente o pacote PATCH com os seguintes caminhos preservados:

- `src/ui.py`
- `src/admin_api.py`
- `src/admin_ui.py`
- `supabase/functions/admin-users/index.ts`
- `supabase/config.toml`
- `app.py`

Atualizar **somente o Streamlit não publica a função Supabase**. Os próximos passos são indispensáveis.

### 2. Atualizar a Edge Function no Supabase

**Via painel:** Supabase Dashboard → **Edge Functions → admin-users → Code**. Substitua pelo conteúdo de `supabase/functions/admin-users/index.ts` e publique (Deploy). Em **Details/Settings**, **DESATIVE** a opção **Verify JWT with legacy secret**. Esse toggle é a verificação antiga do gateway; a própria função continuará checando o token e a autorização com o Supabase Auth. Confira também **Edge Functions → Logs** se uma falha continuar.

**Ou via CLI**, na pasta do projeto com `supabase login` e `supabase link` já feitos:

```bash
supabase functions deploy admin-users --no-verify-jwt
```

O `--no-verify-jwt` corresponde à configuração `verify_jwt = false` de `supabase/config.toml`.

**Importante:** confirme que a função utiliza as variáveis de ambiente do Supabase (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` e `SUPABASE_ANON_KEY` ou `SUPABASE_PUBLISHABLE_KEY`). A chave de serviço jamais vai ao GitHub ou aos Secrets do Streamlit.

### 3. Reiniciar Streamlit

Reinicie o aplicativo e atualize a página com **Ctrl + F5**. O texto do seletor deve estar branco em fundo escuro.

### 4. Testar a função

Entre como administrador e abra **Administrar usuários**. Se falhar, clique em **Testar disponibilidade da Edge Function**.

- **HTTP 401 / Invalid JWT:** a verificação JWT legada provavelmente continua ligada, ou a função antiga não foi republicada. Verifique o toggle e a versão do código.
- **HTTP 404:** a função `admin-users` não está publicada no projeto correto.
- **HTTP 403:** confira o perfil **Administrador** e se a conta está ativa e dentro da validade.
- **HTTP 500 / 503:** abra os Logs da função e confira sua configuração interna; o aplicativo não deve receber chaves secretas.
- **Função online, versão 0.1.7:** a rota existe. Se `list` ainda falhar, confira os logs e a autorização da conta.

Não existe necessidade de executar novamente `schema.sql` ou qualquer SQL completo para resolver apenas esses dois problemas **se a migração v0.1.6 já foi executada com sucesso**.

### 5. Confirmar permissões

Administrador: cria/edita contas e gerencia tarefas. Padrão: cria tarefas sem editar/excluir tarefas anteriores. Visualizador: consulta e baixa arquivos. A função nova NÃO disponibiliza operações administrativas a visitantes anônimos; elas exigem token validado e administrador ativo.

## Testes

Foram executados testes locais de regressão (27 aprovados), compilação dos arquivos Python e verificação do ZIP. **Não foi possível validar o deploy remoto ou testar com a conta real no Supabase nesta sessão.**
