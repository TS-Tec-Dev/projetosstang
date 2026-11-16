# Atualização v0.1.5

## Atualizar instalação existente (passo a passo)

1. Faça download do backup completo **na versão atual** antes da atualização, se possível.
2. Supabase → **SQL Editor**: execute `supabase/migrations/20261116_global_roles_kml.sql`. Não execute `schema.sql` sobre o banco existente apenas para aplicar esta versão. O script não apaga tabelas/projetos.
3. **Obrigatório:** atribua o primeiro administrador manualmente no SQL Editor usando `supabase/PRIMEIRO_ADMINISTRADOR.sql`. Substitua `SEU_EMAIL_CADASTRADO@EXEMPLO.COM` pelo e-mail real da conta já criada e confira o resultado. **Até fazer isso, todos os usuários existentes terão nível Visualizador** (por segurança).
4. GitHub: atualize o código do repositório `TS-Tec-Dev/projetosstang` com os arquivos deste ZIP. **Não envie `.streamlit/secrets.toml`**.
5. Streamlit: Secrets continuam com `SUPABASE_URL` e `SUPABASE_ANON_KEY`; faça Reboot e entre novamente.
6. Em **Equipe**, o Administrador define outros administradores, usuários Padrão ou Visualizadores. Em **Backups**, o Administrador tem a opção de excluir qualquer projeto com confirmação.

### Primeira instalação

Execute **somente** `supabase/schema.sql` (que já inclui a migração global) e depois `supabase/PRIMEIRO_ADMINISTRADOR.sql`. Copie `.streamlit/secrets.toml.example` para `.streamlit/secrets.toml` local, não publique secrets no GitHub. Inicie `streamlit run app.py`.



Veja README.md para limites e segurança.