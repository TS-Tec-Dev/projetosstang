# Atualização CronogramaObras Cloud v0.1.3 — roteiro PROJETO X

A versão mantém o MVP v0.1.2 (autenticação, equipe, quadro Kanban, cronograma geral, lançamentos financeiros, armazenamento privado e relatórios PDF/Excel). A nova página **Plano PROJETO X** reproduz a ordem e os campos de `PROJETO X.pdf`, fornecido como referência.

## 1. Atualizar o banco EXISTENTE no Supabase

1. Acesse o projeto correto no Supabase e abra **SQL Editor → New query**.
2. Cole o conteúdo integral de `supabase/migrations/20261116_projeto_x.sql` e clique em **Run**.
3. Confira as novas tabelas `task_details` e `execution_milestones` em **Database → Tables**.
4. Não use SQL Server Management Studio. Este arquivo é para **PostgreSQL do Supabase**.
5. A migração não remove projetos, tarefas, anexos, senhas ou usuários. O RLS permanece habilitado.

**IMPORTANTE:** se o banco não recebeu a v0.1.2, execute também `supabase/migrations/20261111_atomic_project_creation.sql` antes desta migração. Para um banco Supabase inteiramente novo, execute somente `supabase/schema.sql` (contém tudo, inclusive v0.1.3).

## 2. Publicar os códigos atualizados

- No repositório GitHub existente `TS-Tec-Dev/projetosstang`, substitua `app.py`, `src/`, `supabase/schema.sql`, `supabase/migrations/` e `README.md`. **Não apague as credenciais do Streamlit.**
- Inclua os arquivos novos `src/project_x.py`, `src/project_x_ui.py` e `supabase/migrations/20261116_projeto_x.sql`.
- Não envie `.streamlit/secrets.toml` ou arquivos `.env` para o GitHub.
- Faça **Reboot app** no Streamlit Community Cloud e, se necessário, saia e entre novamente. Verifique na barra lateral `v0.1.3 PROJETO X`.

Os arquivos a publicar estão todos dentro deste ZIP; não publique apenas o arquivo SQL sem atualizar também o Python.

## 3. Usar o roteiro anexado

- **Novo projeto** → selecione **PROJETO X (documentação + 10 projetos)** → mantenha as duas seções ou adicione etapas clássicas → **Criar projeto e tarefas**.
- **Projeto já existente** → navegue até **Plano PROJETO X** → **Adicionar / completar modelo PROJETO X neste projeto**. O sistema só insere códigos 1.1–2.10 ainda ausentes; os dados já cadastrados são preservados.
- **Plano PROJETO X** → escolha um item e clique em **Ficha / dados**, **R$ Financeiro**, **Execução** ou **Anexos**. A ficha técnica contém os campos próprios do documento; responsáveis, datas gerais, custo e status continuam em **Detalhes**.

### Correspondência exata das seções

**1. DOCUMENTAÇÃO:**
- 1.1 Matrícula: número, nome do proprietário, área em m²; matrícula, contrato social, documento pessoal, cadastro Prefeitura.
- 1.2 Proprietário do Empreendimento: nome/razão social, CNPJ; documento pessoal e contrato social.
- 1.3 Contratos e Consultas: contrato de locação e consultas de viabilidade com Prefeitura, Meio Ambiente e Junta Comercial.

**2. PROJETOS:**
- 2.1 Topografia: retificação Sim/Não.
- 2.2 Arquitetônico.
- 2.3 Hidrossanitário.
- 2.4 Projeto Preventivo.
- 2.5 Projeto Ambiental.
- 2.6 EIV: audiência pública Sim/Não.
- 2.7 Alvará de Construção: documentos, matrícula atualizada, CNDs e projetos aprovados.
- 2.8 Projeto de Acesso: indicar se é estadual, federal, concessionária ou não se aplica.
- 2.9 LAI (Condicionantes/LAO): situação das licenças e observações das condicionantes.
- 2.10 Habite-se: situação Prefeitura e Bombeiros.

Os itens de projeto possuem campo de **profissional**, salvo os sem profissional exigido pelo PDF, e são ligados ao **valor previsto da tarefa**, ao **cronograma financeiro de parcelas** e ao **cronograma de execução de atividades**. Itens específicos têm campos adicionais.

### Documentos, orçamento e exportações

- Os anexos recebem categorias próprias (Orçamento, Mapa, Nota Fiscal, CND, Matrícula, Consulta de Viabilidade etc.), além das categorias anteriores. PDFs, imagens e arquivos Excel continuam aceitos; até 25 MB por arquivo.
- O plano informa quais categorias documentais estão pendentes em cada item.
- O orçamento precisa ser anexado na categoria **Orçamento** para concluir uma tarefa (regra preexistente mantida).
- Em **Financeiro**, cadastre parcelas e pagamentos de cada item.
- Em **Execução**, inclua, altere ou exclua marcos com datas, status e avanço percentual, visualizados em Gantt.
- Os relatórios PDF e Excel incluem, além das guias anteriores, **fichas técnicas** e **atividades de execução**. No Excel são seis abas: Resumo, Execução, Financeiro, Documentos, Fichas PROJETO X e Atividades.

### Limitações e validação

O PDF é um **roteiro interno de gestão**, não uma determinação de documentos exigidos por cada órgão. Avalie aplicabilidade de EIV, projeto de acesso, LAP/LAI/LAO e demais licenças com o responsável técnico. Os marcos gerados são apenas referências editáveis, não prazos oficiais.

**Testes realizados neste pacote:** testes unitários locais de modelo, geração transacional de itens, exportações e presença de políticas RLS. A migração PostgreSQL e a experiência de interface ainda precisam ser validadas no seu Supabase e Streamlit reais. Recomenda-se testar em homologação antes de aplicar em produção.
