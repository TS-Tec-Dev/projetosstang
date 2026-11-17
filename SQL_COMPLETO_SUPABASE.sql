-- CronogramaObras Cloud: migracao completa para v0.1.3.1
-- Execute no SQL Editor do Supabase do aplicativo.
-- Nao desativa RLS nem apaga registros.
-- Primeiro garante RPC e esquema da v0.1.2; depois aplica ROTEIRO PADRÃO.

-- CronogramaObras Cloud v0.1.2 | criação transacional de projetos
-- Execute no SQL Editor DO MESMO Supabase usado pelo aplicativo.
-- Não remove dados nem desliga RLS.
-- A função privada SECURITY DEFINER realiza a criação numa transação.
-- O ponto de entrada público é SECURITY INVOKER, sem receber owner_id.

create schema if not exists private;

create or replace function private.create_project_workflow_impl(
    p_project jsonb,
    p_tasks jsonb
) returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_owner uuid := auth.uid();
    v_project_id uuid;
    v_stage_id uuid;
    v_row jsonb;
    v_stage_name text;
    v_title text;
    v_start date;
    v_target date;
begin
    -- Nunca aceitar owner_id fornecido pelo navegador: proprietário = JWT do Supabase.
    if v_owner is null or coalesce(auth.role(), '') <> 'authenticated' then
        raise exception 'Acesso não autenticado na API de dados. Saia da conta e entre novamente.'
            using errcode = '28000';
    end if;
    if p_project is null or jsonb_typeof(p_project) <> 'object' then
        raise exception 'Dados do projeto inválidos.';
    end if;
    v_title := btrim(coalesce(p_project->>'title', ''));
    if length(v_title) < 3 or length(v_title) > 180 then
        raise exception 'O projeto deve ter entre 3 e 180 caracteres.';
    end if;
    if p_tasks is null or jsonb_typeof(p_tasks) <> 'array'
       or jsonb_array_length(p_tasks) < 1 or jsonb_array_length(p_tasks) > 200 then
        raise exception 'Informe de 1 a 200 tarefas no fluxo inicial.';
    end if;
    v_start := coalesce(nullif(p_project->>'start_date','')::date, current_date);
    v_target := nullif(p_project->>'target_date','')::date;
    if v_target is not null and v_target < v_start then
        raise exception 'A data de conclusão não pode anteceder o início.';
    end if;

    insert into public.projects(
        owner_id,title,client_name,location,description,start_date,target_date
    ) values (
        v_owner,
        v_title,
        coalesce(p_project->>'client_name', ''),
        coalesce(p_project->>'location', ''),
        coalesce(p_project->>'description', ''),
        v_start,
        v_target
    ) returning id into v_project_id;

    -- O gatilho on_new_project_membership já adiciona o proprietário.
    -- A associação também é garantida caso o gatilho não esteja presente.
    insert into public.project_members(project_id, user_id, role)
    values (v_project_id, v_owner, 'owner')
    on conflict (project_id,user_id) do nothing;

    for v_row in select value from jsonb_array_elements(p_tasks) loop
        if jsonb_typeof(v_row) <> 'object' then
            raise exception 'Formato de tarefa inválido.';
        end if;
        v_stage_name := btrim(coalesce(v_row->>'stage_name',''));
        if length(v_stage_name) < 1 or length(v_stage_name) > 180 then
            raise exception 'Nome da etapa inválido.';
        end if;
        v_title := btrim(coalesce(v_row->>'title',''));
        if length(v_title) < 2 or length(v_title) > 200 then
            raise exception 'Título da tarefa inválido.';
        end if;
        select s.id into v_stage_id
          from public.stages s
         where s.project_id = v_project_id and s.name = v_stage_name;
        if v_stage_id is null then
            insert into public.stages(project_id,name,sort_order)
            values (v_project_id,v_stage_name,coalesce((v_row->>'stage_order')::int,0))
            returning id into v_stage_id;
        end if;
        insert into public.tasks(
            project_id,stage_id,title,description,sort_order,start_date,due_date
        ) values (
            v_project_id,
            v_stage_id,
            v_title,
            coalesce(v_row->>'description',''),
            coalesce((v_row->>'sort_order')::int,0),
            nullif(v_row->>'start_date','')::date,
            nullif(v_row->>'due_date','')::date
        );
    end loop;

    return v_project_id;
end;
$$;

revoke all on function private.create_project_workflow_impl(jsonb,jsonb) from public;
revoke all on function private.create_project_workflow_impl(jsonb,jsonb) from anon;
grant usage on schema private to authenticated;
grant execute on function private.create_project_workflow_impl(jsonb,jsonb) to authenticated;

-- Exposição mínima para client.rpc() do supabase-py.
create or replace function public.create_project_workflow(
    p_project jsonb,
    p_tasks jsonb
) returns uuid
language sql
security invoker
set search_path = ''
as $$
  select private.create_project_workflow_impl(p_project, p_tasks);
