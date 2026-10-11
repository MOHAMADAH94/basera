from django.core.management.base import BaseCommand
from django.utils import timezone

from lessons.models import Lesson


class Command(BaseCommand):
    help = (
        'تجهيز الدروس للقراءة النصية: مزامنة النص، إكمال حالة التحويل، '
        'ونشر الدروس التي لها نص إن طُلب ذلك.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--publish',
            action='store_true',
            help='نشر كل درس فيه نص وحالته ليست منشوراً',
        )

    def handle(self, *args, **options):
        qs = Lesson.objects.all()
        fixed = 0
        published = 0
        for lesson in qs:
            text = (lesson.text_content or '').strip()
            transcribed = (lesson.transcribed_text or '').strip()
            changed = False

            if text and text != transcribed:
                lesson.transcribed_text = lesson.text_content
                changed = True
            elif not transcribed and text:
                lesson.transcribed_text = lesson.text_content
                changed = True

            readable = (lesson.transcribed_text or lesson.text_content or '').strip()
            if readable and (
                lesson.conversion_status != 'completed'
                or lesson.conversion_error
            ):
                lesson.conversion_status = 'completed'
                lesson.conversion_progress = 100
                lesson.conversion_error = None
                changed = True

            if options['publish'] and readable and lesson.status != 'published':
                lesson.status = 'published'
                if not lesson.published_at:
                    lesson.published_at = timezone.now()
                changed = True
                published += 1

            if changed:
                # تحديث مباشر بدون إعادة تشغيل إشارات الصوت الثقيلة
                Lesson.objects.filter(pk=lesson.pk).update(
                    text_content=lesson.text_content,
                    transcribed_text=lesson.transcribed_text,
                    conversion_status=lesson.conversion_status,
                    conversion_progress=lesson.conversion_progress,
                    conversion_error=lesson.conversion_error,
                    status=lesson.status,
                    published_at=lesson.published_at,
                )
                fixed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'تم تجهيز {fixed} درساً'
                + (f'، ونشر {published}' if options['publish'] else '')
            )
        )
