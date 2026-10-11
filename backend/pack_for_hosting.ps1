# Pack Basera backend for Namecheap upload (no venv / caches / secrets)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$stamp = Get-Date -Format 'yyyyMMdd-HHmm'
$desktop = [Environment]::GetFolderPath('Desktop')
$outZipDesktop = Join-Path $desktop "basera-backend-hosting-$stamp.zip"
$outZipLocal = Join-Path $root "basera-backend-hosting.zip"
$stage = Join-Path $env:TEMP "basera-backend-pack-$stamp"

if (Test-Path $stage) { Remove-Item $stage -Recurse -Force }
New-Item -ItemType Directory -Path $stage | Out-Null

$excludeDirs = @(
  'venv', '.venv', '__pycache__', '.git', 'tmp', 'staticfiles',
  '.pytest_cache', '.mypy_cache'
)
$excludeFiles = @('db.sqlite3', '.env', 'basera-backend-hosting.zip')

Get-ChildItem -Path $root -Force | ForEach-Object {
  $name = $_.Name
  if ($excludeDirs -contains $name) { return }
  if ($excludeFiles -contains $name) { return }
  if ($name -like 'pack_for_hosting.ps1') { return }
  Copy-Item -Path $_.FullName -Destination (Join-Path $stage $name) -Recurse -Force
}

Get-ChildItem -Path $stage -Recurse -Directory -Filter '__pycache__' -ErrorAction SilentlyContinue |
  Remove-Item -Recurse -Force

# أزل ملفات الوسائط الكبيرة وأبقِ المجلدات فارغة على الاستضافة
$media = Join-Path $stage 'media'
if (Test-Path $media) {
  Get-ChildItem $media -Recurse -File | Remove-Item -Force
}
@(
  'media\lessons\audio',
  'media\lessons\pdf',
  'media\questions\audio',
  'media\answers\audio'
) | ForEach-Object {
  New-Item -ItemType Directory -Force -Path (Join-Path $stage $_) | Out-Null
}

if (Test-Path (Join-Path $root '.env.production.example')) {
  Copy-Item (Join-Path $root '.env.production.example') (Join-Path $stage '.env.production.example') -Force
}

$readme = @"
رفع باك اند بصيرة على basera.mobishop.online
============================================
1) ارفع محتويات هذا الأرشيف إلى مجلد تطبيق Python في cPanel (المجلد الذي فيه passenger_wsgi.py).
2) انسخ .env.production.example إلى .env واملأ بيانات MySQL و SECRET_KEY.
3) من Terminal بعد تفعيل بيئة Python:
   pip install -r requirements-hosting.txt
   python manage.py migrate
   python manage.py collectstatic --noinput
   python manage.py createsuperuser
4) من Setup Python App اضغط Restart.
5) تحقق من:
   https://basera.mobishop.online/admin/
   https://basera.mobishop.online/api/lessons/grades/

التفاصيل الكاملة في DEPLOY_NAMECHEAP.md
"@
Set-Content -Path (Join-Path $stage 'ارفع_على_السيرفر.txt') -Value $readme -Encoding UTF8

foreach ($dest in @($outZipDesktop, $outZipLocal)) {
  if (Test-Path $dest) { Remove-Item $dest -Force }
}
Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $outZipDesktop -Force
Copy-Item $outZipDesktop $outZipLocal -Force
Remove-Item $stage -Recurse -Force

Write-Host "Created: $outZipDesktop"
Write-Host "Copy:    $outZipLocal"
