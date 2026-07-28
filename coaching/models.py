import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

class User(AbstractUser):
    ROLE_CHOICES = (
        ('super_admin', 'Super Admin'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')
    face_data = models.TextField(blank=True, null=True, help_text="Base64 encoded profile photo for user accounts")

    def is_super_admin(self):
        return self.role == 'super_admin' or self.is_superuser

    def is_teacher(self):
        return self.role == 'teacher'

    def is_student(self):
        return self.role == 'student'

class Batch(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    timing = models.CharField(max_length=100, help_text="e.g. Mon-Wed-Fri 7:15 PM - 8:15 PM")
    start_time = models.TimeField(default='09:00:00', help_text="Batch start time (e.g. 19:15 for 7:15 PM)")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Batches"

    def get_effective_start_time(self):
        import re, datetime
        # If start_time was explicitly set (not default 09:00:00), return start_time
        if self.start_time and str(self.start_time) != '09:00:00' and self.start_time != datetime.time(9, 0):
            return self.start_time
        
        # Smart parse from timing string: e.g. "Mon-Fri 7:15 PM - 8:15 PM" or "7:15 PM"
        if self.timing:
            match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?', self.timing)
            if match:
                hrs = int(match.group(1))
                mins = int(match.group(2))
                ampm = match.group(3)
                if ampm:
                    ampm = ampm.upper()
                    if ampm == 'PM' and hrs < 12:
                        hrs += 12
                    elif ampm == 'AM' and hrs == 12:
                        hrs = 0
                return datetime.time(hrs, mins)
        
        return self.start_time or datetime.time(9, 0)

    def __str__(self):
        return self.name

class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    class_std = models.CharField(max_length=50, blank=True, null=True, verbose_name="Class/Std")
    school_college = models.CharField(max_length=200, verbose_name="School/College")
    contact_number = models.CharField(max_length=15)
    parent_contact = models.CharField(max_length=15)
    joining_date = models.DateField(default=timezone.now)
    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, related_name='students')
    monthly_fee = models.DecimalField(max_digits=10, decimal_places=2)
    next_due_date = models.DateField()
    qr_code_token = models.CharField(max_length=100, unique=True, default=uuid.uuid4)
    face_data = models.TextField(blank=True, null=True, help_text="Deprecated photo data")

    def __str__(self):
        return self.user.get_full_name() or self.user.username

class AttendanceRecord(models.Model):
    MARKED_BY_CHOICES = (
        ('self_qr', 'Self QR Scan'),
        ('teacher', 'Teacher'),
    )
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
    )
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField(default=timezone.now)
    time_in = models.TimeField(auto_now_add=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')
    minutes_late = models.IntegerField(default=0, help_text="Minutes late relative to batch start time")
    marked_by = models.CharField(max_length=20, choices=MARKED_BY_CHOICES, default='teacher')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'date'], name='unique_student_daily_attendance')
        ]
        ordering = ['-date', '-time_in']

    def __str__(self):
        return f"{self.student} - {self.date} ({self.get_status_display()})"

class DailyBatchAttendanceLock(models.Model):
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='attendance_locks')
    date = models.DateField(default=timezone.now)
    is_locked = models.BooleanField(default=True)
    locked_at = models.DateTimeField(auto_now=True)
    locked_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['batch', 'date'], name='unique_batch_daily_lock')
        ]
        ordering = ['-date']

    def __str__(self):
        status = "Locked" if self.is_locked else "Unlocked"
        return f"{self.batch.name} - {self.date} ({status})"

class FeePayment(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='payments')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(default=timezone.now)
    collected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='collected_payments')
    remarks = models.TextField(blank=True)

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.student} - {self.amount_paid} on {self.payment_date}"

class ClassSchedule(models.Model):
    batch = models.ForeignKey(Batch, on_delete=models.CASCADE, related_name='schedules')
    title = models.CharField(max_length=200)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_holiday = models.BooleanField(default=False)

    class Meta:
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"{self.batch.name} - {self.title} on {self.date}"
