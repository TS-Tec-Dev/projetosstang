# Atualizar o CronogramaObras Cloud para v0.1.4

## Se o aplicativo v0.1.3.1 já funciona com o Supabase

1. Faça um backup dos dados atuais (antes de mudar qualquer coisa). Se a versão anterior não exporta ZIP de backup completo, exporte os relatórios e faça um backup pelo painel do banco/Storage conforme a política da empresa.
2. No repositório `TS-Tec-Dev/projetosstang`, substitua **os arquivos do código** da aplicação pelo conteúdo deste ZIP: `app.py`, pasta `src/`, `.streamlit/config.toml`, `requirements.txt`, assets e documentos de orientação. **Não envie o arquivo `secrets.toml` ao GitHub.**
3. O Supabase da v0.1.3.1 não precisa de nova migração de tabelas para este layout e a aba Backups. A nova interface utiliza os mesmos RPCs, RLS e buckets existentes.
4. Em Streamlit Community Cloud, confirme os Secrets `SUPABASE_URL` e `SUPABASE_ANON_KEY` e reinicie o aplicativo.
5. Crie um empreendimento novo. Ele terá somente a estrutura principal de 13 itens (Documentação e Projetos).
6. Para limpar os projetos antigos, vá a **Backups → Exportar backup** e baixe a cópia. Depois abra **Backups → Excluir projetos antigos**, selecione seus projetos, digite `EXCLUIR` e confirme.

**A exclusão nunca ocorre automaticamente ao atualizar o programa.** Ela é irreversível no banco e remove também arquivos Storage referenciados. Só o proprietário consegue excluir.

## Se o banco ainda não foi atualizado para a v0.1.3.1

Abra **Supabase → SQL Editor → New query** e execute `supabase/SQL_COMPLETO_SUPABASE.sql` (ou, para um banco vazio, `supabase/schema.sql`) antes de implantar o novo código. Nunca execute esse SQL no SQL Server Management Studio.

## Restaurar um backup

Na aba **Backups → Restaurar backup**, envie o ZIP de backup completo, selecione os empreendimentos e confirme a criação de novas cópias. A restauração recria tarefas, fichas, checklists, atividades, registros financeiros e anexos. Os membros antigos não são readicionados automaticamente (por segurança); adicione-os de novo em Equipe. A restauração não é um snapshot do PostgreSQL e não inclui contas/senhas do Auth.

## Limites e observações

- Arquivos por upload: 25 MB cada. Backup integral: no máximo 400 anexos e 200 MB de dados, para evitar consumo de memória na hospedagem Streamlit. Divida backups grandes por empreendimento.
- O Streamlit Cloud reinicia com frequência: **baixe o ZIP antes de sair**. Os ZIPs gerados não ficam permanentemente guardados na aplicação.
- A restauração é composta por operações autenticadas; se alguma delas falhar, o sistema tenta excluir a cópia incompleta e avisa caso a limpeza falhe. Faça sempre um teste de restauração em ambiente de homologação.
- Não copie chaves privadas nem `service_role` para Streamlit/GitHub.
- A interface e os novos backups foram testados estaticamente/localmente; não houve integração nesta entrega com seu Supabase ao vivo.
