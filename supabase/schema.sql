-- CronogramaObras Cloud | executar no Supabase SQL Editor como administrador.
-- Projeto novo ou migração inicial. Não cole chaves secretas aqui.
create extension if not exists pgcrypto;

create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text not null,
  full_name text not null default '',
  created_at timestamptz not null default now()
);
create unique index if not exists ux_profiles_email on public.profiles (lower(email));

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id),
  title text not null check (length(trim(title)) between 3 and 180),
  client_name text not null default '',
  location text not null default '',
  description text not null default '',
  start_date date not null default current_date,
  target_date date,
  created_at timestamptz not null default now()
);
create table if not exists public.project_members (
  project_id uuid not null references public.projects(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  role text not null check (role in ('owner','editor','viewer')),
  created_at timestamptz not null default now(),
  primary key(project_id, user_id)
);
create index if not exists ix_members_user on public.project_members(user_id);

create table if not exists public.stages (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  name text not null,
  sort_order int not null default 0,
  created_at timestamptz not null default now(),
  unique (project_id,name), unique (id,project_id)
);
create table if not exists public.tasks (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references public.projects(id) on delete cascade,
  stage_id uuid not null,
  title text not null check (length(trim(title)) between 2 and 200),
  description text not null default '',
  status text not null default 'A fazer'
    check (status in ('A fazer','Em andamento','Em aprovação','Concluída','Bloqueada')),
  priority text not null default 'Normal' check (priority in ('Baixa','Normal','Alta','Urgente')),
  responsible_id uuid references auth.users(id) on delete set null,
  start_date date,
  due_date date,
  planned_cost numeric(14,2) not null default 0 check (planned_cost >= 0),
  percent_done int not null default 0 check (percent_done between 0 and 100),
  sort_order int not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id,project_id),
  foreign key (stage_id,project_id) references public.stages (id,project_id)
);
create index if not exists ix_tasks_project_status on public.tasks(project_id,status);
create index if not exists ix_tasks_due_date on public.tasks(due_date);

create table if not exists public.task_checklist (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null,
  task_id uuid not null,
  title text not null,
  completed boolean not null default false,
  sort_order int not null default 0,
  created_at timestamptz not null default now(),
  foreign key (task_id,project_id) references public.tasks (id,project_id) on delete cascade
);
create table if not exists public.finance_entries (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null,
  task_id uuid not null,
  description text not null,
  planned_date date not null,
  planned_amount numeric(14,2) not null default 0 check (planned_amount >= 0),
  paid_date date,
  paid_amount numeric(14,2) not null default 0 check (paid_amount >= 0),
  status text not null default 'Previsto' check(status in ('Previsto','Pago')),
  created_at timestamptz not null default now(),
  foreign key (task_id,project_id) references public.tasks (id,project_id) on delete cascade,
  check (status <> 'Pago' or paid_date is not null)
);
create index if not exists ix_finance_project_date on public.finance_entries(project_id,planned_date);

create table if not exists public.documents (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null,
  task_id uuid not null,
  uploaded_by uuid not null references auth.users(id),
  category text not null check (category in ('Orçamento','Projeto','Licença','Comprovante','Imagem','Planilha','Outro')),
  filename text not null,
  storage_path text not null unique,
  content_type text not null,
  size_bytes bigint not null check (size_bytes between 1 and 26214400),
  uploaded_at timestamptz not null default now(),
  foreign key (task_id,project_id) references public.tasks (id,project_id) on delete cascade
);
create index if not exists ix_documents_task on public.documents(task_id);

create table if not exists public.task_comments (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null,
  task_id uuid not null,
  author_id uuid not null references auth.users(id),
  content text not null check (length(trim(content)) between 1 and 2000),
  created_at timestamptz not null default now(),
  foreign key (task_id,project_id) references public.tasks (id,project_id) on delete cascade
);

-- Funções SECURITY DEFINER usadas para quebrar ciclos de políticas de associação.
create or replace function public.is_member(p_project_id uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.project_members pm
    where pm.project_id = p_project_id and pm.user_id = (select auth.uid())
  );
