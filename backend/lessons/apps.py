from django.apps import AppConfig


class LessonsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lessons'
    verbose_name = 'المحتوى التعليمي'

    def ready(self):
        import lessons.signals  # noqa: F401
