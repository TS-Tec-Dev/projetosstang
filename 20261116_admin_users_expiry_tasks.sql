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
