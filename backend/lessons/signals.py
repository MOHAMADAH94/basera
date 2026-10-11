"""
مسارات محتوى الدرس (ثلاثة أوضاع):

1) لصق نص → مزامنة النص → توليد ملف صوتي (إن تفعّل TTS ولم يوجد صوت مرفوع)
2) رفع ملف صوتي جاهز → اكتمال بدون توليد
3) رفع PDF → استخراج النص بعد الحفظ → توليد ملف صوتي

ENABLE_SERVER_TTS=True مطلوب لتوليد الصوت من النص/PDF.
إن فشل التوليد يبقى النص صالحاً للقراءة من التطبيق.
"""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.core.files.base import ContentFile
from django.conf import settings
from django.db import transaction
import os
import logging
import tempfile

from .models import Lesson
from .text_conversion_service import TextConversionService

logger = logging.getLogger(__name__)


def _server_tts_enabled():
    return str(getattr(settings, 'ENABLE_SERVER_TTS', True)).lower() in (
        '1', 'true', 'yes', 'on',
    )


def _mark_completed(lesson_id, message='', **extra):
    update = {
        'conversion_status': 'completed',
        'conversion_progress': 100,
        'conversion_error': message or '',
    }
    update.update(extra)
    Lesson.objects.filter(pk=lesson_id).update(**update)


def _has_readable_text(instance):
    return bool((instance.transcribed_text or '').strip() or (instance.text_content or '').strip())


def _audio_file_ready(lesson):
    if not lesson.audio_file:
        return False
    try:
        return os.path.exists(lesson.audio_file.path)
    except Exception:
        return bool(lesson.audio_file.name)


def _resolve_pdf_path(lesson):
    if not lesson.pdf_file:
        return None
    try:
        path = lesson.pdf_file.path
        if path and os.path.exists(path):
            return path
    except Exception as e:
        logger.warning('تعذر قراءة مسار PDF مباشرة: %s', e)

    try:
        suffix = os.path.splitext(lesson.pdf_file.name or 'lesson.pdf')[1] or '.pdf'
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        try:
            lesson.pdf_file.open('rb')
            for chunk in lesson.pdf_file.chunks():
                tmp.write(chunk)
        finally:
            try:
                lesson.pdf_file.close()
            except Exception:
                pass
            tmp.close()
        return tmp.name
    except Exception as e:
        logger.error('فشل تجهيز ملف PDF مؤقت: %s', e, exc_info=True)
        return None


def _extract_pdf_for_lesson(lesson_id):
    """وضع 3: استخراج النص من PDF."""
    lesson = Lesson.objects.filter(pk=lesson_id).first()
    if not lesson or not lesson.pdf_file:
        return False

    Lesson.objects.filter(pk=lesson_id).update(
        conversion_status='extracting_text',
        conversion_progress=15,
        conversion_error='',
    )

    pdf_path = _resolve_pdf_path(lesson)
    if not pdf_path:
        Lesson.objects.filter(pk=lesson_id).update(
            conversion_status='failed',
            conversion_progress=0,
            conversion_error='تعذر الوصول لملف PDF بعد الرفع',
        )
        return False

    try:
        extracted = TextConversionService.extract_text_from_pdf(pdf_path)
        if extracted:
            extracted = TextConversionService.clean_text(extracted)

        if not extracted:
            Lesson.objects.filter(pk=lesson_id).update(
                conversion_status='failed',
                conversion_progress=0,
                conversion_error=(
                    'فشل استخراج النص من PDF. '
                    'الملف يجب أن يحتوي نصاً قابلاً للنسخ (وليس صورة ممسوحة فقط).'
                ),
            )
            return False

        update = {
            'transcribed_text': extracted,
            'conversion_status': 'text_extracted',
            'conversion_progress': 55,
            'conversion_error': '',
        }
        if not (lesson.text_content or '').strip():
            update['text_content'] = extracted

        Lesson.objects.filter(pk=lesson_id).update(**update)
        logger.info('تم استخراج %s حرف من PDF للدرس %s', len(extracted), lesson_id)
        return True
    except Exception as e:
        logger.error('خطأ استخراج PDF للدرس %s: %s', lesson_id, e, exc_info=True)
        Lesson.objects.filter(pk=lesson_id).update(
            conversion_status='failed',
            conversion_progress=0,
            conversion_error=f'خطأ استخراج PDF: {e}'[:500],
        )
        return False
    finally:
        try:
            media_root = str(settings.MEDIA_ROOT)
            if pdf_path and media_root not in pdf_path and os.path.exists(pdf_path):
                if tempfile.gettempdir() in pdf_path:
                    os.remove(pdf_path)
        except OSError:
            pass


