# رفع بصيرة على basera.mobishop.online (Namecheap Stellar)

الدومين الفرعي جاهز: http://basera.mobishop.online/

هذا الرفع **منفصل عن موبي شوب** (مجلد + قاعدة بيانات مختلفان).

## 1) في cPanel

1. **MySQL Databases**
   - أنشئ قاعدة و مستخدم واربطهما.
   - احفظ: الاسم، المستخدم، كلمة المرور.

2. **SSL/TLS** (مستحسن)
   - فعّل AutoSSL لـ `basera.mobishop.online`
   - بعدها استخدم `https://` في التطبيق (الإعداد الافتراضي).

3. **Setup Python App**
   - Python: 3.10 أو 3.11 إن وُجد
   - Application root: مجلد رفع الباك اند (يحتوي `manage.py` و `passenger_wsgi.py`)
   - Application URL: `basera.mobishop.online` (المسار `/`)
   - Application startup file: `passenger_wsgi.py`
   - أنشئ التطبيق ثم ادخل إلى الـ virtual environment من الزر الذي يظهره cPanel

## 2) رفع الملفات

ارفع محتويات مجلد `backend` **بدون**:

- `venv/`
- `__pycache__/`
- `.git/`
- `db.sqlite3` (إلا لو أردت نقل بيانات تجريبية ثم التحويل لـ MySQL)

يمكنك إنشاء أرشيف جاهز محلياً:

```powershell
cd backend
powershell -ExecutionPolicy Bypass -File .\pack_for_hosting.ps1
```

سيُنشئ `basera-backend-hosting.zip` على سطح المكتب أو بجانب السكربت.

ارفع الملفات عبر File Manager أو FTP إلى مجلد الـ Python App.

## 3) ملف `.env` على السيرفر

انسخ `.env.production.example` إلى `.env` واملأ القيم:

```env
DEBUG=False
SECRET_KEY=مفتاح-عشوائي-طويل
ALLOWED_HOSTS=basera.mobishop.online
CSRF_TRUSTED_ORIGINS=https://basera.mobishop.online,http://basera.mobishop.online
DB_ENGINE=mysql
DB_NAME=...
DB_USER=...
DB_PASSWORD=...
DB_HOST=localhost
```

إن لم يُفعَّل SSL بعد، اترك التطبيق على `http` مؤقتاً (انظر قسم Flutter).

## 4) تثبيت الحزم والترحيل

من Terminal في cPanel (بعد تفعيل venv الخاص بالتطبيق):

```bash
cd ~/مسار_تطبيق_بصيرة
pip install -r requirements-hosting.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

ثم من واجهة Setup Python App اضغط **Restart**.

## 5) التحقق

- Admin: `https://basera.mobishop.online/admin/`
- API: `https://basera.mobishop.online/api/lessons/` أو `/api/auth/`

يجب أن تختفي صفحة `Index of /`.

## 6) تطبيق Flutter

الإعداد الافتراضي يتصل بـ:

`http://basera.mobishop.online/api`

(حاليًا الدومين يعمل على http؛ بعد AutoSSL غيّر في `lib/config/app_config.dart` إلى `https://...`)

للتشغيل المحلي مؤقتاً:

```bash
flutter run --dart-define=USE_LOCAL_API=true
```

لبناء نسخة الإنتاج:

```bash
flutter build apk
```

## ملاحظات

- لا ترفع `openai-whisper` على Stellar؛ التفريغ الصوتي غير مطلوب للقراءة من النص عبر TTS على الجهاز.
- مجلد `media/` يجب أن يكون قابلاً للكتابة (صلاحيات 755 أو 775 حسب الاستضافة).
- موبي شوب على الدومين الرئيسي يبقى كما هو دون تعديل ملفاته.
