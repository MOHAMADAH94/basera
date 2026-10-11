from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import Quiz, Question, Choice, QuizAttempt, Answer


def _sync_true_false(question, correct_label):
    correct = correct_label or 'صح'
    question.choices.all().delete()
    Choice.objects.create(question=question, choice_text='صح', is_correct=(correct == 'صح'))
    Choice.objects.create(question=question, choice_text='خطأ', is_correct=(correct == 'خطأ'))


def _sync_mcq(question, texts_by_index, correct_idx):
    rows = [(idx, text) for idx, text in texts_by_index if text]
    if not rows:
        return
    question.choices.all().delete()
    created = []
    for idx, text in rows:
        created.append(Choice.objects.create(
            question=question,
            choice_text=text,
            is_correct=(str(idx) == str(correct_idx)),
        ))
    if created and not any(c.is_correct for c in created):
        created[0].is_correct = True
        created[0].save(update_fields=['is_correct'])


class QuestionInlineForm(forms.ModelForm):
    """من صفحة الاختبار: خيارات الاختيار من متعدد + تحديد الصحيح لصح/خطأ."""

    correct_true_false = forms.ChoiceField(
        label='الإجابة الصحيحة (صح / خطأ)',
        choices=[('صح', 'صح'), ('خطأ', 'خطأ')],
        required=False,
        initial='صح',
        widget=forms.RadioSelect,
        help_text='حدّد الخيار الصحيح ليظهر بالأخضر للطالب بعد الإجابة.',
    )
    choice_1 = forms.CharField(label='خيار 1', required=False)
    choice_2 = forms.CharField(label='خيار 2', required=False)
    choice_3 = forms.CharField(label='خيار 3', required=False)
    choice_4 = forms.CharField(label='خيار 4', required=False)
    correct_choice = forms.ChoiceField(
        label='الخيار الصحيح',
        choices=[('1', 'الخيار 1'), ('2', 'الخيار 2'), ('3', 'الخيار 3'), ('4', 'الخيار 4')],
        required=False,
        initial='1',
        widget=forms.RadioSelect,
        help_text='علّم أي خيار هو الصحيح.',
    )

    class Meta:
        model = Question
        fields = ['question_type', 'question_text', 'question_audio', 'order', 'points']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance
        if not instance or not instance.pk:
            return
        if instance.question_type == 'true_false':
            correct = instance.choices.filter(is_correct=True).first()
            if correct and correct.choice_text in ('صح', 'خطأ'):
                self.fields['correct_true_false'].initial = correct.choice_text
            return
        choices = list(instance.choices.all()[:4])
        for i, choice in enumerate(choices, start=1):
            self.fields[f'choice_{i}'].initial = choice.choice_text
            if choice.is_correct:
                self.fields['correct_choice'].initial = str(i)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('question_type') != 'multiple_choice':
            return cleaned
        filled = [(cleaned.get(f'choice_{i}') or '').strip() for i in range(1, 5)]
        nonempty = [t for t in filled if t]
        has_existing = bool(self.instance.pk and self.instance.choices.exists())
        if len(nonempty) < 2 and not has_existing:
            raise ValidationError('أضف خيارين على الأقل لسؤال الاختيار من متعدد.')
        return cleaned

    def save(self, commit=True):
        question = super().save(commit=commit)
        if commit and question.pk:
            self.persist_choices(question)
        return question

    def persist_choices(self, question):
        qtype = question.question_type
        if qtype == 'true_false':
            _sync_true_false(question, self.cleaned_data.get('correct_true_false'))
            return
        if qtype == 'multiple_choice':
            texts = [(i, (self.cleaned_data.get(f'choice_{i}') or '').strip()) for i in range(1, 5)]
            _sync_mcq(question, texts, self.cleaned_data.get('correct_choice') or '1')