def _safe_audio_filename(lesson_id):
    return f'lesson_{lesson_id}.mp3'


def _generate_audio_for_lesson(lesson_id, text):
    """توليد ملف صوتي من النص (بعد لصق أو بعد PDF)."""
    from .tts_service import TTSService

    lesson = Lesson.objects.filter(pk=lesson_id).first()
    if not lesson:
        return False

    if _audio_file_ready(lesson):
        _mark_completed(lesson_id)
        return True

    text = (text or '').strip()
    if not text:
        Lesson.objects.filter(pk=lesson_id).update(
            conversion_status='failed',
            conversion_error='لا يوجد نص لتوليد الصوت',
        )
        return False

    Lesson.objects.filter(pk=lesson_id).update(
        conversion_status='converting_audio',
        conversion_progress=70,
        conversion_error='',
    )

    audio_filename = _safe_audio_filename(lesson_id)
    temp_audio_path = os.path.join(tempfile.gettempdir(), audio_filename)

    try:
        result_path = TTSService.convert_text_to_speech(
            text,
            output_path=temp_audio_path,
            use_gtts=True,
            fallback_to_pyttsx3=True,
        )
    except Exception as tts_error:
        logger.error('فشل TTS للدرس %s: %s', lesson_id, tts_error, exc_info=True)
        _mark_completed(
            lesson_id,
            message=f'تم حفظ النص؛ تعذر توليد الصوت. التطبيق يمكنه قراءة النص. ({tts_error})'[:500],
        )
        return False

    if result_path and os.path.exists(result_path):
        lesson = Lesson.objects.filter(pk=lesson_id).first()
        if lesson:
            with open(result_path, 'rb') as audio_file:
                lesson._basera_skip_signals = True
                lesson.audio_file.save(
                    audio_filename,
                    ContentFile(audio_file.read()),
                    save=True,
                )
            try:
                os.remove(result_path)
            except OSError:
                pass
            word_count = len(text.split())
            estimated_duration = max(1, int((word_count / 150) * 60))
            _mark_completed(lesson_id, duration=estimated_duration)
            return True

    _mark_completed(
        lesson_id,
        message='تم حفظ النص؛ تعذر إنشاء ملف صوتي. التطبيق يمكنه قراءة النص.',
    )
    return False