$$;

revoke all on function public.create_project_workflow(jsonb,jsonb) from public;
revoke all on function public.create_project_workflow(jsonb,jsonb) from anon;
grant execute on function public.create_project_workflow(jsonb,jsonb) to authenticated;


-- Recarregar a lista de RPCs da API após criar a função.
notify pgrst, 'reload schema';


-- Início da migração ROTEIRO PADRÃO v0.1.3.1

-- CronogramaObras Cloud v0.1.3 · modelo ROTEIRO PADRÃO.pdf
-- IMPORTANTE: execute após o SQL da versão 0.1.2, uma única vez no SQL Editor.
-- A migração é repetível e preserva projetos, usuários, anexos e cronogramas.
-- Mantém RLS ativo e o proprietário vinculado ao JWT autenticado.

begin;

-- O esquema privado e requerido pelas funcoes internas desta migracao.
-- Se a v0.1.2 ainda nao foi aplicada, execute antes:
-- supabase/migrations/20261111_atomic_project_creation.sql
create schema if not exists private;

create table if not exists public.task_details (
    task_id uuid primary key,
    project_id uuid not null,
    template_code text not null default '',
    data jsonb not null default '{}'::jsonb check (jsonb_typeof(data)='object'),
    updated_at timestamptz not null default now(),
    foreign key (task_id,project_id) references public.tasks(id,project_id) on delete cascade
);
create index if not exists ix_task_details_project on public.task_details(project_id);

create table if not exists public.execution_milestones (
    id uuid primary key default gen_random_uuid(),
    project_id uuid not null,
    task_id uuid not null,
    title text not null check(length(btrim(title)) between 1 and 200),
    start_date date not null,
    due_date date not null,
    percent_done integer not null default 0 check(percent_done between 0 and 100),
    status text not null default 'A fazer' check(status in ('A fazer','Em andamento','Concluída','Bloqueada')),
    created_at timestamptz not null default now(),
    constraint execution_dates_ok check(due_date >= start_date),
    foreign key (task_id,project_id) references public.tasks(id,project_id) on delete cascade
);
create index if not exists ix_milestones_project on public.execution_milestones(project_id,start_date);
create index if not exists ix_milestones_task on public.execution_milestones(task_id);

alter table public.task_details enable row level security;
alter table public.execution_milestones enable row level security;

-- Privilégios de tabela não substituem RLS. Acesso é controlado por projeto.
revoke all on public.task_details from anon;
revoke all on public.execution_milestones from anon;
grant select,insert,update,delete on public.task_details to authenticated;
grant select,insert,update,delete on public.execution_milestones to authenticated;

drop policy if exists "detail read" on public.task_details;
create policy "detail read" on public.task_details for select to authenticated
 using (public.is_member(project_id));
drop policy if exists "detail add" on public.task_details;
create policy "detail add" on public.task_details for insert to authenticated
 with check (public.can_edit(project_id));
drop policy if exists "detail edit" on public.task_details;
create policy "detail edit" on public.task_details for update to authenticated
 using (public.can_edit(project_id)) with check(public.can_edit(project_id));
drop policy if exists "detail remove" on public.task_details;
create policy "detail remove" on public.task_details for delete to authenticated
 using (public.can_edit(project_id));

drop policy if exists "execution read" on public.execution_milestones;
create policy "execution read" on public.execution_milestones for select to authenticated
 using (public.is_member(project_id));
drop policy if exists "execution add" on public.execution_milestones;
create policy "execution add" on public.execution_milestones for insert to authenticated
 with check (public.can_edit(project_id));
drop policy if exists "execution edit" on public.execution_milestones;
create policy "execution edit" on public.execution_milestones for update to authenticated
 using (public.can_edit(project_id)) with check(public.can_edit(project_id));
drop policy if exists "execution remove" on public.execution_milestones;
create policy "execution remove" on public.execution_milestones for delete to authenticated
 using (public.can_edit(project_id));

-- Ampliar as categorias do anexo sem perder categorias da versão anterior.
-- A regra de manter o orçamento obrigatório na conclusão continua ativa.
alter table public.documents drop constraint if exists documents_category_check;
alter table public.documents add constraint documents_category_check check (category in (
  'Orçamento','Projeto','Licença','Comprovante','Imagem','Planilha','Outro',
  'Matrícula','Contrato Social','Documento pessoal','Cadastro Prefeitura',
  'Contrato de Locação','Consulta de Viabilidade','Mapa','Nota Fiscal',
  'Documentos','Matrícula Atualizada','CND','Projeto Aprovado'
));

