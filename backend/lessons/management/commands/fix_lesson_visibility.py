from django.core.management.base import BaseCommand

from lessons.models import Category, Grade, Lesson


class Command(BaseCommand):
    help = (
        'إصلاح ظهور الدروس في التطبيق: تفعيل المواد وربطها بصف دراسي '
        'عندما تكون الدروس منشورة لكن المادة مخفية.'
    )

    def handle(self, *args, **options):
        first_grade = Grade.objects.filter(is_active=True).order_by('order', 'id').first()
        if not first_grade:
            self.stderr.write(self.style.ERROR('لا يوجد صف دراسي نشط. أنشئ صفاً أولاً من الأدمن.'))
            return

        fixed = 0
        categories = Category.objects.all()
        for cat in categories:
            changes = []
            if not cat.is_active:
                cat.is_active = True
                changes.append('تفعيل')
            if not cat.grade_id:
                cat.grade = first_grade
                changes.append(f'ربط بـ {first_grade.name}')
            if changes:
                cat.save()
                fixed += 1
                self.stdout.write(f'✓ المادة «{cat.name}»: {", ".join(changes)}')

        published = Lesson.objects.filter(status='published').count()
        visible_cats = Category.objects.filter(is_active=True, grade__isnull=False).count()

        self.stdout.write(
            self.style.SUCCESS(
                f'تم. دروس منشورة: {published} | مواد ظاهرة للتطبيق: {visible_cats} | مواد أُصلحت: {fixed}'
            )
        )
        self.stdout.write(
            'مسار الظهور في التطبيق: الصفوف → المادة → الدرس'
        )
