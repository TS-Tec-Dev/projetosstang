# Correção do visualizador KML — v0.1.9

## Origem do problema confirmada no GitHub

A versão publicada em `TS-Tec-Dev/projetosstang` possuía `map_style='light'`
em `src/kml_map.py` e a tela `src/location_ui.py` não possuía exclusão KML.
O código de `src/workflow_ui.py` não repassava `is_admin` ao painel.
Por isso alterar apenas o banco de dados não corrigiria a interface.

## Instalação sem apagar dados

1. No GitHub, atualize os arquivos `src/kml_map.py`, `src/location_ui.py`,
   `src/workflow_ui.py` e `src/db.py` do pacote. O `requirements.txt` do seu repositório já inclui Folium.
   **Importante:** substitua os arquivos nos respectivos diretórios, não crie uma
   pasta extra. O pacote mínimo inclui somente os arquivos necessários.
2. No Streamlit Community Cloud, confirme que o aplicativo usa a branch
   `main` e aguarde a publicação do commit. Se necessário, reinicie e
   recarregue com Ctrl+F5.
3. Verifique o texto `Visualizador KML 0.1.9` sobre os arquivos.
4. Abra o KML em `Etapas > 1.0 Localização`. O mapa abre com a camada
   **Satélite (Esri)**; no canto superior direito é possível alternar para ruas.
5. Entre como Administrador para ver `Excluir KML` ao lado do link de download.
   A ação requer confirmação, exclui o registro e tenta remover o arquivo
   correspondente do Storage. Outros arquivos ficam intactos.
6. Se o botão aparecer mas a exclusão for bloqueada por RLS, execute somente
   `APLICAR_KML_v019_SUPABASE.sql` no SQL Editor. Não rode SQL_COMPLETO
   nem migrações antigas que recriem documents_category_check.

## Segurança

O aplicativo não usa `service_role` no navegador/Streamlit. A exclusão
depende do usuário autenticado e do perfil `admin` no Supabase.
Se a limpeza do arquivo físico falhar após apagar o registro, será exibido
erro informando que poderá restar um objeto órfão no Storage.

## Dependência externa

O mapa obtém imagens da Esri World Imagery via internet. Em redes que
bloqueiem `server.arcgisonline.com`, a camada pode ficar vazia; nesses casos,
libere o serviço ou use a camada opcional de ruas. As imagens não vêm do
Google Earth, embora o arquivo KML seja compatível com Google Earth.
