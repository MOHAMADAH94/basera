@echo off
chcp 65001 >nul
setlocal EnableExtensions
title Basera Backend فقط

cd /d "%~dp0"

echo.
echo ========================================
echo   بصيرة - تشغيل الباك اند فقط
echo ========================================
echo.
echo   للتشغيل الكامل (فرونت + باك) استخدم:
echo   ..\start.bat
echo.

set "URL_HOME=http://127.0.0.1:8000/"
set "URL_ADMIN=http://127.0.0.1:8000/admin/"
set "URL_API=http://127.0.0.1:8000/api/"

if not exist "manage.py" (
  echo [خطأ] ضع هذا الملف داخل مجلد backend
  pause
  exit /b 1
)

if not exist "venv\Scripts\python.exe" (
  echo [!] إنشاء venv...
  py -3.10 -m venv venv 2>nul
  if not exist "venv\Scripts\python.exe" py -3 -m venv venv 2>nul
  if not exist "venv\Scripts\python.exe" python -m venv venv 2>nul
  if not exist "venv\Scripts\python.exe" (
    echo [خطأ] تعذر إنشاء venv
    pause
    exit /b 1
  )
)

set "PYTHON=venv\Scripts\python.exe"
set "PIP=venv\Scripts\pip.exe"

"%PYTHON%" -c "import django" 2>nul
if errorlevel 1 (
  if exist "requirements.txt" (
    "%PIP%" install -r requirements.txt
  ) else (
    "%PIP%" install "Django>=4.2,<5" djangorestframework django-cors-headers django-filter python-decouple python-dotenv Pillow pdfplumber PyPDF2 gTTS
  )
)

if not exist "media\lessons\audio" mkdir "media\lessons\audio"
if not exist "media\lessons\pdf" mkdir "media\lessons\pdf"
if not exist "media\questions\audio" mkdir "media\questions\audio"
if not exist "staticfiles" mkdir "staticfiles"
if not exist "tmp" mkdir "tmp"
if not exist "static" mkdir "static"
if not exist ".env" (
  echo DEBUG=True> .env
  echo ENABLE_SERVER_TTS=True>> .env
)

rem ---- المنفذ 8000: هل هو مشغول؟ ----
set "PORT_PID="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:":8000 .*LISTENING"') do if not defined PORT_PID set "PORT_PID=%%p"
if defined PORT_PID (
  curl -s -m 3 "%URL_API%" 2>nul | findstr /i /c:"basera" >nul
  if not errorlevel 1 (
    echo [i] الباك اند يعمل بالفعل على المنفذ 8000 - سيتم فتح الروابط فقط.
    start "" "%URL_HOME%"
    start "" "%URL_ADMIN%"
    start "" "%URL_API%"
    timeout /t 3 >nul 2>&1
    exit /b 0
  )
  echo [!] المنفذ 8000 مشغول ببرنامج آخر ^(PID %PORT_PID%^):
  tasklist /fi "PID eq %PORT_PID%" /fo list 2>nul | findstr /i "Image"
  choice /c YN /t 15 /d Y /m "إيقاف هذا البرنامج وتشغيل بصيرة مكانه"
  if errorlevel 2 (
    echo [خطأ] المنفذ مشغول. أوقف البرنامج الآخر ثم أعد التشغيل.
    pause
    exit /b 1
  )
  taskkill /pid %PORT_PID% /t /f >nul 2>&1
  timeout /t 1 >nul 2>&1
)

"%PYTHON%" manage.py migrate --noinput
if errorlevel 1 (
  echo [خطأ] فشل migrate
  pause
  exit /b 1
)

"%PYTHON%" manage.py check
if errorlevel 1 (
  echo [خطأ] فشل الفحص
  pause
  exit /b 1
)

echo.
echo   Admin : %URL_ADMIN%
echo   Home  : %URL_HOME%
echo   API   : %URL_API%
echo.
echo فتح الروابط في المتصفح...
start "" "%URL_HOME%"
timeout /t 1 /nobreak >nul 2>&1
start "" "%URL_ADMIN%"
timeout /t 1 /nobreak >nul 2>&1
start "" "%URL_API%"

echo.
echo   للإيقاف: Ctrl+C
echo.

"%PYTHON%" manage.py runserver 127.0.0.1:8000
set "EXITCODE=%ERRORLEVEL%"
if not "%EXITCODE%"=="0" (
  echo [!] توقف برمز %EXITCODE%
  pause
)
exit /b %EXITCODE%