class QuestionAdminForm(forms.ModelForm):
    correct_true_false = forms.ChoiceField(
        label='الإجابة الصحيحة (صح / خطأ)',
        choices=[('صح', 'صح'), ('خطأ', 'خطأ')],
        required=False,
        initial='صح',
        widget=forms.RadioSelect,
        help_text='للاختيار من متعدد أضف الخيارات من الجدول أسفل الصفحة وعلّم «صحيح».',
    )

    class Meta:
        model = Question
        fields = ['quiz', 'question_type', 'question_text', 'question_audio', 'order', 'points']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = self.instance
        if instance and instance.pk and instance.question_type == 'true_false':
            correct = instance.choices.filter(is_correct=True).first()
            if correct and correct.choice_text in ('صح', 'خطأ'):
                self.fields['correct_true_false'].initial = correct.choice_text


class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4
    min_num = 0
    fields = ['choice_text', 'is_correct']
    verbose_name = 'خيار'
    verbose_name_plural = 'خيارات الإجابة — اكتب النص وعلّم الخيار الصحيح'


class QuestionInline(admin.StackedInline):
    model = Question
    form = QuestionInlineForm
    extra = 1
    show_change_link = True
    fieldsets = (
        (None, {
            'fields': ('question_type', 'question_text', 'question_audio', 'order', 'points'),
        }),
        ('صح / خطأ — حدّد الإجابة الصحيحة', {
            'fields': ('correct_true_false',),
            'classes': ('basera-tf-fields',),
        }),
        ('اختيار من متعدد — أضف الخيارات هنا', {
            'fields': ('choice_1', 'choice_2', 'choice_3', 'choice_4', 'correct_choice'),
            'classes': ('basera-mcq-fields',),
        }),
    )


@admin.register(Quiz)
class QuizAdmin(admin.ModelAdmin):
    list_display = ['title', 'lesson', 'passing_score', 'questions_count', 'created_at']
    list_filter = ['created_at', 'lesson__category', 'lesson']
    search_fields = ['title', 'description', 'lesson__title']
    inlines = [QuestionInline]
    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('lesson', 'title', 'description', 'passing_score'),
            'description': (
                'اربط الاختبار بدرس منشور ثم أضف الأسئلة أسفل الصفحة. '
                'للاختيار من متعدد اكتب الخيارات وعلّم الصحيح. '
                'لصح/خطأ اختر الإجابة الصحيحة.'
            ),
        }),
    )

    @admin.display(description='عدد الأسئلة')
    def questions_count(self, obj):
        return obj.questions.count()


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    form = QuestionAdminForm
    list_display = ['question_text_short', 'quiz', 'question_type', 'points', 'order']
    list_filter = ['question_type', 'quiz']
    search_fields = ['question_text', 'quiz__title']
    ordering = ['quiz', 'order']
    autocomplete_fields = ['quiz']

    def get_inlines(self, request, obj=None):
        if obj and obj.question_type == 'true_false':
            return []
        return [ChoiceInline]

    fieldsets = (
        (None, {
            'fields': ('quiz', 'question_type', 'question_text', 'question_audio', 'order', 'points'),
        }),
        ('صح / خطأ', {
            'fields': ('correct_true_false',),
            'classes': ('basera-tf-fields',),
            'description': 'حدّد الإجابة الصحيحة. للاختيار من متعدد استخدم الجدول أسفل الصفحة.',
        }),
    )

    @admin.display(description='نص السؤال')
    def question_text_short(self, obj):
        text = obj.question_text or ''
        return text[:70] + ('…' if len(text) > 70 else '')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.question_type == 'true_false':
            _sync_true_false(obj, form.cleaned_data.get('correct_true_false'))


@admin.register(QuizAttempt)
class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ['user', 'quiz', 'score', 'passed', 'started_at', 'completed_at']
    list_filter = ['passed', 'started_at', 'quiz']
    search_fields = ['user__username', 'quiz__title']
    readonly_fields = ['started_at', 'completed_at']


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['attempt', 'question', 'is_correct', 'points_earned', 'reviewed']
    list_filter = ['is_correct', 'reviewed']
    search_fields = ['attempt__user__username', 'question__question_text']
