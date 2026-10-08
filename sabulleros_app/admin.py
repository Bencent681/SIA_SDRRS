from django.contrib import admin
from django.utils import timezone

from .models import DocumentRequest


@admin.register(DocumentRequest)
class DocumentRequestAdmin(admin.ModelAdmin):
    actions = ('release_ready_documents',)
    list_display = (
        'request_id',
        'student_id',
        'student_name',
        'course',
        'year_level',
        'document_type',
        'status',
        'request_date',
        'release_date',
    )
    list_filter = ('status', 'document_type', 'request_date', 'year_level')
    search_fields = ('request_id', 'student_id', 'student_name', 'course')
    readonly_fields = ('request_date',)
    date_hierarchy = 'request_date'
    ordering = ('-request_date',)
    fieldsets = (
        ('Student Information', {
            'fields': ('student_account', 'student_id', 'student_name', 'course', 'year_level'),
        }),
        ('Request', {
            'fields': ('document_type', 'status', 'request_date', 'release_date', 'remarks'),
        }),
    )

    @admin.action(description='Release selected ready documents')
    def release_ready_documents(self, request, queryset):
        ready_requests = queryset.filter(status=DocumentRequest.Status.READY)
        released_count = ready_requests.update(
            status=DocumentRequest.Status.RELEASED,
            release_date=timezone.now(),
        )
        skipped_count = queryset.count() - released_count

        if released_count:
            self.message_user(
                request,
                f'{released_count} document(s) released successfully.',
                level='success',
            )
        if skipped_count:
            self.message_user(
                request,
                f'{skipped_count} selected request(s) were not Ready and were not released.',
                level='warning',
            )
