from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from coaching.models import User, Batch, StudentProfile, AttendanceRecord, FeePayment
import datetime

class CoachingSecurityTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # 1. Create a Batch
        self.batch = Batch.objects.create(
            name="Test Batch",
            timing="Mon-Fri 10AM-12PM"
        )
        
        # 2. Create Student User & Profile
        self.student_user = User.objects.create_user(
            username="student_alice",
            email="alice@test.com",
            first_name="Alice",
            last_name="Green",
            role="student"
        )
        self.student_user.set_password("pass123")
        self.student_user.save()
        
        self.student_profile = StudentProfile.objects.create(
            user=self.student_user,
            age=16,
            school_college="Test High School",
            contact_number="1234567890",
            parent_contact="0987654321",
            joining_date=timezone.localdate(),
            batch=self.batch,
            monthly_fee=150.00,
            next_due_date=timezone.localdate() + datetime.timedelta(days=30),
            qr_code_token="QR-ALICE-TOKEN"
        )

        # 3. Create Teacher User
        self.teacher_user = User.objects.create_user(
            username="teacher_john",
            email="john@test.com",
            first_name="John",
            last_name="Doe",
            role="teacher"
        )
        self.teacher_user.set_password("pass123")
        self.teacher_user.save()

    def test_student_dashboard_disabled(self):
        """
        Verify that student dashboard returns 404 since it has been disabled.
        """
        self.client.login(username="student_alice", password="pass123")
        response = self.client.get(reverse('student_dashboard'))
        self.assertEqual(response.status_code, 404)

    def test_student_blocked_from_teacher_views(self):
        """
        Verify that students cannot access teacher-only views.
        """
        self.client.login(username="student_alice", password="pass123")
        
        # Blocked from Student Detail page
        detail_url = reverse('student_detail', kwargs={'student_id': self.student_profile.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 403) # PermissionDenied raised by decorator
        
        # Blocked from Student registration
        reg_url = reverse('register_student')
        response = self.client.get(reg_url)
        self.assertEqual(response.status_code, 403)
        
        # Blocked from Fee scanner view
        fee_scan_url = reverse('scanner_fees')
        response = self.client.get(fee_scan_url)
        self.assertEqual(response.status_code, 403)

    def test_teacher_can_access_views(self):
        """
        Verify that teachers can access student detail profiles and registration views.
        """
        self.client.login(username="teacher_john", password="pass123")
        
        # Access Student detail
        detail_url = reverse('student_detail', kwargs={'student_id': self.student_profile.id})
        response = self.client.get(detail_url)
        self.assertEqual(response.status_code, 200)
        
        # Access registration wizard
        response = self.client.get(reverse('register_student'))
        self.assertEqual(response.status_code, 200)


class AttendanceLogicTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Set up a student
        self.batch = Batch.objects.create(name="Science Batch", timing="Mon-Wed-Fri")
        self.student_user = User.objects.create_user(username="student_bob", role="student")
        self.student_user.set_password("pass123")
        self.student_user.save()
        
        self.profile = StudentProfile.objects.create(
            user=self.student_user,
            age=15,
            school_college="College B",
            contact_number="1111",
            parent_contact="2222",
            joining_date=timezone.localdate(),
            batch=self.batch,
            monthly_fee=100.00,
            next_due_date=timezone.localdate() + datetime.timedelta(days=30),
            qr_code_token="QR-BOB-TOKEN"
        )
        self.client.login(username="student_bob", password="pass123")

    def test_prevent_double_attendance(self):
        """
        Assert that the system prevents marking attendance more than once on the same day.
        """
        # First check-in
        response = self.client.post(
            reverse('mark_attendance_api'),
            data={'qr_token': 'QR-BOB-TOKEN', 'marked_by': 'self_qr'},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'], msg=data.get('message', 'No message'))
        self.assertEqual(data['message'], 'Attendance marked successfully!')
        
        # Confirm record created
        self.assertEqual(AttendanceRecord.objects.filter(student=self.profile).count(), 1)
        
        # Second check-in on the same day
        response2 = self.client.post(
            reverse('mark_attendance_api'),
            data={'qr_token': 'QR-BOB-TOKEN', 'marked_by': 'self_qr'},
            content_type='application/json'
        )
        self.assertEqual(response2.status_code, 200)
        data2 = response2.json()
        self.assertFalse(data2['success'])
        self.assertIn('already marked present', data2['message'])
        
        # Verify record count is still 1
        self.assertEqual(AttendanceRecord.objects.filter(student=self.profile).count(), 1)
