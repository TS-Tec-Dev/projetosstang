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
