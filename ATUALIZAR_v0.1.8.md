# CronogramaObras Cloud v0.1.8 — KML no satélite e exclusão

Esta atualização utiliza como base a v0.1.7. **Não exclui os KMLs existentes automaticamente**.

## O que mudou

- Em **Etapas → 1.0 Localização do empreendimento**, cada KML possui **Baixar / abrir KML** e **Excluir KML** lado a lado (exclusão somente Administrador). A exclusão exige confirmação, é individual e não remove outros KMLs.
- **Observar no mapa** abre por padrão um mapa de imagens de satélite **Esri World Imagery**, com contornos, linhas e pontos do KML. No canto do mapa, a opção de camadas permite alternar para mapa de ruas.
- Envios acidentais repetidos com o mesmo nome e tamanho são alertados. KMLs repetidos já existentes continuam visíveis como registros separados até que o administrador decida removê-los.
- A área **Anexos** da tarefa não exclui KML diretamente; a exclusão com confirmação fica concentrada na seção **1.0 Localização**, somente para administradores.
- O banco de dados e o Storage aplicam a restrição de exclusão, não apenas a interface.

## Atualizar o sistema existente

1. **Antes de tudo, gere um backup** na versão atual. O SQL desta versão não remove arquivos, mas é importante manter cópias.
2. **Supabase → SQL Editor:** execute **somente** `supabase/migrations/20261117_kml_satellite_admin_delete.sql`. **Não execute** `schema.sql` ou `SQL_COMPLETO_SUPABASE.sql` em banco já instalado.
3. **GitHub:** envie os arquivos do ZIP v0.1.8 para o repositório `TS-Tec-Dev/projetosstang` (ou aplique apenas os arquivos do pacote de correção), sem publicar `.streamlit/secrets.toml`.
4. **Streamlit:** reinicie o aplicativo (Reboot) e recarregue com Ctrl+F5.
5. Faça login como **Administrador**, abra **Etapas → Localização do empreendimento**, clique em **Observar no mapa** e verifique o satélite. Teste a exclusão de um KML de teste, confirmando a operação. Verifique com outro perfil que o botão não apareça.

## Observações

- O **serviço de imagens é Esri World Imagery**, não o Google Earth. O arquivo continua sendo `.kml` compatível com Google Earth. A imagem de satélite é fornecida pela Esri e pode depender das condições de uso do provedor; confira os termos para implantação pública. O mapa exige conexão com a internet no navegador e exibe a atribuição de fonte.
- KML de até 10 MB, apenas pontos, linhas e polígonos para pré-visualização. Modelos 3D e overlays não são renderizados internamente; o arquivo original pode ser aberto no Google Earth.
- Em caso de falha na remoção de objetos do Storage após a exclusão do registro, o aplicativo informa que restou arquivo órfão para limpeza administrativa.
- Esta atualização **não exige nenhuma nova Edge Function**. As configurações de usuários da v0.1.7 permanecem inalteradas.
- Não foi realizada uma validação conectada à sua instância Supabase. Teste as permissões após aplicar a migração.
