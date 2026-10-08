from django.conf import settings
from django.db import models
from django.urls import reverse


class DocumentRequest(models.Model):
    """A student's request for an official school document.

    Workflow: Pending -> Ready -> Released
    """

    class DocumentType(models.TextChoices):
        CERTIFICATE_OF_ENROLLMENT = 'Certificate of Enrollment', 'Certificate of Enrollment'
        TRANSCRIPT_OF_RECORDS = 'Transcript of Records', 'Transcript of Records'
        CERTIFICATE_OF_GRADES = 'Certificate of Grades', 'Certificate of Grades'
        GOOD_MORAL_CERTIFICATE = 'Good Moral Certificate', 'Good Moral Certificate'
        SCHOOL_CLEARANCE = 'School Clearance', 'School Clearance'

    class Status(models.TextChoices):
        PENDING = 'Pending', 'Pending'
        READY = 'Ready', 'Ready'
        RELEASED = 'Released', 'Released'

    class YearLevel(models.TextChoices):
        FIRST = '1st Year', '1st Year'
        SECOND = '2nd Year', '2nd Year'
        THIRD = '3rd Year', '3rd Year'
        FOURTH = '4th Year', '4th Year'
        FIFTH = '5th Year', '5th Year'

    STATUS_ORDER = {
        Status.PENDING: 0,
        Status.READY: 1,
        Status.RELEASED: 2,
    }

    request_id = models.AutoField(primary_key=True, verbose_name='Request ID')
    student_account = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='document_requests',
        verbose_name='Student Account',
    )
    student_id = models.CharField('Student ID', max_length=30)
    student_name = models.CharField('Student Name', max_length=150)
    course = models.CharField('Course', max_length=100)
    year_level = models.CharField('Year Level', max_length=20, choices=YearLevel.choices)
    document_type = models.CharField(
        'Document Type',
        max_length=50,
        choices=DocumentType.choices,
    )
    request_date = models.DateTimeField('Request Date', auto_now_add=True)
    status = models.CharField(
        'Status',
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    release_date = models.DateTimeField('Release Date', null=True, blank=True)
    remarks = models.TextField('Remarks', blank=True, default='')

    class Meta:
        ordering = ['-request_date', '-request_id']
        verbose_name = 'Document Request'
        verbose_name_plural = 'Document Requests'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['document_type']),
        ]

    def __str__(self):
        return f'{self.request_no} - {self.document_type} ({self.student_name})'

    @property
    def request_no(self):
        if self.request_id is None:
            return 'REQ-????'
        return f'REQ-{self.request_id:04d}'

    def get_absolute_url(self):
        return reverse('request_detail', args=[self.pk])

    def can_mark_ready(self):
        return self.status == self.Status.PENDING

    def can_mark_released(self):
        return self.status == self.Status.READY

