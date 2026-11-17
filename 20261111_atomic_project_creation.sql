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