def process_lesson_content(lesson_id, force_pdf=False, force_audio=False):
    """
    مسار موحّد لمعالجة الدرس بعد الحفظ أو من إجراء الأدمن.
    يعيد ملخصاً نصياً للحالة.
    """
    lesson = Lesson.objects.filter(pk=lesson_id).first()
    if not lesson:
        return 'الدرس غير موجود'

    # وضع 2: صوت مرفوع جاهز
    if _audio_file_ready(lesson) and not force_audio:
        _mark_completed(lesson_id)
        return 'ملف صوتي جاهز — اكتمل'

    # وضع 3: PDF يحتاج استخراجاً
    needs_pdf = force_pdf or (
        bool(lesson.pdf_file)
        and not _has_readable_text(lesson)
    )
    # أيضاً إن طُلب إعادة استخراج من PDF حتى مع وجود نص قديم فارغ المعنى
    if force_pdf and lesson.pdf_file:
        needs_pdf = True

    if needs_pdf:
        ok = _extract_pdf_for_lesson(lesson_id)
        if not ok:
            return 'فشل استخراج PDF'
        lesson.refresh_from_db()

    readable = (lesson.transcribed_text or lesson.text_content or '').strip()

    # وضع 1 أو استمرار وضع 3: نص موجود
    if not readable:
        if lesson.pdf_file:
            return 'لا يوجد نص بعد PDF'
        if _audio_file_ready(lesson):
            _mark_completed(lesson_id)
            return 'صوت فقط — اكتمل'
        Lesson.objects.filter(pk=lesson_id).update(
            conversion_status='failed',
            conversion_error='أضف نصاً أو ملفاً صوتياً أو PDF يحتوي نصاً',
        )
        return 'لا يوجد محتوى'

    # توليد صوت من النص إذا لم يوجد ملف صوتي
    if _audio_file_ready(lesson) and not force_audio:
        _mark_completed(lesson_id)
        return 'نص + صوت موجود — اكتمل'

    if not _server_tts_enabled():
        _mark_completed(
            lesson_id,
            message='النص جاهز. توليد الصوت معطّل (ENABLE_SERVER_TTS=False).',
        )
        return 'نص جاهز — توليد الصوت معطّل'

    ok = _generate_audio_for_lesson(lesson_id, readable)
    return 'تم توليد الصوت' if ok else 'نص جاهز — فشل توليد الصوت'


@receiver(pre_save, sender=Lesson)
def prepare_lesson_text(sender, instance, **kwargs):
    if getattr(instance, '_basera_skip_signals', False):
        return

    text_content = (instance.text_content or '').strip()

    # مزامنة النص الملصوق
    if text_content:
        instance.transcribed_text = instance.text_content

    # تتبع تغيّر PDF
    instance._basera_pdf_changed = False
    if instance.pdf_file:
        if not instance.pk:
            instance._basera_pdf_changed = True
        else:
            try:
                old = Lesson.objects.get(pk=instance.pk)
                old_pdf = old.pdf_file.name if old.pdf_file else ''
                new_pdf = instance.pdf_file.name if instance.pdf_file else ''
                instance._basera_pdf_changed = bool(new_pdf and new_pdf != old_pdf)
            except Lesson.DoesNotExist:
                instance._basera_pdf_changed = True

    has_readable = _has_readable_text(instance)

    # صوت جاهز فقط
    if instance.audio_file and not has_readable and not instance.pdf_file:
        instance.conversion_status = 'completed'
        instance.conversion_progress = 100
        instance.conversion_error = None
        instance._basera_process_after_save = True
        return

    # يحتاج استخراج PDF
    if instance.pdf_file and (not has_readable or instance._basera_pdf_changed and not has_readable):
        instance.conversion_status = 'extracting_text'
        instance.conversion_progress = 10
        instance.conversion_error = None

    instance._basera_process_after_save = True


@receiver(post_save, sender=Lesson)
def process_lesson_after_save(sender, instance, created, **kwargs):
    if getattr(instance, '_basera_skip_signals', False):
        return
    if not getattr(instance, '_basera_process_after_save', True):
        return

    force_pdf = bool(
        getattr(instance, '_basera_force_pdf_extract', False)
        or (
            getattr(instance, '_basera_pdf_changed', False)
            and not _has_readable_text(instance)
        )
        or (instance.pdf_file and not _has_readable_text(instance))
    )

    def work():
        try:
            summary = process_lesson_content(
                instance.pk,
                force_pdf=force_pdf,
                force_audio=False,
            )
            logger.info('معالجة الدرس %s: %s', instance.pk, summary)
        except Exception as e:
            logger.error('فشل مسار معالجة الدرس %s: %s', instance.pk, e, exc_info=True)
            _mark_completed(instance.pk, message=f'خطأ معالجة: {e}'[:500])

    transaction.on_commit(work)
