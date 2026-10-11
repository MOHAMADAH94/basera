@echo off
setlocal
cd /d "%~dp0"
title Basera Launcher
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%PS%" set "PS=powershell.exe"
start "" "%PS%" -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -Command "$f=[IO.File]::ReadAllText('%~f0',[Text.Encoding]::UTF8); $m='#PS_'+'BEGIN'; Invoke-Expression $f.Substring($f.LastIndexOf($m))"
exit /b

#PS_BEGIN  ===== PowerShell GUI (do not edit the header above) =====
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$Root = (Get-Location).Path
$Backend = Join-Path $Root 'backend'
$Nabd = Join-Path $Root 'nabd-site'
$Py = Join-Path $Backend 'venv\Scripts\python.exe'
$BackendPort = 8000
$NabdPort = 5500

function Test-Port([int]$Port) {
  try {
    $c = New-Object System.Net.Sockets.TcpClient
    $iar = $c.BeginConnect('127.0.0.1', $Port, $null, $null)
    $ok = $iar.AsyncWaitHandle.WaitOne(400)
    if ($ok -and $c.Connected) { $c.Close(); return $true }
    $c.Close()
    return $false
  } catch { return $false }
}

function Set-Status([string]$Text) {
  $global:Status.Text = $Text
  [System.Windows.Forms.Application]::DoEvents()
}

function Ensure-Venv {
  if (Test-Path -LiteralPath $Py) { return $true }
  Set-Status 'جاري إنشاء بيئة Python...'
  $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
  if ($pyLauncher) {
    & py -3 -m venv (Join-Path $Backend 'venv')
  } else {
    & python -m venv (Join-Path $Backend 'venv')
  }
  if (-not (Test-Path -LiteralPath $Py)) { return $false }
  $req = Join-Path $Backend 'requirements.txt'
  if (Test-Path $req) {
    & (Join-Path $Backend 'venv\Scripts\pip.exe') install -r $req
  } else {
    & (Join-Path $Backend 'venv\Scripts\pip.exe') install 'Django>=4.2,<5' djangorestframework django-cors-headers django-filter python-decouple python-dotenv Pillow
  }
  return $true
}

function Test-BaseraBackend {
  try {
    $r = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/api/" -UseBasicParsing -TimeoutSec 3
    return ($r.Content -match 'basera')
  } catch { return $false }
}

function Free-Port([int]$Port) {
  $owners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
  if (-not $owners) { return $true }
  $names = ($owners | ForEach-Object { $p = Get-Process -Id $_ -ErrorAction SilentlyContinue; if ($p) { "$($p.ProcessName) (PID $_)" } }) -join ', '
  $msg = "المنفذ $Port مشغول ببرنامج آخر ليس بصيرة:`n$names`n`nهل تريد إيقافه وتشغيل بصيرة مكانه؟"
  $ans = [System.Windows.Forms.MessageBox]::Show($msg, 'بصيرة', 'YesNo', 'Question')
  if ($ans -ne 'Yes') { return $false }
  foreach ($id in $owners) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue }
  Start-Sleep -Seconds 1
  return (-not (Test-Port $Port))
}

function Start-Backend {
  if (-not (Ensure-Venv)) {
    [System.Windows.Forms.MessageBox]::Show('تعذر العثور على Python أو إنشاء البيئة.', 'بصيرة') | Out-Null
    return $false
  }
  if (Test-Port $BackendPort) {
    if (Test-BaseraBackend) { return $true }
    if (-not (Free-Port $BackendPort)) { Set-Status "المنفذ $BackendPort مشغول ببرنامج آخر"; return $false }
  }
  Set-Status 'جاري تشغيل الباك اند...'
  $cmd = "venv\Scripts\python.exe manage.py migrate --noinput && venv\Scripts\python.exe manage.py runserver 127.0.0.1:$BackendPort"
  Start-Process -FilePath 'cmd.exe' -WorkingDirectory $Backend -ArgumentList '/k', $cmd -WindowStyle Normal
  for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Milliseconds 400
    if (Test-Port $BackendPort) { return $true }
  }
  return (Test-Port $BackendPort)
}

function Start-NabdServer {
  if (Test-Port $NabdPort) { return $true }
  if (-not (Test-Path (Join-Path $Nabd 'index.html'))) { return $false }
  $pyExe = (Get-Command python -ErrorAction SilentlyContinue)
  if (-not $pyExe) { $pyExe = Get-Command py -ErrorAction SilentlyContinue }
  if (-not $pyExe) { return $false }
  Set-Status 'جاري تشغيل واجهة نبض...'
  Start-Process -FilePath $pyExe.Source -WorkingDirectory $Nabd -ArgumentList '-m','http.server',"$NabdPort",'--bind','127.0.0.1' -WindowStyle Minimized
  Start-Sleep -Seconds 1
  return (Test-Port $NabdPort)
}

function Open-Url([string]$Url) {
  Start-Process $Url
}

