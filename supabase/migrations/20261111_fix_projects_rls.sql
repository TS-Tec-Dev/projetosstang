-- CronogramaObras Cloud | correção de RLS para criação de projetos
-- Execute no SQL Editor do MESMO projeto Supabase usado pelo Streamlit.
-- Mantém RLS habilitado; não apaga tabelas, projetos ou documentos.
-- A leitura precisa permitir o dono ainda antes do trigger AFTER INSERT
-- preencher a tabela project_members (INSERT ... RETURNING).

drop policy if exists "project read members" on public.projects;
create policy "project read members" on public.projects
  for select to authenticated
  using (owner_id=(select auth.uid()) or public.is_member(id));

drop policy if exists "project create self" on public.projects;
create policy "project create self" on public.projects
  for insert to authenticated
  with check (owner_id=(select auth.uid()));
