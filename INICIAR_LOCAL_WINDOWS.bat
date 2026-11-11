@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Criando ambiente Python 3.12...
  py -3.12 -m venv .venv || goto :error
  echo [2/3] Instalando dependencias...
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || goto :error
)
if not exist ".streamlit\secrets.toml" (
  copy ".streamlit\secrets.toml.example" ".streamlit\secrets.toml" >nul
  echo.
  echo [IMPORTANTE] Preencha .streamlit\secrets.toml com a URL e chave publica do Supabase.
  notepad ".streamlit\secrets.toml"
)
echo [3/3] Iniciando o CronogramaObras Cloud...
".venv\Scripts\python.exe" -m streamlit run app.py
pause
exit /b 0
:error
echo.
echo Erro: verifique a versao do Python, conexao e o arquivo de configuracao.
pause
exit /b 1