$form = New-Object System.Windows.Forms.Form
$form.Text = 'بصيرة — لوحة التشغيل'
$form.StartPosition = 'CenterScreen'
$form.Size = New-Object System.Drawing.Size(460, 560)
$form.MinimumSize = New-Object System.Drawing.Size(420, 520)
$form.RightToLeft = 'Yes'
$form.RightToLeftLayout = $true
$form.BackColor = [System.Drawing.Color]::FromArgb(244, 247, 251)
$form.Font = New-Object System.Drawing.Font('Segoe UI', 11)
$form.FormBorderStyle = 'FixedDialog'
$form.MaximizeBox = $false

$title = New-Object System.Windows.Forms.Label
$title.Text = 'بصيرة'
$title.Font = New-Object System.Drawing.Font('Segoe UI', 22, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(27, 79, 114)
$title.AutoSize = $true
$title.Location = New-Object System.Drawing.Point(30, 18)
$form.Controls.Add($title)

$sub = New-Object System.Windows.Forms.Label
$sub.Text = 'اختر ما تريد تشغيله'
$sub.ForeColor = [System.Drawing.Color]::FromArgb(90, 106, 122)
$sub.AutoSize = $true
$sub.Location = New-Object System.Drawing.Point(30, 62)
$form.Controls.Add($sub)

function New-ActionButton([string]$Text, [int]$Y, [System.Drawing.Color]$Color, [scriptblock]$Click) {
  $b = New-Object System.Windows.Forms.Button
  $b.Text = $Text
  $b.Size = New-Object System.Drawing.Size(380, 72)
  $b.Location = New-Object System.Drawing.Point(30, $Y)
  $b.FlatStyle = 'Flat'
  $b.FlatAppearance.BorderSize = 0
  $b.Font = New-Object System.Drawing.Font('Segoe UI', 13, [System.Drawing.FontStyle]::Bold)
  $b.ForeColor = [System.Drawing.Color]::White
  $b.BackColor = $Color
  $b.Cursor = [System.Windows.Forms.Cursors]::Hand
  $b.Add_Click($Click)
  $form.Controls.Add($b)
}

$global:Status = New-Object System.Windows.Forms.Label
$global:Status.Text = 'جاهز'
$global:Status.AutoSize = $false
$global:Status.Size = New-Object System.Drawing.Size(380, 40)
$global:Status.Location = New-Object System.Drawing.Point(30, 460)
$global:Status.ForeColor = [System.Drawing.Color]::FromArgb(90, 106, 122)
$form.Controls.Add($global:Status)

New-ActionButton 'تشغيل الباك اند' 100 ([System.Drawing.Color]::FromArgb(27, 79, 114)) {
  if (Start-Backend) {
    Open-Url 'http://127.0.0.1:8000/'
    Open-Url 'http://127.0.0.1:8000/admin/'
    Set-Status 'الباك اند يعمل — http://127.0.0.1:8000/'
  } else {
    Set-Status 'فشل تشغيل الباك اند'
  }
}

New-ActionButton 'فرونت نبض' 184 ([System.Drawing.Color]::FromArgb(20, 143, 119)) {
  $ok = Start-Backend
  $null = Start-NabdServer
  if ($ok) {
    Open-Url 'http://127.0.0.1:8000/nabd/'
    Set-Status 'نبض يعمل عبر الباك اند — /nabd/'
  } elseif (Test-Port $NabdPort) {
    Open-Url "http://127.0.0.1:$NabdPort/"
    Set-Status "نبض يعمل على المنفذ $NabdPort"
  } else {
    Set-Status 'تعذر تشغيل موقع نبض'
  }
}

New-ActionButton 'تطبيق فلتر' 268 ([System.Drawing.Color]::FromArgb(212, 160, 23)) {
  $flutter = Get-Command flutter -ErrorAction SilentlyContinue
  if (-not $flutter) {
    [System.Windows.Forms.MessageBox]::Show('لم يتم العثور على Flutter في PATH.', 'بصيرة') | Out-Null
    return
  }
  $null = Start-Backend
  Set-Status 'جاري تشغيل تطبيق فلتر...'
  $flutterArgs = 'run --dart-define=USE_LOCAL_API=true'
  Start-Process -FilePath 'cmd.exe' -WorkingDirectory $Root -ArgumentList '/k', "flutter $flutterArgs"
}

New-ActionButton 'شجرة الـ API' 352 ([System.Drawing.Color]::FromArgb(21, 67, 96)) {
  if (Start-Backend) {
    Open-Url 'http://127.0.0.1:8000/api/'
    Set-Status 'شجرة API — http://127.0.0.1:8000/api/'
  } else {
    Set-Status 'شغّل الباك اند أولاً'
  }
}

$form.WindowState = 'Normal'
$form.TopMost = $true
$form.Add_Shown({ $form.WindowState = 'Normal'; $form.Activate(); $form.TopMost = $false })
[void]$form.ShowDialog()
