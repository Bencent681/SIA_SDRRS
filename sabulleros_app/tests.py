from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import DocumentRequest

User = get_user_model()

STUDENT_PW = 'StudentPass123'
STAFF_PW = 'StaffPass123'


class DocumentRequestTestBase(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            username='student1', password=STUDENT_PW,
            first_name='Ana', last_name='Reyes', is_staff=False,
        )
        self.other_student = User.objects.create_user(
            username='student2', password=STUDENT_PW,
            first_name='Ben', last_name='Cruz', is_staff=False,
        )
        self.registrar = User.objects.create_user(
            username='registrar1', password=STAFF_PW,
            first_name='Registrar', is_staff=True,
        )
        self.request1 = DocumentRequest.objects.create(
            student_account=self.student,
            student_id='2024-0001',
            student_name='Ana Reyes',
            course='BS Information Technology',
            year_level=DocumentRequest.YearLevel.THIRD,
            document_type=DocumentRequest.DocumentType.CERTIFICATE_OF_ENROLLMENT,
        )

    def create_payload(self, **overrides):
        payload = {
            'student_id': '2024-0002',
            'student_name': 'Ben Cruz',
            'course': 'BS Computer Science',
            'year_level': DocumentRequest.YearLevel.SECOND,
            'document_type': DocumentRequest.DocumentType.TRANSCRIPT_OF_RECORDS,
        }
        payload.update(overrides)
        return payload


class ModelTests(DocumentRequestTestBase):
    def test_new_request_defaults_to_pending(self):
        self.assertEqual(self.request1.status, DocumentRequest.Status.PENDING)
        self.assertIsNone(self.request1.release_date)
        self.assertTrue(self.request1.request_date)

    def test_request_number_format(self):
        self.assertEqual(self.request1.request_no, f'REQ-{self.request1.pk:04d}')


class CreateTests(DocumentRequestTestBase):
    def test_student_can_submit_request(self):
        self.client.login(username='student1', password=STUDENT_PW)
        response = self.client.post(reverse('request_create'), self.create_payload())
        self.assertEqual(response.status_code, 302)

        new_request = DocumentRequest.objects.exclude(pk=self.request1.pk).get()
        self.assertEqual(new_request.student_account, self.student)
        self.assertEqual(new_request.status, DocumentRequest.Status.PENDING)
        self.assertIsNone(new_request.release_date)

    def test_student_cannot_inject_ready_status(self):
        self.client.login(username='student1', password=STUDENT_PW)
        self.client.post(
            reverse('request_create'),
            self.create_payload(status=DocumentRequest.Status.RELEASED),
        )
        new_request = DocumentRequest.objects.exclude(pk=self.request1.pk).get()
        self.assertEqual(new_request.status, DocumentRequest.Status.PENDING)

    def test_required_fields_are_validated(self):
        self.client.login(username='student1', password=STUDENT_PW)
        response = self.client.post(reverse('request_create'), {})
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context['form'], 'student_id', 'Student ID is required.')
        self.assertFormError(response.context['form'], 'student_name', 'Student Name is required.')

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse('request_create'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)


