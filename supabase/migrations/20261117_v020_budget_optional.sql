-- CronogramaObras Cloud v0.2.0: orçamentos opcionais na conclusão de tarefas.
-- Atualização INCREMENTAL para o banco atual. Não exclui tarefas, documentos ou usuários.
-- Executar no Supabase → SQL Editor, uma única vez (idempotente).
BEGIN;

DROP TRIGGER IF EXISTS task_require_budget ON public.tasks;
DROP TRIGGER IF EXISTS document_keep_budget ON public.documents;

-- As funções antigas só implementavam a exigência removida.
DROP FUNCTION IF EXISTS public.require_budget_document();
DROP FUNCTION IF EXISTS public.keep_final_budget();

COMMIT;
