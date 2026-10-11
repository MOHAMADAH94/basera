from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'النظام والمستخدمون'

    def ready(self):
        from django.contrib import admin

        admin.site.site_header = 'بصيرة'
        admin.site.site_title = 'بصيرة | لوحة التحكم'
        admin.site.index_title = 'لوحة تحكم بصيرة'
        admin.site.site_url = None  # إخفاء رابط «عرض الموقع» الافتراضي إن لم يوجد واجهة ويب
        admin.site.enable_nav_sidebar = True
