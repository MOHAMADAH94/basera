from django.contrib import admin
from django.utils.html import format_html
from .models import Grade, Category, Lesson, LessonSection, LessonProgress


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ['name', 'subjects_count', 'order', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['order', 'name']
    list_editable = ['order', 'is_active']

    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('name', 'description')
        }),
        ('الإعدادات', {
            'fields': ('order', 'is_active')
        }),
        ('معلومات النظام', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['created_at', 'updated_at']

    @admin.display(description='عدد المواد')
    def subjects_count(self, obj):
        return obj.subjects_count


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_grade', 'lessons_count', 'order', 'is_active', 'created_at']
    list_filter = ['grade', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    ordering = ['grade__order', 'order', 'name']
    list_editable = ['order', 'is_active']
    autocomplete_fields = ['grade']

    @admin.display(description='الصف الدراسي')
    def get_grade(self, obj):
        return obj.grade.name if obj.grade else 'بدون صف — لن تظهر في التطبيق'

    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('grade', 'name', 'description'),
            'description': (
                'مهم جداً: اختر الصف الدراسي وفعّل «نشط»، '
                'وإلا لن تظهر المادة ولا دروسها في التطبيق.'
            ),
        }),
        ('الإعدادات', {
            'fields': ('icon', 'order', 'is_active'),
            'description': 'يجب أن تكون المادة «نشط» لتظهر في التطبيق.',
        }),
        ('معلومات النظام', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    readonly_fields = ['created_at', 'updated_at']

    @admin.display(description='عدد الدروس')
    def lessons_count(self, obj):
        return obj.lessons_count

    def save_model(self, request, obj, form, change):
        if not obj.grade_id:
            first_grade = Grade.objects.filter(is_active=True).order_by('order', 'id').first()
            if first_grade:
                obj.grade = first_grade
        if obj.is_active is None:
            obj.is_active = True
        super().save_model(request, obj, form, change)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'category',
        'status_badge',
        'has_text',
        'has_audio',
        'readiness_badge',
        'created_at_display',
    ]
    list_filter = ['status', 'category', 'conversion_status', 'created_at']
    search_fields = ['title', 'description', 'text_content', 'transcribed_text']
    list_display_links = ['title']
    # قائمة منسدلة عادية أوضح من autocomplete داخل النموذج
    raw_id_fields = []
    autocomplete_fields = []
    readonly_fields = [
        'created_at',
        'updated_at',
        'conversion_status',
        'conversion_progress',
        'conversion_error',
    ]
    actions = [
        'mark_published',
        'mark_draft',
        'mark_ready',
        'extract_pdf_text',
        'regenerate_audio_from_text',
    ]

    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('title', 'description', 'category', 'status'),
            'description': 'الحالة «منشور» ضرورية ليظهر الدرس في التطبيق.',
        }),
        ('① لصق النص', {
            'fields': ('text_content', 'transcribed_text', 'transcribed_text_reviewed'),
            'description': (
                'الصق نص الدرس هنا. بعد الحفظ يُولَّد ملف صوتي تلقائياً '
                '(إذا كان ENABLE_SERVER_TTS=True ولم ترفع صوتاً جاهزاً).'
            ),
        }),
        ('② رفع ملف صوتي جاهز', {
            'fields': ('audio_file', 'duration'),
            'description': (
                'ارفع MP3 جاهزاً. اترك حقول النص فارغة إن أردت تشغيل الصوت فقط. '
                'اسم الملف يفضّل إنجليزي.'
            ),
        }),
        ('③ رفع PDF → استخراج نص → صوت', {
            'fields': ('pdf_file',),
            'description': (
                'ارفع PDF فيه نص قابل للنسخ (ليس صورة ممسوحة). '
                'بعد الحفظ: يُستخرج النص ثم يُحوَّل إلى ملف صوتي تلقائياً.'
            ),
        }),
        ('ملخص اختياري', {
            'fields': ('summary',),
            'classes': ('collapse',),
        }),
        ('المراجعة', {
            'fields': ('created_by', 'reviewed_by'),
            'classes': ('collapse',),
        }),
        ('حالة التحويل', {
            'fields': ('conversion_status', 'conversion_progress', 'conversion_error'),
        }),
        ('معلومات الزمن', {
            'fields': ('created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',),
        }),
    )

    @admin.display(description='الحالة', ordering='status')
    def status_badge(self, obj):
        styles = {
            'published': ('#0B6E4F', '#D8F3E7'),
            'draft': ('#5A6A7A', '#ECEFF3'),
            'review': ('#9A7B0A', '#FCF3CF'),
            'approved': ('#1B4F72', '#D6EAF8'),
        }
        color, bg = styles.get(obj.status, ('#5A6A7A', '#ECEFF3'))
        return format_html(
            '<span class="basera-badge" style="color:{};background:{};border:1px solid {}33">'
            '{}</span>',
            color,
            bg,
            color,
            obj.get_status_display(),
        )

    @admin.display(boolean=True, description='يوجد نص')
    def has_text(self, obj):
        return bool((obj.text_content or obj.transcribed_text or '').strip())

    @admin.display(boolean=True, description='يوجد صوت')
    def has_audio(self, obj):
        return bool(obj.audio_file)

    @admin.display(description='جاهزية التطبيق')
    def readiness_badge(self, obj):
        has_text = bool((obj.text_content or obj.transcribed_text or '').strip())
        has_audio = bool(obj.audio_file)
        if obj.status == 'published' and (has_text or has_audio):
            return format_html(
                '<span class="basera-badge" style="color:#0B6E4F;background:#D8F3E7;'
                'border:1px solid #0B6E4F33">جاهز ويظهر</span>'
            )
        if obj.status == 'published' and not has_text and not has_audio:
            return format_html(
                '<span class="basera-badge" style="color:#C0392B;background:#FDEDEC;'
                'border:1px solid #C0392B33">منشور بلا محتوى</span>'
            )
        if has_text or has_audio:
            return format_html(
                '<span class="basera-badge" style="color:#9A7B0A;background:#FCF3CF;'
                'border:1px solid #9A7B0A33">محتوى موجود — غير منشور</span>'
            )
        return format_html(
            '<span class="basera-badge" style="color:#5A6A7A;background:#ECEFF3;'
            'border:1px solid #5A6A7A33">غير جاهز</span>'
        )

    @admin.display(description='تاريخ الإنشاء', ordering='created_at')
    def created_at_display(self, obj):
        return obj.created_at

    @admin.action(description='تعيين كـ منشور')
    def mark_published(self, request, queryset):
        from django.utils import timezone
        updated = 0
        for lesson in queryset:
            lesson.status = 'published'
            if not lesson.published_at:
                lesson.published_at = timezone.now()
            self._sync_ready_flags(lesson)
            lesson.save()
            updated += 1
        self.message_user(request, f'تم نشر {updated} درس/دروس.')

    @admin.action(description='تعيين كـ مسودة')
    def mark_draft(self, request, queryset):
        count = queryset.update(status='draft')
        self.message_user(request, f'تم تحويل {count} إلى مسودة.')

    @admin.action(description='تحديث الجاهزية (نص/صوت مكتمل)')
    def mark_ready(self, request, queryset):
        updated = 0
        for lesson in queryset:
            if self._sync_ready_flags(lesson):
                lesson.save(update_fields=[
                    'conversion_status', 'conversion_progress', 'conversion_error',
                    'transcribed_text',
                ])
                updated += 1
        self.message_user(request, f'تم تحديث جاهزية {updated} درس/دروس.')

    @admin.action(description='استخراج PDF ثم توليد الصوت')
    def extract_pdf_text(self, request, queryset):
        from lessons.signals import process_lesson_content

        messages = []
        for lesson in queryset:
            if not lesson.pdf_file:
                messages.append(f'«{lesson.title}»: لا يوجد PDF')
                continue
            summary = process_lesson_content(lesson.pk, force_pdf=True, force_audio=True)
            messages.append(f'«{lesson.title}»: {summary}')
        self.message_user(request, ' | '.join(messages)[:900])

    @admin.action(description='إعادة توليد الصوت من النص')
    def regenerate_audio_from_text(self, request, queryset):
        from lessons.signals import process_lesson_content, _server_tts_enabled

        if not _server_tts_enabled():
            self.message_user(
                request,
                'توليد الصوت معطّل. ضع ENABLE_SERVER_TTS=True في .env ثم أعد التشغيل.',
                level=30,
            )
            return
        messages = []
        for lesson in queryset:
            text = (lesson.transcribed_text or lesson.text_content or '').strip()
            if not text:
                messages.append(f'«{lesson.title}»: لا يوجد نص')
                continue
            # احذف الصوت القديم لإجبار إعادة التوليد
            if lesson.audio_file:
                lesson.audio_file.delete(save=False)
                lesson.audio_file = None
                lesson.save(update_fields=['audio_file'])
            summary = process_lesson_content(lesson.pk, force_pdf=False, force_audio=True)
            messages.append(f'«{lesson.title}»: {summary}')
        self.message_user(request, ' | '.join(messages)[:900])

    def _sync_ready_flags(self, obj):
        changed = False
        text = (obj.text_content or '').strip()
        if text and (obj.transcribed_text or '').strip() != text:
            obj.transcribed_text = obj.text_content
            changed = True
        if text or obj.audio_file:
            if obj.conversion_status != 'completed' or obj.conversion_error:
                obj.conversion_status = 'completed'
                obj.conversion_progress = 100
                obj.conversion_error = None
                changed = True
        return changed

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        self._sync_ready_flags(obj)
        if obj.status == 'published' and not obj.published_at:
            from django.utils import timezone
            obj.published_at = timezone.now()
        super().save_model(request, obj, form, change)

        category = obj.category
        if category:
            changed = False
            if not category.is_active:
                category.is_active = True
                changed = True
            if not category.grade_id:
                first_grade = Grade.objects.filter(is_active=True).order_by('order', 'id').first()
                if first_grade:
                    category.grade = first_grade
                    changed = True
            if changed:
                category.save()


@admin.register(LessonSection)
class LessonSectionAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'section_type', 'order']
    list_filter = ['section_type']
    ordering = ['lesson', 'order']
    search_fields = ['lesson__title', 'text']


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ['user', 'lesson', 'completed', 'listening_time_seconds', 'current_position', 'last_accessed']
    list_filter = ['completed', 'last_accessed', 'lesson__category']
    search_fields = ['user__username', 'lesson__title']
    readonly_fields = ['created_at', 'last_accessed']
    list_select_related = ['user', 'lesson']
    date_hierarchy = 'last_accessed'
