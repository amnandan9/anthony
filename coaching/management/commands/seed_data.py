import datetime
import uuid
from django.core.management.base import BaseCommand
from django.utils import timezone
from coaching.models import User, Batch, StudentProfile, AttendanceRecord, FeePayment, ClassSchedule

class Command(BaseCommand):
    help = 'Seeds the database with coaching center initial data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')

        # 1. Create Super Admin
        admin_user, created = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@coaching.com',
                'first_name': 'Super',
                'last_name': 'Admin',
                'role': 'super_admin',
                'is_staff': True,
                'is_superuser': True
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('Created Super Admin: admin / admin123'))
        else:
            self.stdout.write('Super Admin admin already exists.')

        # 2. Create Teachers
        teachers_data = [
            ('teacher1', 'teacher123', 'John', 'Doe', 'john@coaching.com'),
            ('teacher2', 'teacher123', 'Jane', 'Smith', 'jane@coaching.com')
        ]
        teachers = []
        for username, password, first, last, email in teachers_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first,
                    'last_name': last,
                    'role': 'teacher',
                    'is_staff': True
                }
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Created Teacher: {username} / {password}'))
            teachers.append(user)

        # 3. Create Batches
        batches_data = [
            ('Morning Science Batch', 'Science lectures for high school students', 'Mon-Wed-Fri 08:00 AM - 10:00 AM'),
            ('Evening Maths Batch', 'Mathematics coaching for college level', 'Tue-Thu-Sat 05:00 PM - 07:00 PM'),
            ('Weekend Programming Batch', 'Introduction to Python & Django', 'Sat-Sun 10:00 AM - 01:00 PM')
        ]
        batches = []
        for name, desc, timing in batches_data:
            batch, created = Batch.objects.get_or_create(
                name=name,
                defaults={'description': desc, 'timing': timing}
            )
            batches.append(batch)
            self.stdout.write(f'Ensured Batch: {name}')

        # 4. Create Students
        students_data = [
            ('student1', 'student123', 'Alice', 'Green', 'alice@gmail.com', '10th Std', 'High School West', '9876543210', '9876543211', batches[0], 150.00),
            ('student2', 'student123', 'Bob', 'Brown', 'bob@gmail.com', '11th Std', 'High School West', '8765432109', '8765432108', batches[0], 150.00),
            ('student3', 'student123', 'Charlie', 'Davis', 'charlie@gmail.com', '12th Std', 'State College', '7654321098', '7654321097', batches[1], 200.00),
            ('student4', 'student123', 'David', 'Evans', 'david@gmail.com', 'College Fresh', 'State College', '6543210987', '6543210986', batches[2], 250.00)
        ]
        
        today = timezone.localdate()
        next_month = today + datetime.timedelta(days=30)

        for username, password, first, last, email, class_std, school, contact, parent, batch, fee in students_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'first_name': first,
                    'last_name': last,
                    'role': 'student'
                }
            )
            if created:
                user.set_password(password)
                user.save()
                
                # Create Profile
                profile = StudentProfile.objects.create(
                    user=user,
                    class_std=class_std,
                    school_college=school,
                    contact_number=contact,
                    parent_contact=parent,
                    joining_date=today - datetime.timedelta(days=15),
                    batch=batch,
                    monthly_fee=fee,
                    next_due_date=next_month,
                    qr_code_token=f"QR-{username.upper()}-SECRET-KEY"
                )
                self.stdout.write(self.style.SUCCESS(f'Created Student: {username} / {password} with QR: {profile.qr_code_token}'))

                # Seed some attendance
                # Present for the last 5 days
                for i in range(1, 6):
                    class_date = today - datetime.timedelta(days=i)
                    AttendanceRecord.objects.get_or_create(
                        student=profile,
                        date=class_date,
                        defaults={
                            'status': 'present',
                            'marked_by': 'teacher'
                        }
                    )
                
                # Seed fee payment
                FeePayment.objects.get_or_create(
                    student=profile,
                    amount_paid=fee,
                    payment_date=today - datetime.timedelta(days=15),
                    defaults={
                        'collected_by': teachers[0],
                        'remarks': "First month fee paid upon joining."
                    }
                )

        # 5. Create Schedules
        schedules_data = [
            (batches[0], 'Physics - Laws of Motion', today, datetime.time(8, 0), datetime.time(10, 0)),
            (batches[0], 'Chemistry - Organic Bonds', today + datetime.timedelta(days=2), datetime.time(8, 0), datetime.time(10, 0)),
            (batches[1], 'Algebraic Functions', today, datetime.time(17, 0), datetime.time(19, 0)),
            (batches[1], 'Calculus Introduction', today + datetime.timedelta(days=1), datetime.time(17, 0), datetime.time(19, 0)),
            (batches[2], 'Python Variables & Control Flow', today + datetime.timedelta(days=4), datetime.time(10, 0), datetime.time(13, 0)),
        ]
        
        for batch, title, date, start, end in schedules_data:
            ClassSchedule.objects.get_or_create(
                batch=batch,
                title=title,
                date=date,
                defaults={'start_time': start, 'end_time': end}
            )
            self.stdout.write(f'Ensured Class Schedule: {title} for {batch.name}')

        self.stdout.write(self.style.SUCCESS('Successfully seeded database!'))