$$;
create or replace function public.can_edit(p_project_id uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.project_members pm
    where pm.project_id = p_project_id
      and pm.user_id = (select auth.uid()) and pm.role in ('owner','editor')
  );
$$;
create or replace function public.is_owner(p_project_id uuid)
returns boolean language sql stable security definer set search_path = '' as $$
  select exists (
    select 1 from public.projects p
    where p.id = p_project_id and p.owner_id = (select auth.uid())
  );
$$;

create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id,email,full_name)
  values (new.id,coalesce(new.email,''),coalesce(new.raw_user_meta_data->>'full_name',''))
  on conflict (id) do update set email=excluded.email;
  return new;
end;
$$;
drop trigger if exists on_auth_user_created_project_app on auth.users;
create trigger on_auth_user_created_project_app
  after insert on auth.users for each row execute procedure public.handle_new_user();
insert into public.profiles(id,email,full_name)
select id,coalesce(email,''),coalesce(raw_user_meta_data->>'full_name','')
from auth.users where email is not null
on conflict (id) do nothing;

create or replace function public.handle_new_project()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into public.project_members(project_id,user_id,role)
  values(new.id,new.owner_id,'owner');
  return new;
end;
$$;
drop trigger if exists on_new_project_membership on public.projects;
create trigger on_new_project_membership
  after insert on public.projects for each row execute procedure public.handle_new_project();

create or replace function public.protect_project_owner()
returns trigger language plpgsql set search_path = '' as $$
begin
  if new.owner_id is distinct from old.owner_id or new.id is distinct from old.id then
    raise exception 'Proprietário e identificador do projeto não podem ser alterados.';
  end if;
  return new;
end;
$$;
drop trigger if exists project_owner_protected on public.projects;
create trigger project_owner_protected before update on public.projects
  for each row execute procedure public.protect_project_owner();

create or replace function public.touch_task()
returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at = now();
  if new.status = 'Concluída' then new.percent_done = 100; end if;
  return new;
end;
$$;
drop trigger if exists task_touched on public.tasks;
create trigger task_touched before update on public.tasks
  for each row execute procedure public.touch_task();

-- A conclusão de uma tarefa requer um orçamento anexado, inclusive se chamada pela API.
create or replace function public.require_budget_document()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if new.status = 'Concluída' and (tg_op = 'INSERT' or old.status is distinct from 'Concluída')
     and not exists (select 1 from public.documents d where d.task_id = new.id and d.category = 'Orçamento') then
    raise exception 'Anexe pelo menos um documento de orçamento antes de concluir a tarefa.';
  end if;
  return new;
end;
$$;
drop trigger if exists task_require_budget on public.tasks;
create trigger task_require_budget before insert or update on public.tasks
  for each row execute procedure public.require_budget_document();

-- Impede apagar o último orçamento de tarefa já concluída.
create or replace function public.keep_final_budget()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
  if old.category = 'Orçamento' and exists (select 1 from public.tasks t where t.id=old.task_id and t.status='Concluída')
    and not exists (select 1 from public.documents d where d.task_id=old.task_id and d.id <> old.id and d.category='Orçamento') then
    raise exception 'Uma tarefa concluída deve manter um orçamento anexado.';
  end if;
  return old;
end;
$$;
drop trigger if exists document_keep_budget on public.documents;
create trigger document_keep_budget before delete on public.documents
  for each row execute procedure public.keep_final_budget();

