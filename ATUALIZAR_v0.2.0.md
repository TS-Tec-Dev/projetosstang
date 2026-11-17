# CronogramaObras Cloud v0.2.0 — Atualização incremental

## Alterações

1. **Orçamento opcional para concluir uma tarefa**: removidos o aviso e o bloqueio na interface. O orçamento continua disponível como anexo sugerido e como valor financeiro.
2. **Removida a guia Execução** do painel de cada tarefa. A aba geral **Cronograma** continua disponível, incluindo Gantt e atividades registradas.
3. **Datas brasileiras**: resumos, tabelas e relatórios mostram `DD/MM/AA` (ex.: `17/11/26`). Os seletores nativos do Streamlit mostram `DD/MM/AAAA`, pois essa é a forma brasileira disponível no widget (ex.: `17/11/2026`). Os dados continuam gravados no Supabase em ISO `YYYY-MM-DD`, evitando incompatibilidades.

## Implantação no Streamlit / GitHub

1. **Faça um backup** pelo menu Backups antes de atualizar.
2. No Supabase, execute **somente** `supabase/migrations/20261117_v020_budget_optional.sql` no SQL Editor. O script remove dois gatilhos antigos que obrigavam manter um anexo de orçamento, sem alterar documentos, categorias, usuários ou políticas RLS.
3. Envie os arquivos atualizados ao repositório GitHub `TS-Tec-Dev/projetosstang` (ou somente os arquivos do ZIP de atualização) mantendo o arquivo principal `app.py`.
4. Reinicie o Streamlit e faça `Ctrl + F5` no navegador. Verifique no menu lateral o texto `Versão 0.2.0`.
5. Como administrador, abra uma tarefa sem orçamento, altere o status para `Concluída` e salve. Verifique a guia **Execução** ausente, a aba global **Cronograma** e as datas.

**Não rode o SQL completo antigo**: ele pode recriar restrições de categorias de documentos de versões anteriores. Use somente a migração incremental indicada.

### Arquivos de aplicação alterados
- `app.py`: remove o bloqueio, a aba Execução e formata datas da interface.
- `src/workflow_ui.py`: substitui o acesso direto à guia Execução por navegação à aba Cronograma e marca anexos como sugeridos.
- `src/utils.py`: formatação textual de datas `DD/MM/AA`.
- `src/reports.py`: datas dos relatórios.
- `src/admin_ui.py`: validade exibida com ano de dois dígitos.
- `src/db.py` e `src/backups.py`: comentários técnicos coerentes com a nova regra.
- `supabase/schema.sql` e `supabase/SQL_COMPLETO_SUPABASE.sql`: compatibilidade para instalações futuras.

**Validação**: testes locais de código e relatórios; a migração ainda não foi executada no banco Supabase real.
