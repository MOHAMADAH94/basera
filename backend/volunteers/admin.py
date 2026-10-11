from django.contrib import admin
from .models import TranscriptionReview, AudioRecording, VolunteerRole


@admin.register(VolunteerRole)
class VolunteerRoleAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'category', 'tasks_completed', 'is_active', 'assigned_at']
    list_filter = ['role', 'is_active', 'category']
    search_fields = ['user__username', 'category__name']
    readonly_fields = ['assigned_at']
    autocomplete_fields = ['user', 'category']

    fieldsets = (
        ('المعلومات الأساسية', {
            'fields': ('user', 'role', 'category'),
        }),
        ('الإحصائيات', {
            'fields': ('tasks_completed', 'tasks_in_progress'),
        }),
        ('الحالة', {
            'fields': ('is_active', 'assigned_at'),
        }),
    )


@admin.register(TranscriptionReview)
class TranscriptionReviewAdmin(admin.ModelAdmin):
    list_display = ['lesson', 'reviewer', 'status', 'reviewed_at']
    list_filter = ['status', 'reviewed_at']
    search_fields = ['lesson__title', 'reviewer__username']
    autocomplete_fields = ['lesson', 'reviewer']


@admin.register(AudioRecording)
class AudioRecordingAdmin(admin.ModelAdmin):
    list_display = ['title', 'recorded_by', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['title', 'description']
    autocomplete_fields = ['recorded_by']
