-- CronogramaObras v0.1.9 — Permissão de exclusão KML
-- Atualização incremental. Não altera categorias, anexos ou projetos.
-- Executar somente se o SQL de exclusão KML v0.1.8 não tiver sido aplicado.
-- Pré-requisitos: funções public.my_platform_role(), public.can_edit(),
-- public.storage_project_uuid(), política RLS da plataforma já configuradas.
BEGIN;
DROP POLICY IF EXISTS "documents remove" ON public.documents;
CREATE POLICY "documents remove" ON public.documents
  FOR DELETE TO authenticated
  USING (
    public.can_edit(project_id)
    AND (
      (category IS DISTINCT FROM 'Localização KML'
       AND lower(coalesce(filename,'')) NOT LIKE '%.kml')
      OR public.my_platform_role() = 'admin'
    )
  );
DROP POLICY IF EXISTS "project object delete" ON storage.objects;
CREATE POLICY "project object delete" ON storage.objects
  FOR DELETE TO authenticated
  USING (
    bucket_id = 'project-files'
    AND public.can_edit(public.storage_project_uuid(name))
    AND (
      right(lower(name),4) <> '.kml'
      OR public.my_platform_role() = 'admin'
    )
  );
COMMIT;
NOTIFY pgrst, 'reload schema';
