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
