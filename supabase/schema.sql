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