-- Atualiza o RPC atômico existente para registrar as fichas e os checklists.
-- Mantém a assinatura para continuar funcionando com projetos do modelo antigo.
create or replace function private.create_project_workflow_impl(
    p_project jsonb,
    p_tasks jsonb
) returns uuid
language plpgsql
security definer
set search_path = ''
as $$
declare
    v_owner uuid := auth.uid();
    v_project_id uuid;
    v_stage_id uuid;
    v_task_id uuid;
    v_check text;
    v_execution text;
    v_task_start date;
    v_task_end date;
    v_row jsonb;
    v_stage_name text;
    v_title text;
    v_start date;
    v_target date;
begin
    -- Nunca aceitar owner_id fornecido pelo navegador: proprietário = JWT do Supabase.
    if v_owner is null or coalesce(auth.role(), '') <> 'authenticated' then
        raise exception 'Acesso não autenticado na API de dados. Saia da conta e entre novamente.'
            using errcode = '28000';
    end if;
    if p_project is null or jsonb_typeof(p_project) <> 'object' then
        raise exception 'Dados do projeto inválidos.';
    end if;
    v_title := btrim(coalesce(p_project->>'title', ''));
    if length(v_title) < 3 or length(v_title) > 180 then
        raise exception 'O projeto deve ter entre 3 e 180 caracteres.';
    end if;
    if p_tasks is null or jsonb_typeof(p_tasks) <> 'array'
       or jsonb_array_length(p_tasks) < 1 or jsonb_array_length(p_tasks) > 200 then
        raise exception 'Informe de 1 a 200 tarefas no fluxo inicial.';
    end if;
    v_start := coalesce(nullif(p_project->>'start_date','')::date, current_date);
    v_target := nullif(p_project->>'target_date','')::date;
    if v_target is not null and v_target < v_start then
        raise exception 'A data de conclusão não pode anteceder o início.';
    end if;

    insert into public.projects(
        owner_id,title,client_name,location,description,start_date,target_date
    ) values (
        v_owner,
        v_title,
        coalesce(p_project->>'client_name', ''),
        coalesce(p_project->>'location', ''),
        coalesce(p_project->>'description', ''),
        v_start,
        v_target
    ) returning id into v_project_id;

    -- O gatilho on_new_project_membership já adiciona o proprietário.
    -- A associação também é garantida caso o gatilho não esteja presente.
    insert into public.project_members(project_id, user_id, role)
    values (v_project_id, v_owner, 'owner')
    on conflict (project_id,user_id) do nothing;

    for v_row in select value from jsonb_array_elements(p_tasks) loop
        if jsonb_typeof(v_row) <> 'object' then
            raise exception 'Formato de tarefa inválido.';
        end if;
        v_stage_name := btrim(coalesce(v_row->>'stage_name',''));
        if length(v_stage_name) < 1 or length(v_stage_name) > 180 then
            raise exception 'Nome da etapa inválido.';
        end if;
        v_title := btrim(coalesce(v_row->>'title',''));
        if length(v_title) < 2 or length(v_title) > 200 then
            raise exception 'Título da tarefa inválido.';
        end if;
        select s.id into v_stage_id
          from public.stages s
         where s.project_id = v_project_id and s.name = v_stage_name;
        if v_stage_id is null then
            insert into public.stages(project_id,name,sort_order)
            values (v_project_id,v_stage_name,coalesce((v_row->>'stage_order')::int,0))
            returning id into v_stage_id;
        end if;
        v_task_start := nullif(v_row->>'start_date','')::date;
        v_task_end := nullif(v_row->>'due_date','')::date;
        insert into public.tasks(
            project_id,stage_id,title,description,sort_order,start_date,due_date
        ) values (
            v_project_id,
            v_stage_id,
            v_title,
            coalesce(v_row->>'description',''),
            coalesce((v_row->>'sort_order')::int,0),
            v_task_start,
            v_task_end
        ) returning id into v_task_id;

        -- Metadados do item 1.1–2.10, na mesma transação.
        if nullif(v_row->>'template_code','') is not null then
            insert into public.task_details(project_id,task_id,template_code,data)
            values(v_project_id,v_task_id,left(v_row->>'template_code',20),'{}'::jsonb);
        end if;
        if jsonb_typeof(v_row->'checklist') = 'array' then
            for v_check in select jsonb_array_elements_text(v_row->'checklist') loop
                if length(btrim(v_check)) > 0 then
                    insert into public.task_checklist(project_id,task_id,title,sort_order)
                    values (v_project_id,v_task_id,left(btrim(v_check),300),
                        (select count(*) from public.task_checklist where task_id = v_task_id));
                end if;
            end loop;
        end if;
        if jsonb_typeof(v_row->'execution') = 'array'
           and v_task_start is not null and v_task_end is not null then
            for v_execution in select jsonb_array_elements_text(v_row->'execution') loop
                if length(btrim(v_execution)) > 0 then
                    insert into public.execution_milestones(project_id,task_id,title,start_date,due_date)
                    values(v_project_id,v_task_id,left(btrim(v_execution),200),v_task_start,v_task_end);
                end if;
            end loop;
        end if;
    end loop;

    return v_project_id;