-- Função de inclusão controlada: somente proprietário adiciona usuário já cadastrado.
create or replace function public.add_project_member(p_project_id uuid, p_email text, p_role text)
returns text language plpgsql security definer set search_path = '' as $$
declare v_user_id uuid;
begin
  if not public.is_owner(p_project_id) then raise exception 'Sem permissão.'; end if;
  if p_role not in ('editor','viewer') then raise exception 'Perfil de acesso inválido.'; end if;
  select p.id into v_user_id from public.profiles p where lower(p.email) = lower(trim(p_email)) limit 1;
  if v_user_id is null then raise exception 'Usuário não cadastrado. Solicite que se registre no sistema.'; end if;
  if v_user_id = (select auth.uid()) then raise exception 'O proprietário já é membro.'; end if;
  insert into public.project_members(project_id,user_id,role)
  values(p_project_id,v_user_id,p_role)
  on conflict (project_id,user_id) do update set role=excluded.role;
  return 'Colaborador adicionado ou atualizado.';
end;
$$;

-- Privacidade: nenhuma tabela deve ficar pública por engano.
alter table public.profiles enable row level security;
alter table public.projects enable row level security;
alter table public.project_members enable row level security;
alter table public.stages enable row level security;
alter table public.tasks enable row level security;
alter table public.task_checklist enable row level security;
alter table public.finance_entries enable row level security;
alter table public.documents enable row level security;
alter table public.task_comments enable row level security;

drop policy if exists "profile self/shared" on public.profiles;
create policy "profile self/shared" on public.profiles for select to authenticated
 using (id=(select auth.uid()) or exists (
   select 1 from public.project_members pm
   where pm.user_id=profiles.id and public.is_member(pm.project_id)
 ));
drop policy if exists "project read members" on public.projects;
create policy "project read members" on public.projects for select to authenticated
 -- A associação project_members surge em um trigger AFTER INSERT.
 -- INSERT ... RETURNING precisa ler a linha antes dessa associação ficar visível;
 -- por isso o proprietário também deve ter permissão direta de SELECT.
 using (owner_id=(select auth.uid()) or public.is_member(id));
drop policy if exists "project create self" on public.projects;
create policy "project create self" on public.projects for insert to authenticated
 with check(owner_id=(select auth.uid()));
drop policy if exists "project edit" on public.projects;
create policy "project edit" on public.projects for update to authenticated
 using(public.can_edit(id)) with check (public.can_edit(id));
drop policy if exists "project delete owner" on public.projects;
create policy "project delete owner" on public.projects for delete to authenticated
 using(public.is_owner(id));
drop policy if exists "membership read" on public.project_members;
create policy "membership read" on public.project_members for select to authenticated
 using(public.is_member(project_id));
drop policy if exists "membership remove owner" on public.project_members;
create policy "membership remove owner" on public.project_members for delete to authenticated
 using(public.is_owner(project_id) and role <> 'owner');

drop policy if exists "stage read" on public.stages;
create policy "stage read" on public.stages for select to authenticated using(public.is_member(project_id));
drop policy if exists "stage add" on public.stages;
create policy "stage add" on public.stages for insert to authenticated with check(public.can_edit(project_id));
drop policy if exists "stage edit" on public.stages;
create policy "stage edit" on public.stages for update to authenticated using(public.can_edit(project_id)) with check(public.can_edit(project_id));
drop policy if exists "stage remove" on public.stages;
create policy "stage remove" on public.stages for delete to authenticated using(public.can_edit(project_id));
drop policy if exists "task read" on public.tasks;
create policy "task read" on public.tasks for select to authenticated using(public.is_member(project_id));
drop policy if exists "task add" on public.tasks;
create policy "task add" on public.tasks for insert to authenticated with check(public.can_edit(project_id));
drop policy if exists "task edit" on public.tasks;
create policy "task edit" on public.tasks for update to authenticated using(public.can_edit(project_id)) with check(public.can_edit(project_id));
drop policy if exists "task remove" on public.tasks;
create policy "task remove" on public.tasks for delete to authenticated using(public.can_edit(project_id));
drop policy if exists "checklist read" on public.task_checklist;
create policy "checklist read" on public.task_checklist for select to authenticated using(public.is_member(project_id));
drop policy if exists "checklist add" on public.task_checklist;
create policy "checklist add" on public.task_checklist for insert to authenticated with check(public.can_edit(project_id));
drop policy if exists "checklist edit" on public.task_checklist;
create policy "checklist edit" on public.task_checklist for update to authenticated using(public.can_edit(project_id)) with check(public.can_edit(project_id));
drop policy if exists "checklist remove" on public.task_checklist;
create policy "checklist remove" on public.task_checklist for delete to authenticated using(public.can_edit(project_id));
drop policy if exists "finance read" on public.finance_entries;
create policy "finance read" on public.finance_entries for select to authenticated using(public.is_member(project_id));
drop policy if exists "finance add" on public.finance_entries;
create policy "finance add" on public.finance_entries for insert to authenticated with check(public.can_edit(project_id));
drop policy if exists "finance edit" on public.finance_entries;
create policy "finance edit" on public.finance_entries for update to authenticated using(public.can_edit(project_id)) with check(public.can_edit(project_id));
drop policy if exists "finance remove" on public.finance_entries;
create policy "finance remove" on public.finance_entries for delete to authenticated using(public.can_edit(project_id));
drop policy if exists "documents read" on public.documents;
create policy "documents read" on public.documents for select to authenticated using(public.is_member(project_id));
drop policy if exists "documents add" on public.documents;
create policy "documents add" on public.documents for insert to authenticated
 with check(public.can_edit(project_id) and uploaded_by=(select auth.uid())
   and storage_path like project_id::text || '/' || task_id::text || '/%');
