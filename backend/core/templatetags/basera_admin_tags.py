from django import template
from django.contrib.auth import get_user_model

register = template.Library()


@register.simple_tag
def basera_dashboard_stats():
    """إحصائيات سريعة لصفحة رئيسية لوحة التحكم."""
    stats = {
        'grades': 0,
        'categories': 0,
        'lessons': 0,
        'published': 0,
        'quizzes': 0,
        'users': 0,
    }
    try:
        from lessons.models import Category, Grade, Lesson

        stats['grades'] = Grade.objects.count()
        stats['categories'] = Category.objects.count()
        stats['lessons'] = Lesson.objects.count()
        stats['published'] = Lesson.objects.filter(status='published').count()
    except Exception:
        pass

    try:
        from tests.models import Quiz as AppQuiz

        stats['quizzes'] = AppQuiz.objects.count()
    except Exception:
        pass

    try:
        User = get_user_model()
        stats['users'] = User.objects.count()
    except Exception:
        pass

    return stats


@register.simple_tag
def basera_brand_name():
    return 'بصيرة'
