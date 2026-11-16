-- CronogramaObras Cloud v0.1.3 · modelo PROJETO X.pdf
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
            raise exception 'Código não reconhecido no modelo PROJETO X.';
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