drop policy if exists "documents remove" on public.documents;
create policy "documents remove" on public.documents for delete to authenticated using(public.can_edit(project_id));
drop policy if exists "comments read" on public.task_comments;
create policy "comments read" on public.task_comments for select to authenticated using(public.is_member(project_id));
drop policy if exists "comments add" on public.task_comments;
create policy "comments add" on public.task_comments for insert to authenticated
 with check(public.is_member(project_id) and author_id=(select auth.uid()));

-- Bucket privado com tamanho máximo 25MB e URLs temporárias.
insert into storage.buckets(id,name,public,file_size_limit)
values('project-files','project-files',false,26214400)
on conflict (id) do update set public=false,file_size_limit=26214400;
create or replace function public.storage_project_uuid(p_path text)
returns uuid language sql immutable set search_path = '' as $$
  select case when split_part(p_path,'/',1) ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    then split_part(p_path,'/',1)::uuid else null end;
$$;
drop policy if exists "project object read" on storage.objects;
create policy "project object read" on storage.objects for select to authenticated
 using(bucket_id='project-files' and public.is_member(public.storage_project_uuid(name)));
drop policy if exists "project object insert" on storage.objects;
create policy "project object insert" on storage.objects for insert to authenticated
 with check(bucket_id='project-files' and public.can_edit(public.storage_project_uuid(name)));
drop policy if exists "project object delete" on storage.objects;
create policy "project object delete" on storage.objects for delete to authenticated
 using(bucket_id='project-files' and public.can_edit(public.storage_project_uuid(name)));

revoke all on public.profiles, public.projects, public.project_members, public.stages,
 public.tasks, public.task_checklist, public.finance_entries, public.documents, public.task_comments from anon;
grant select,insert,update,delete on public.profiles, public.projects, public.project_members,
 public.stages, public.tasks, public.task_checklist, public.finance_entries,
 public.documents, public.task_comments to authenticated;
revoke all on function public.add_project_member(uuid,text,text) from public;
grant execute on function public.add_project_member(uuid,text,text) to authenticated;


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


notify pgrst, 'reload schema';


-- =================== MODELO ROTEIRO PADRÃO (v0.1.3) ===================
-- CronogramaObras Cloud v0.1.3 · modelo ROTEIRO PADRÃO.pdf
-- IMPORTANTE: execute após o SQL da versão 0.1.2, uma única vez no SQL Editor.
-- A migração é repetível e preserva projetos, usuários, anexos e cronogramas.
-- Mantém RLS ativo e o proprietário vinculado ao JWT autenticado.

begin;

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



-- ==== ACESSO COMPARTILHADO E KML v0.1.5 ====
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