end;
$$;


revoke all on function private.create_project_workflow_impl(jsonb,jsonb) from public,anon;
grant usage on schema private to authenticated;
grant execute on function private.create_project_workflow_impl(jsonb,jsonb) to authenticated;


-- Permite anexar o roteiro aos projetos antigos sem apagar dados.
-- Garante apenas um registro de cada código do modelo por projeto.
create unique index if not exists ux_task_details_model_code
 on public.task_details(project_id,template_code)
 where template_code <> '';

create or replace function private.add_project_x_impl(
    p_project_id uuid,
    p_tasks jsonb
) returns integer
language plpgsql security definer set search_path = ''
as $$
declare
    v_row jsonb;
    v_stage_id uuid;
    v_task_id uuid;
    v_code text;
    v_name text;
    v_title text;
    v_step text;
    v_start date;
    v_end date;
    v_added integer := 0;
begin
    if auth.uid() is null or not public.can_edit(p_project_id) then
        raise exception 'Sem permissão para editar este projeto.' using errcode = '42501';
    end if;
    if p_tasks is null or jsonb_typeof(p_tasks) <> 'array'
        or jsonb_array_length(p_tasks) > 13 then
        raise exception 'Roteiro do projeto inválido.';
    end if;
    for v_row in select value from jsonb_array_elements(p_tasks) loop
        v_code := v_row->>'template_code';
        if v_code not in ('1.1','1.2','1.3','2.1','2.2','2.3','2.4','2.5',
                          '2.6','2.7','2.8','2.9','2.10') then
            raise exception 'Código não reconhecido no modelo ROTEIRO PADRÃO.';
        end if;
        if exists(select 1 from public.task_details d
            where d.project_id = p_project_id and d.template_code = v_code) then
            continue;
        end if;
        v_name := btrim(coalesce(v_row->>'stage_name',''));
        v_title := btrim(coalesce(v_row->>'title',''));
        if length(v_name) < 1 or length(v_title) < 2 then
            raise exception 'Etapa ou título inválido.';
        end if;
        select id into v_stage_id from public.stages
            where project_id = p_project_id and name = v_name;
        if v_stage_id is null then
            insert into public.stages(project_id,name,sort_order)
            values(p_project_id,v_name,coalesce((v_row->>'stage_order')::int,0))
            returning id into v_stage_id;
        end if;
        v_start := nullif(v_row->>'start_date','')::date;
        v_end := nullif(v_row->>'due_date','')::date;
        insert into public.tasks(project_id,stage_id,title,description,
                                 sort_order,start_date,due_date)
        values(p_project_id,v_stage_id,v_title,
               coalesce(v_row->>'description',''),
               coalesce((v_row->>'sort_order')::int,0),v_start,v_end)
        returning id into v_task_id;
        insert into public.task_details(project_id,task_id,template_code,data)
            values(p_project_id,v_task_id,v_code,'{}'::jsonb);
        if jsonb_typeof(v_row->'checklist') = 'array' then
            for v_step in select jsonb_array_elements_text(v_row->'checklist') loop
                if length(btrim(v_step)) > 0 then
                    insert into public.task_checklist(project_id,task_id,title,sort_order)
                    values (p_project_id,v_task_id,left(btrim(v_step),300),
                        (select count(*) from public.task_checklist where task_id=v_task_id));
                end if;
            end loop;
        end if;
        if jsonb_typeof(v_row->'execution') = 'array'
            and v_start is not null and v_end is not null then
            for v_step in select jsonb_array_elements_text(v_row->'execution') loop
                if length(btrim(v_step)) > 0 then
                    insert into public.execution_milestones(project_id,task_id,title,start_date,due_date)
                    values(p_project_id,v_task_id,left(btrim(v_step),200),v_start,v_end);
                end if;
            end loop;
        end if;
        v_added := v_added + 1;
    end loop;
    return v_added;
end;
$$;

revoke all on function private.add_project_x_impl(uuid,jsonb) from public,anon;
grant execute on function private.add_project_x_impl(uuid,jsonb) to authenticated;

create or replace function public.add_project_x_to_existing(p_project_id uuid, p_tasks jsonb)
returns integer language sql security invoker set search_path = ''
as $$
  select private.add_project_x_impl(p_project_id,p_tasks);
$$;
revoke all on function public.add_project_x_to_existing(uuid,jsonb) from public,anon;
grant execute on function public.add_project_x_to_existing(uuid,jsonb) to authenticated;

commit;
notify pgrst, 'reload schema';