class ReadTests(DocumentRequestTestBase):
    def test_student_sees_only_own_requests(self):
        DocumentRequest.objects.create(
            student_account=self.other_student,
            student_id='2024-9999',
            student_name='Ben Cruz',
            course='BS Computer Science',
            year_level=DocumentRequest.YearLevel.SECOND,
            document_type=DocumentRequest.DocumentType.SCHOOL_CLEARANCE,
        )
        self.client.login(username='student1', password=STUDENT_PW)
        response = self.client.get(reverse('request_list'))
        self.assertContains(response, 'REQ-%04d' % self.request1.pk)
        self.assertNotContains(response, '2024-9999')

    def test_student_cannot_view_another_students_request(self):
        other = DocumentRequest.objects.create(
            student_account=self.other_student,
            student_id='2024-9999',
            student_name='Ben Cruz',
            course='BS Computer Science',
            year_level=DocumentRequest.YearLevel.SECOND,
            document_type=DocumentRequest.DocumentType.SCHOOL_CLEARANCE,
        )
        self.client.login(username='student1', password=STUDENT_PW)
        response = self.client.get(reverse('request_detail', args=[other.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('request_list'))

    def test_registrar_sees_all_requests(self):
        DocumentRequest.objects.create(
            student_account=self.other_student,
            student_id='2024-9999',
            student_name='Ben Cruz',
            course='BS Computer Science',
            year_level=DocumentRequest.YearLevel.SECOND,
            document_type=DocumentRequest.DocumentType.SCHOOL_CLEARANCE,
        )
        self.client.login(username='registrar1', password=STAFF_PW)
        response = self.client.get(reverse('request_list'))
        self.assertContains(response, '2024-9999')
        self.assertContains(response, '2024-0001')

    def test_registrar_search_filters_queryset(self):
        self.client.login(username='registrar1', password=STAFF_PW)
        response = self.client.get(reverse('request_list'), {'q': 'Ana'})
        self.assertContains(response, '2024-0001')
        response = self.client.get(reverse('request_list'), {'q': 'NobodyHere'})
        self.assertNotContains(response, '2024-0001')


class AccessControlTests(DocumentRequestTestBase):
    def test_student_cannot_access_edit(self):
        self.client.login(username='student1', password=STUDENT_PW)
        response = self.client.get(reverse('request_edit', args=[self.request1.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

    def test_student_cannot_access_delete(self):
        self.client.login(username='student1', password=STUDENT_PW)
        response = self.client.get(reverse('request_delete', args=[self.request1.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('dashboard'))

    def test_student_cannot_call_mark_ready(self):
        self.client.login(username='student1', password=STUDENT_PW)
        self.client.post(reverse('mark_ready', args=[self.request1.pk]))
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DocumentRequest.Status.PENDING)

    def test_student_cannot_call_mark_released(self):
        self.client.login(username='student1', password=STUDENT_PW)
        self.client.post(reverse('mark_released', args=[self.request1.pk]))
        self.request1.refresh_from_db()
        self.assertIsNone(self.request1.release_date)


class WorkflowTests(DocumentRequestTestBase):
    def setUp(self):
        super().setUp()
        self.client.login(username='registrar1', password=STAFF_PW)

    def test_mark_ready(self):
        response = self.client.post(reverse('mark_ready', args=[self.request1.pk]))
        self.assertEqual(response.status_code, 302)
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DocumentRequest.Status.READY)

    def test_cannot_release_a_pending_request(self):
        self.client.post(reverse('mark_released', args=[self.request1.pk]))
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DocumentRequest.Status.PENDING)
        self.assertIsNone(self.request1.release_date)

    def test_mark_released_records_release_date(self):
        self.client.post(reverse('mark_ready', args=[self.request1.pk]))
        self.client.post(reverse('mark_released', args=[self.request1.pk]))
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DocumentRequest.Status.RELEASED)
        self.assertIsNotNone(self.request1.release_date)

    def test_released_request_is_announced_on_its_student_dashboard(self):
        self.request1.status = DocumentRequest.Status.RELEASED
        self.request1.release_date = timezone.now()
        self.request1.save(update_fields=['status', 'release_date'])
        self.client.force_login(self.student)

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, 'Your document has been released')
        self.assertContains(response, self.request1.document_type)
        self.assertContains(response, self.request1.request_no)
        self.assertContains(response, reverse('request_detail', args=[self.request1.pk]))

    def test_dashboard_release_updates_only_include_logged_in_students_requests(self):
        other_release = DocumentRequest.objects.create(
            student_account=self.other_student,
            student_id='2024-9999',
            student_name='Ben Cruz',
            course='BS Computer Science',
            year_level=DocumentRequest.YearLevel.SECOND,
            document_type=DocumentRequest.DocumentType.SCHOOL_CLEARANCE,
            status=DocumentRequest.Status.RELEASED,
            release_date=timezone.now(),
        )
        self.request1.status = DocumentRequest.Status.RELEASED
        self.request1.release_date = timezone.now()
        self.request1.save(update_fields=['status', 'release_date'])
        self.client.force_login(self.student)

        response = self.client.get(reverse('dashboard'))

        self.assertContains(response, self.request1.request_no)
        self.assertNotContains(response, other_release.request_no)

    def test_edit_updates_remarks_and_status(self):
        payload = self.create_payload(
            student_id=self.request1.student_id,
            student_name=self.request1.student_name,
            course=self.request1.course,
            year_level=self.request1.year_level,
            document_type=self.request1.document_type,
            status=DocumentRequest.Status.READY,
            remarks='Ready for pickup at the Registrar office.',
            student_account=self.student.pk,
        )
        response = self.client.post(
            reverse('request_edit', args=[self.request1.pk]), payload
        )
        self.assertEqual(response.status_code, 302)
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DocumentRequest.Status.READY)
        self.assertIn('pickup', self.request1.remarks)

    def test_cannot_move_status_backwards(self):
        self.request1.status = DocumentRequest.Status.RELEASED
        self.request1.save(update_fields=['status'])
        payload = self.create_payload(
            student_id=self.request1.student_id,
            student_name=self.request1.student_name,
            course=self.request1.course,
            year_level=self.request1.year_level,
            document_type=self.request1.document_type,
            status=DocumentRequest.Status.PENDING,
            student_account=self.student.pk,
        )
        response = self.client.post(
            reverse('request_edit', args=[self.request1.pk]), payload
        )
        self.assertEqual(response.status_code, 200)
        self.request1.refresh_from_db()
        self.assertEqual(self.request1.status, DocumentRequest.Status.RELEASED)

    def test_delete_request(self):
        response = self.client.post(reverse('request_delete', args=[self.request1.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(DocumentRequest.objects.filter(pk=self.request1.pk).exists())


class AccountTests(TestCase):
    def signup_payload(self, **overrides):
        payload = {
            'first_name': 'Taylor',
            'last_name': 'Student',
            'username': 'taylor_student',
            'email': 'taylor@example.edu',
            'password1': 'StudentPass123',
            'password2': 'StudentPass123',
        }
        payload.update(overrides)
        return payload

    def test_student_can_sign_up_and_is_signed_in_without_staff_access(self):
        response = self.client.post(
            reverse('signup'),
            self.signup_payload(is_staff='true', is_superuser='true'),
        )
        self.assertRedirects(response, reverse('dashboard'))

        user = User.objects.get(username='taylor_student')
        self.assertEqual(user.email, 'taylor@example.edu')
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        dashboard_response = self.client.get(reverse('dashboard'))
        self.assertEqual(dashboard_response.wsgi_request.user.pk, user.pk)

    def test_sign_up_rejects_an_email_already_in_use(self):
        User.objects.create_user(
            username='existing_student',
            email='taylor@example.edu',
            password=STUDENT_PW,
        )
        response = self.client.post(
            reverse('signup'), self.signup_payload(email='TAYLOR@example.edu')
        )
        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context['form'],
            'email',
            'An account with this email already exists.',
        )
        self.assertFalse(User.objects.filter(username='taylor_student').exists())

    def test_authenticated_student_is_redirected_from_sign_up(self):
        user = User.objects.create_user(username='existing_student', password=STUDENT_PW)
        self.client.force_login(user)
        response = self.client.get(reverse('signup'))
        self.assertRedirects(response, reverse('dashboard'))

    def test_logout_ends_the_session(self):
        user = User.objects.create_user(username='existing_student', password=STUDENT_PW)
        self.client.force_login(user)
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'))
        protected_response = self.client.get(reverse('dashboard'))
        self.assertRedirects(
            protected_response,
            f'{reverse("login")}?next={reverse("dashboard")}',
            fetch_redirect_response=False,
        )


class AdminReleaseActionTests(DocumentRequestTestBase):
    def setUp(self):
        super().setUp()
        self.admin_user = User.objects.create_superuser(
            username='admin_user',
            email='admin@example.edu',
            password='AdminPass123',
        )
        self.ready_request = DocumentRequest.objects.create(
            student_account=self.student,
            student_id='2024-0003',
            student_name='Ana Reyes',
            course='BS Information Technology',
            year_level=DocumentRequest.YearLevel.THIRD,
            document_type=DocumentRequest.DocumentType.SCHOOL_CLEARANCE,
            status=DocumentRequest.Status.READY,
        )
        self.client.force_login(self.admin_user)

    def test_admin_action_releases_ready_requests_only(self):
        released_request = DocumentRequest.objects.create(
            student_account=self.other_student,
            student_id='2024-0004',
            student_name='Ben Cruz',
            course='BS Computer Science',
            year_level=DocumentRequest.YearLevel.SECOND,
            document_type=DocumentRequest.DocumentType.SCHOOL_CLEARANCE,
            status=DocumentRequest.Status.RELEASED,
        )
        response = self.client.post(
            reverse('admin:sabulleros_app_documentrequest_changelist'),
            {
                'action': 'release_ready_documents',
                '_selected_action': [
                    str(self.request1.pk),
                    str(self.ready_request.pk),
                    str(released_request.pk),
                ],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.ready_request.refresh_from_db()
        self.request1.refresh_from_db()
        released_request.refresh_from_db()
        self.assertEqual(self.ready_request.status, DocumentRequest.Status.RELEASED)
        self.assertIsNotNone(self.ready_request.release_date)
        self.assertEqual(self.request1.status, DocumentRequest.Status.PENDING)
        self.assertIsNone(self.request1.release_date)
        self.assertEqual(released_request.status, DocumentRequest.Status.RELEASED)
        self.assertIsNone(released_request.release_date)