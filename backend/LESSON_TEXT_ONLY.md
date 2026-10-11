# إضافة درس يظهر في التطبيق (بدون تحويل صوت على السيرفر)

## في لوحة الأدمن
1. افتح الدروس → أضف درس
2. العنوان + المادة
3. الصق النص في حقل **محتوى النص**
4. الحالة: **منشور** (مهم جداً)
5. احفظ

التطبيق يقرأ النص عبر صوت الجهاز. لا حاجة لملف صوتي أو PDF.

## على السيرفر بعد رفع الملفات المحدّثة
ارفع على الأقل:
- `lessons/signals.py`
- `lessons/admin.py`
- `basera_backend/settings.py`
- مجلد `lessons/management/` إن وُجد

أضف في `.env`:
```env
ENABLE_SERVER_TTS=False
```

ثم:
```bash
source /home/mobihull/virtualenv/basera.mobishop.online/3.10/bin/activate
cd /home/mobihull/basera.mobishop.online
python manage.py prepare_text_lessons --publish
touch tmp/restart.txt
```

`--publish` ينشر أي درس فيه نص ولم يكن منشوراً.