-- ==== CONTROLE DE ACESSO GLOBAL v0.1.5 ====
-- CronogramaObras Cloud v0.1.5 | Perfis globais, projetos compartilhados e KML
-- Execute UMA VEZ após v0.1.4. Idempotente, não apaga projetos/anexos.
-- ATENÇÃO: após executar, promova explicitamente um administrador no SQL Editor.
-- Nova conta começa como visualizador para evitar que usuários se auto-promovam.
BEGIN;

ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS platform_role text NOT NULL DEFAULT 'viewer';
ALTER TABLE public.profiles DROP CONSTRAINT IF EXISTS profiles_platform_role_check;
ALTER TABLE public.profiles ADD CONSTRAINT profiles_platform_role_check
  CHECK (platform_role IN ('admin','standard','viewer'));
UPDATE public.profiles SET platform_role='viewer'
  WHERE platform_role IS NULL OR platform_role NOT IN ('admin','standard','viewer');

CREATE OR REPLACE FUNCTION public.my_platform_role()
RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT coalesce((SELECT p.platform_role FROM public.profiles p WHERE p.id=auth.uid()),'viewer');
$$;
REVOKE ALL ON FUNCTION public.my_platform_role() FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.my_platform_role() TO authenticated;

-- Compatibilidade das políticas existentes. Todas as consultas continuam exigindo JWT.
-- A existência do projeto é checada para não autorizar arquivos fora de projetos válidos.
CREATE OR REPLACE FUNCTION public.is_member(p_project_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT auth.uid() IS NOT NULL AND EXISTS (SELECT 1 FROM public.projects p WHERE p.id=p_project_id);
$$;
CREATE OR REPLACE FUNCTION public.can_edit(p_project_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT auth.uid() IS NOT NULL AND public.my_platform_role() IN ('admin','standard')
    AND EXISTS(SELECT 1 FROM public.projects p WHERE p.id=p_project_id);
$$;
CREATE OR REPLACE FUNCTION public.is_owner(p_project_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT auth.uid() IS NOT NULL AND public.my_platform_role()='admin'
    AND EXISTS(SELECT 1 FROM public.projects p WHERE p.id=p_project_id);
$$;
REVOKE ALL ON FUNCTION public.is_member(uuid),public.can_edit(uuid),public.is_owner(uuid) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.is_member(uuid),public.can_edit(uuid),public.is_owner(uuid) TO authenticated;

-- Cadastro de projeto: só admin/padrão; o RPC SECURITY DEFINER também passa por este trigger.
DROP POLICY IF EXISTS "project create self" ON public.projects;
CREATE POLICY "project create self" ON public.projects FOR INSERT TO authenticated
  WITH CHECK (owner_id=auth.uid() AND public.my_platform_role() IN ('admin','standard'));
CREATE OR REPLACE FUNCTION private.prevent_viewer_project_create()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
  IF auth.uid() IS NULL OR public.my_platform_role() NOT IN ('admin','standard') THEN
    RAISE EXCEPTION 'Seu perfil não permite criar empreendimentos.' USING errcode='42501';
  END IF;
  IF NEW.owner_id IS DISTINCT FROM auth.uid() THEN
    RAISE EXCEPTION 'Proprietário deve ser o usuário autenticado.' USING errcode='42501';
  END IF;
  RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS check_platform_project_create ON public.projects;
CREATE TRIGGER check_platform_project_create BEFORE INSERT ON public.projects
  FOR EACH ROW EXECUTE FUNCTION private.prevent_viewer_project_create();

-- Projetos e anexos ficam visíveis aos autenticados; RLS nunca é desativado.
-- As políticas de leitura de etapas/finanças/documentos/Storage já chamam is_member().
DROP POLICY IF EXISTS "project read members" ON public.projects;
CREATE POLICY "project read members" ON public.projects FOR SELECT TO authenticated
  USING (auth.uid() IS NOT NULL);
DROP POLICY IF EXISTS "project edit" ON public.projects;
CREATE POLICY "project edit" ON public.projects FOR UPDATE TO authenticated
  USING (public.can_edit(id)) WITH CHECK (public.can_edit(id));
DROP POLICY IF EXISTS "project delete owner" ON public.projects;
CREATE POLICY "project delete owner" ON public.projects FOR DELETE TO authenticated
  USING (public.is_owner(id));
DROP POLICY IF EXISTS "comments add" ON public.task_comments;
CREATE POLICY "comments add" ON public.task_comments FOR INSERT TO authenticated
  WITH CHECK (public.can_edit(project_id) AND author_id=auth.uid());

-- Perfis: cada usuário vê o seu; administradores veem e gerenciam todos os perfis.
DROP POLICY IF EXISTS "profile self/shared" ON public.profiles;
CREATE POLICY "profile self/shared" ON public.profiles FOR SELECT TO authenticated
  USING (id=auth.uid() OR public.my_platform_role()='admin');
REVOKE INSERT,UPDATE,DELETE ON public.profiles FROM authenticated;
GRANT SELECT ON public.profiles TO authenticated;

CREATE OR REPLACE FUNCTION public.admin_set_user_role(p_user_id uuid, p_role text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
BEGIN
  IF auth.uid() IS NULL OR public.my_platform_role()<>'admin' THEN
    RAISE EXCEPTION 'Somente administradores podem alterar perfis.' USING errcode='42501';
  END IF;
  IF p_role NOT IN ('admin','standard','viewer') THEN
    RAISE EXCEPTION 'Perfil inválido.';
  END IF;
  -- Não permitir que o último administrador perca o perfil administrativo.
  IF p_user_id=auth.uid() AND p_role<>'admin' THEN
    RAISE EXCEPTION 'Um administrador não pode rebaixar a própria conta.';
  END IF;
  UPDATE public.profiles SET platform_role=p_role WHERE id=p_user_id;
  IF NOT FOUND THEN RAISE EXCEPTION 'Usuário não encontrado.'; END IF;
  RETURN 'Perfil atualizado.';
END;
$$;
REVOKE ALL ON FUNCTION public.admin_set_user_role(uuid,text) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.admin_set_user_role(uuid,text) TO authenticated;

-- Diretório público aos usuários autenticados sem expor e-mails de outros usuários.
CREATE OR REPLACE FUNCTION public.team_directory()
RETURNS TABLE(user_id uuid,full_name text,platform_role text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT p.id,coalesce(nullif(p.full_name,''),'Colaborador'),p.platform_role
  FROM public.profiles p WHERE auth.uid() IS NOT NULL ORDER BY p.full_name,p.id;
$$;
REVOKE ALL ON FUNCTION public.team_directory() FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.team_directory() TO authenticated;

-- A categoria de KML fica associada à matrícula no armazenamento privado.
ALTER TABLE public.documents DROP CONSTRAINT IF EXISTS documents_category_check;
ALTER TABLE public.documents ADD CONSTRAINT documents_category_check CHECK (category IN (
 'Orçamento','Projeto','Licença','Comprovante','Imagem','Planilha','Outro',
 'Matrícula','Contrato Social','Documento pessoal','Cadastro Prefeitura',
 'Contrato de Locação','Consulta de Viabilidade','Mapa','Nota Fiscal',
 'Documentos','Matrícula Atualizada','CND','Projeto Aprovado','Localização KML'
));

-- Somente renomeia rótulos antigos. Não elimina dados, etapas ou anexos.
UPDATE public.stages s SET name='Documentação'
  WHERE name='Documentação (PROJETO X)'
    AND NOT EXISTS(SELECT 1 FROM public.stages x WHERE x.project_id=s.project_id AND x.name='Documentação');
UPDATE public.stages s SET name='Projetos'
  WHERE name='Projetos (PROJETO X)'
    AND NOT EXISTS(SELECT 1 FROM public.stages x WHERE x.project_id=s.project_id AND x.name='Projetos');

-- Nome técnico neutro para a operação de completar etapas.
CREATE OR REPLACE FUNCTION public.add_missing_workflow_steps(p_project_id uuid,p_tasks jsonb)
RETURNS integer LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$
  SELECT public.add_project_x_to_existing(p_project_id,p_tasks);
$$;
REVOKE ALL ON FUNCTION public.add_missing_workflow_steps(uuid,jsonb) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.add_missing_workflow_steps(uuid,jsonb) TO authenticated;

COMMIT;
NOTIFY pgrst,'reload schema';


-- Atualização v0.1.6 incluída para novas instalações
-- v0.1.6: contas administradas, prazo de acesso e edição/exclusão de tarefas pelo Admin.
-- Pré-requisito: v0.1.5 instalada. Execute no SQL Editor com papel postgres.
-- NÃO remove usuários, projetos, senhas ou arquivos. RLS permanece ligado.
BEGIN;

ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS account_enabled boolean NOT NULL DEFAULT true;
ALTER TABLE public.profiles ADD COLUMN IF NOT EXISTS account_expires_at timestamptz NULL;

-- Contas vitalícias usam account_expires_at = NULL; contas vencidas e desativadas
-- são bloqueadas em RLS, mesmo se ainda possuírem token JWT válido.
CREATE OR REPLACE FUNCTION public.account_is_active()
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT auth.uid() IS NOT NULL AND EXISTS (
    SELECT 1 FROM public.profiles p
    WHERE p.id = auth.uid() AND p.account_enabled
      AND (p.account_expires_at IS NULL OR p.account_expires_at > now())
  );
$$;
REVOKE ALL ON FUNCTION public.account_is_active() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.account_is_active() TO authenticated;

CREATE OR REPLACE FUNCTION public.my_account_access()
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT jsonb_build_object(
    'role', p.platform_role,
    'active', (p.account_enabled AND (p.account_expires_at IS NULL OR p.account_expires_at > now())),
    'expires_at', p.account_expires_at,
    'enabled', p.account_enabled
  ) FROM public.profiles p WHERE p.id = auth.uid()
$$;
REVOKE ALL ON FUNCTION public.my_account_access() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.my_account_access() TO authenticated;

CREATE OR REPLACE FUNCTION public.my_platform_role()
RETURNS text LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT CASE WHEN public.account_is_active()
    THEN COALESCE((SELECT p.platform_role FROM public.profiles p WHERE p.id=auth.uid()),'viewer')
    ELSE 'viewer' END
$$;
REVOKE ALL ON FUNCTION public.my_platform_role() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.my_platform_role() TO authenticated;

-- Recalcula as permissões globais, mantendo acesso multiempreendimento.
CREATE OR REPLACE FUNCTION public.is_member(p_project_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT public.account_is_active() AND EXISTS (
    SELECT 1 FROM public.projects p WHERE p.id = p_project_id
  );
$$;
CREATE OR REPLACE FUNCTION public.can_edit(p_project_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT public.account_is_active() AND public.my_platform_role() IN ('admin','standard')
    AND EXISTS (SELECT 1 FROM public.projects p WHERE p.id = p_project_id);
$$;
CREATE OR REPLACE FUNCTION public.is_owner(p_project_id uuid)
RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT public.account_is_active() AND public.my_platform_role() = 'admin'
    AND EXISTS (SELECT 1 FROM public.projects p WHERE p.id = p_project_id);
$$;
REVOKE ALL ON FUNCTION public.is_member(uuid), public.can_edit(uuid), public.is_owner(uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_member(uuid), public.can_edit(uuid), public.is_owner(uuid) TO authenticated;

-- Somente Administrador pode alterar/excluir tarefas. Padrão pode criar tarefas
-- e manter financeiros/documentos, sem alterar dados da tarefa principal.
DROP POLICY IF EXISTS "task edit" ON public.tasks;
CREATE POLICY "task edit" ON public.tasks FOR UPDATE TO authenticated
  USING (public.is_owner(project_id)) WITH CHECK (public.is_owner(project_id));
DROP POLICY IF EXISTS "task remove" ON public.tasks;
CREATE POLICY "task remove" ON public.tasks FOR DELETE TO authenticated
  USING (public.is_owner(project_id));
DROP POLICY IF EXISTS "stage edit" ON public.stages;
CREATE POLICY "stage edit" ON public.stages FOR UPDATE TO authenticated
  USING (public.is_owner(project_id)) WITH CHECK (public.is_owner(project_id));
DROP POLICY IF EXISTS "stage remove" ON public.stages;
CREATE POLICY "stage remove" ON public.stages FOR DELETE TO authenticated
  USING (public.is_owner(project_id));

-- Fichas técnicas, passos e marcos são partes da tarefa: edição restrita ao Admin.
DROP POLICY IF EXISTS "detail add" ON public.task_details;
CREATE POLICY "detail add" ON public.task_details FOR INSERT TO authenticated WITH CHECK (public.is_owner(project_id));
DROP POLICY IF EXISTS "detail edit" ON public.task_details;
CREATE POLICY "detail edit" ON public.task_details FOR UPDATE TO authenticated USING (public.is_owner(project_id)) WITH CHECK(public.is_owner(project_id));
DROP POLICY IF EXISTS "detail remove" ON public.task_details;
CREATE POLICY "detail remove" ON public.task_details FOR DELETE TO authenticated USING (public.is_owner(project_id));
DROP POLICY IF EXISTS "execution add" ON public.execution_milestones;
CREATE POLICY "execution add" ON public.execution_milestones FOR INSERT TO authenticated WITH CHECK(public.is_owner(project_id));
DROP POLICY IF EXISTS "execution edit" ON public.execution_milestones;
CREATE POLICY "execution edit" ON public.execution_milestones FOR UPDATE TO authenticated USING(public.is_owner(project_id)) WITH CHECK(public.is_owner(project_id));
DROP POLICY IF EXISTS "execution remove" ON public.execution_milestones;
CREATE POLICY "execution remove" ON public.execution_milestones FOR DELETE TO authenticated USING(public.is_owner(project_id));
DROP POLICY IF EXISTS "checklist add" ON public.task_checklist;
CREATE POLICY "checklist add" ON public.task_checklist FOR INSERT TO authenticated WITH CHECK(public.is_owner(project_id));
DROP POLICY IF EXISTS "checklist edit" ON public.task_checklist;
CREATE POLICY "checklist edit" ON public.task_checklist FOR UPDATE TO authenticated USING(public.is_owner(project_id)) WITH CHECK(public.is_owner(project_id));
DROP POLICY IF EXISTS "checklist remove" ON public.task_checklist;
CREATE POLICY "checklist remove" ON public.task_checklist FOR DELETE TO authenticated USING(public.is_owner(project_id));

-- RLS por usuário ativo em todas as consultas sensíveis, inclusive storage.
DROP POLICY IF EXISTS "project read members" ON public.projects;
CREATE POLICY "project read members" ON public.projects FOR SELECT TO authenticated
  USING(public.account_is_active());
DROP POLICY IF EXISTS "project create self" ON public.projects;
CREATE POLICY "project create self" ON public.projects FOR INSERT TO authenticated
  WITH CHECK(owner_id=auth.uid() AND public.account_is_active() AND public.my_platform_role() IN ('admin','standard'));
DROP POLICY IF EXISTS "profile self/shared" ON public.profiles;
CREATE POLICY "profile self/shared" ON public.profiles FOR SELECT TO authenticated
  USING(public.account_is_active() AND (id=auth.uid() OR public.my_platform_role()='admin'));
DROP POLICY IF EXISTS "membership read" ON public.project_members;
CREATE POLICY "membership read" ON public.project_members FOR SELECT TO authenticated
  USING(public.is_member(project_id));
DROP POLICY IF EXISTS "project object read" ON storage.objects;
CREATE POLICY "project object read" ON storage.objects FOR SELECT TO authenticated
  USING(bucket_id='project-files' AND public.is_member(public.storage_project_uuid(name)));
DROP POLICY IF EXISTS "project object insert" ON storage.objects;
CREATE POLICY "project object insert" ON storage.objects FOR INSERT TO authenticated
  WITH CHECK(bucket_id='project-files' AND public.can_edit(public.storage_project_uuid(name)));
DROP POLICY IF EXISTS "project object delete" ON storage.objects;
CREATE POLICY "project object delete" ON storage.objects FOR DELETE TO authenticated
  USING(bucket_id='project-files' AND public.can_edit(public.storage_project_uuid(name)));

-- Diretório para usuários ativos, listado sem senhas.
CREATE OR REPLACE FUNCTION public.team_directory()
RETURNS TABLE(user_id uuid,full_name text,platform_role text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = '' AS $$
  SELECT p.id,coalesce(nullif(p.full_name,''),'Colaborador'),p.platform_role
  FROM public.profiles p WHERE public.account_is_active() ORDER BY p.full_name,p.id;
$$;
REVOKE ALL ON FUNCTION public.team_directory() FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.team_directory() TO authenticated;

-- A exclusão é transacional: não deixa uma tarefa parcialmente apagada.
-- O status é liberado para que o trigger 'último orçamento' não bloqueie
-- a exclusão de arquivos pertencentes a uma tarefa concluída.
CREATE OR REPLACE FUNCTION public.admin_delete_workflow_task(p_task_id uuid)
RETURNS text[] LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE
  v_project_id uuid;
  v_paths text[];
BEGIN
  SELECT t.project_id INTO v_project_id FROM public.tasks t WHERE t.id=p_task_id FOR UPDATE;
  IF v_project_id IS NULL THEN RAISE EXCEPTION 'Tarefa não encontrada.'; END IF;
  IF NOT public.is_owner(v_project_id) THEN
    RAISE EXCEPTION 'Somente administradores podem excluir tarefas.' USING errcode='42501';
  END IF;
  SELECT COALESCE(array_agg(d.storage_path),ARRAY[]::text[])
    INTO v_paths FROM public.documents d WHERE d.task_id=p_task_id;
  UPDATE public.tasks SET status='A fazer', percent_done=0 WHERE id=p_task_id;
  DELETE FROM public.tasks WHERE id=p_task_id;
  RETURN v_paths;
END;
$$;
REVOKE ALL ON FUNCTION public.admin_delete_workflow_task(uuid) FROM PUBLIC,anon;
GRANT EXECUTE ON FUNCTION public.admin_delete_workflow_task(uuid) TO authenticated;

COMMIT;
NOTIFY pgrst,'reload schema';

-- ==== 20261117_kml_satellite_admin_delete ===
-- CronogramaObras Cloud v0.1.8 | KML: exclusão somente administrador.
-- Migração incremental e idempotente. Não apaga documentos ou empreendimentos.
-- Pressupõe que a migração de perfis globais da v0.1.5 já foi executada.
BEGIN;

DROP POLICY IF EXISTS "documents remove" ON public.documents;
CREATE POLICY "documents remove" ON public.documents
FOR DELETE TO authenticated
USING (
    public.can_edit(project_id)
    AND (
        (
            category <> 'Localização KML'
            AND lower(filename) NOT LIKE '%.kml'
        )
        OR public.my_platform_role() = 'admin'
    )
);

-- Proteção também no arquivo do bucket privado: uma chamada direta à
-- Storage API não pode apagar KMLs com perfil padrão/visualizador.
DROP POLICY IF EXISTS "project object delete" ON storage.objects;
CREATE POLICY "project object delete" ON storage.objects
FOR DELETE TO authenticated
USING (
    bucket_id = 'project-files'
    AND public.can_edit(public.storage_project_uuid(name))
    AND (
        right(lower(name), 4) <> '.kml'
        OR public.my_platform_role() = 'admin'
    )
);

COMMIT;
NOTIFY pgrst, 'reload schema';
