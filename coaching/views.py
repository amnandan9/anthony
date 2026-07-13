import json
import datetime
from django.shortcuts import render, redirect, get_object_or_454
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from coaching.models import User, Batch, StudentProfile, AttendanceRecord, FeePayment, ClassSchedule
from coaching.decorators import super_admin_required, teacher_required, student_required, role_required

# --- Authentication Views ---

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, "This account is inactive. Please contact the administrator.")
                return render(request, 'coaching/login.html')
            login(request, user)
            return redirect('dashboard_redirect')
        else:
            messages.error(request, "Invalid username or password.")
            
    return render(request, 'coaching/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
def dashboard_redirect(request):
    if request.user.role == 'super_admin' or request.user.is_superuser:
        return redirect('super_admin_dashboard')
    elif request.user.role == 'teacher':
        return redirect('teacher_dashboard')
    elif request.user.role == 'student':
        return redirect('student_dashboard')
    else:
        return redirect('login')

# --- Super Admin Views ---

@login_required
@super_admin_required
def super_admin_dashboard(request):
    teachers = User.objects.filter(role='teacher')
    
    # Calculate global analytics
    total_teachers = teachers.count()
    total_students = StudentProfile.objects.filter(user__is_active=True).count()
    
    today = timezone.localdate()
    first_of_month = today.replace(day=1)
    monthly_revenue = FeePayment.objects.filter(payment_date__gte=first_of_month).aggregate(total=Sum('amount_paid'))['total'] or 0.00
    
    # Attendance Rate: Present counts / Total records
    total_att = AttendanceRecord.objects.all().count()
    present_att = AttendanceRecord.objects.filter(status='present').count()
    overall_attendance = int((present_att / total_att * 100)) if total_att > 0 else 100

    context = {
        'teachers': teachers,
        'total_teachers': total_teachers,
        'total_students': total_students,
        'monthly_revenue': monthly_revenue,
        'overall_attendance': overall_attendance,
        'batches': Batch.objects.all(),
    }
    return render(request, 'coaching/super_admin_dashboard.html', context)

@login_required
@super_admin_required
def manage_teacher(request, teacher_id=None):
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'create':
            username = request.POST.get('username')
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            password = request.POST.get('password')
            
            if User.objects.filter(username=username).exists():
                messages.error(request, f"Username '{username}' already exists.")
            else:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role='teacher',
                    is_staff=True
                )
                user.set_password(password)
                user.save()
                messages.success(request, f"Teacher {user.get_full_name()} successfully registered.")
                
        elif action == 'toggle_active':
            teacher = get_object_or_454(User, id=teacher_id, role='teacher')
            teacher.is_active = not teacher.is_active
            teacher.save()
            status = "activated" if teacher.is_active else "deactivated"
            messages.success(request, f"Teacher {teacher.get_full_name()} has been {status}.")
            
    return redirect('super_admin_dashboard')

# --- Teacher Views ---

@login_required
@teacher_required
def teacher_dashboard(request):
    today = timezone.localdate()
    first_of_month = today.replace(day=1)
    
    # 1. Dashboard summary boxes
    # Daily Attendance rate
    todays_total_schedules = ClassSchedule.objects.filter(date=today, is_holiday=False).count()
    todays_att_records = AttendanceRecord.objects.filter(date=today)
    todays_present = todays_att_records.filter(status='present').count()
    todays_total = todays_att_records.count()
    todays_attendance_rate = int((todays_present / todays_total * 100)) if todays_total > 0 else 0
    
    # Monthly fee collected
    monthly_fees_collected = FeePayment.objects.filter(payment_date__gte=first_of_month).aggregate(total=Sum('amount_paid'))['total'] or 0.00
    
    # Pending Dues count and list
    overdue_students = StudentProfile.objects.filter(next_due_date__lte=today, user__is_active=True)
    pending_dues_count = overdue_students.count()
    
    # Newly registered students (last 30 days)
    thirty_days_ago = today - datetime.timedelta(days=30)
    new_registers_count = StudentProfile.objects.filter(joining_date__gte=thirty_days_ago, user__is_active=True).count()
    
    # 2. Student Directory list with search/filters
    students = StudentProfile.objects.filter(user__is_active=True)
    query = request.GET.get('q', '')
    batch_filter = request.GET.get('batch', '')
    due_filter = request.GET.get('due', '')
    
    if query:
        students = students.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__username__icontains=query) |
            Q(school_college__icontains=query)
        )
    if batch_filter:
        students = students.filter(batch_id=batch_filter)
    if due_filter == 'overdue':
        students = students.filter(next_due_date__lte=today)
    elif due_filter == 'cleared':
        students = students.filter(next_due_date__gt=today)

    # 3. Calendar classes & events
    classes_this_month = ClassSchedule.objects.filter(date__year=today.year, date__month=today.month)
    batches = Batch.objects.all()

    # Form schemas and structures
    context = {
        'todays_attendance_rate': todays_attendance_rate,
        'todays_present': todays_present,
        'todays_total': todays_total,
        'monthly_fees_collected': monthly_fees_collected,
        'pending_dues_count': pending_dues_count,
        'new_registers_count': new_registers_count,
        'students': students,
        'batches': batches,
        'calendar_classes': classes_this_month,
        'overdue_students': overdue_students,
        'today': today,
        'selected_batch': batch_filter,
        'selected_due': due_filter,
        'search_query': query,
    }
    return render(request, 'coaching/teacher_dashboard.html', context)

@login_required
@teacher_required
def register_student(request):
    batches = Batch.objects.all()
    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        age = request.POST.get('age')
        school = request.POST.get('school_college')
        contact = request.POST.get('contact_number')
        parent_contact = request.POST.get('parent_contact')
        joining_date = request.POST.get('joining_date') or timezone.localdate()
        batch_id = request.POST.get('batch')
        fee = request.POST.get('monthly_fee')
        next_due = request.POST.get('next_due_date')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists.")
            return render(request, 'coaching/register_student.html', {'batches': batches})
            
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role='student'
        )
        user.set_password(password)
        user.save()
        
        batch = Batch.objects.filter(id=batch_id).first() if batch_id else None
        
        profile = StudentProfile.objects.create(
            user=user,
            age=age,
            school_college=school,
            contact_number=contact,
            parent_contact=parent_contact,
            joining_date=joining_date,
            batch=batch,
            monthly_fee=fee,
            next_due_date=next_due
        )
        
        messages.success(request, f"Student {user.get_full_name()} registered successfully!")
        return redirect('teacher_dashboard')
        
    return render(request, 'coaching/register_student.html', {'batches': batches, 'today': timezone.localdate()})

@login_required
@teacher_required
def edit_student(request, student_id):
    profile = get_object_or_454(StudentProfile, id=student_id)
    batches = Batch.objects.all()
    
    if request.method == 'POST':
        user = profile.user
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.save()
        
        profile.age = request.POST.get('age')
        profile.school_college = request.POST.get('school_college')
        profile.contact_number = request.POST.get('contact_number')
        profile.parent_contact = request.POST.get('parent_contact')
        profile.joining_date = request.POST.get('joining_date')
        profile.monthly_fee = request.POST.get('monthly_fee')
        profile.next_due_date = request.POST.get('next_due_date')
        
        batch_id = request.POST.get('batch')
        profile.batch = Batch.objects.filter(id=batch_id).first() if batch_id else None
        profile.save()
        
        messages.success(request, f"Student {user.get_full_name()} updated successfully.")
        return redirect('student_detail', student_id=student_id)
        
    return render(request, 'coaching/edit_student.html', {'profile': profile, 'batches': batches})

@login_required
@teacher_required
def student_detail(request, student_id):
    profile = get_object_or_454(StudentProfile, id=student_id)
    payments = FeePayment.objects.filter(student=profile)
    attendance = AttendanceRecord.objects.filter(student=profile)
    
    # Statistics calculations
    # 1. Total classes conducted for this batch since they joined
    classes_conducted = ClassSchedule.objects.filter(
        batch=profile.batch,
        date__gte=profile.joining_date,
        date__lte=timezone.localdate(),
        is_holiday=False
    ).count()
    
    # 2. Classes attended
    classes_attended = attendance.filter(status='present').count()
    
    # 3. Attendance Rate
    attendance_rate = int((classes_attended / classes_conducted * 100)) if classes_conducted > 0 else 100
    
    context = {
        'profile': profile,
        'payments': payments,
        'attendance': attendance,
        'classes_conducted': classes_conducted,
        'classes_attended': classes_attended,
        'attendance_rate': attendance_rate,
        'today': timezone.localdate()
    }
    return render(request, 'coaching/student_detail.html', context)

@login_required
@teacher_required
def collect_fee(request, student_id):
    if request.method == 'POST':
        profile = get_object_or_454(StudentProfile, id=student_id)
        amount = request.POST.get('amount')
        remarks = request.POST.get('remarks', '')
        next_due = request.POST.get('next_due_date')
        
        payment = FeePayment.objects.create(
            student=profile,
            amount_paid=amount,
            collected_by=request.user,
            remarks=remarks
        )
        
        profile.next_due_date = next_due
        profile.save()
        
        messages.success(request, f"Fee payment of ${amount} recorded for {profile.user.get_full_name()}. Next due: {next_due}.")
        return redirect('student_detail', student_id=student_id)
    return redirect('teacher_dashboard')

@login_required
@teacher_required
def add_class_schedule(request):
    if request.method == 'POST':
        batch_id = request.POST.get('batch')
        title = request.POST.get('title')
        date = request.POST.get('date')
        start = request.POST.get('start_time')
        end = request.POST.get('end_time')
        is_holiday = request.POST.get('is_holiday') == 'on'
        
        batch = get_object_or_454(Batch, id=batch_id)
        
        ClassSchedule.objects.create(
            batch=batch,
            title=title,
            date=date,
            start_time=start,
            end_time=end,
            is_holiday=is_holiday
        )
        messages.success(request, "Class schedule added to the calendar.")
    return redirect('dashboard_redirect')

# --- Student Views ---

@login_required
@student_required
def student_dashboard(request):
    profile = get_object_or_454(StudentProfile, user=request.user)
    attendance = AttendanceRecord.objects.filter(student=profile)
    
    # Calculate Attendance Rate
    classes_conducted = ClassSchedule.objects.filter(
        batch=profile.batch,
        date__gte=profile.joining_date,
        date__lte=timezone.localdate(),
        is_holiday=False
    ).count()
    
    classes_attended = attendance.filter(status='present').count()
    attendance_rate = int((classes_attended / classes_conducted * 100)) if classes_conducted > 0 else 100
    
    context = {
        'profile': profile,
        'attendance': attendance,
        'classes_conducted': classes_conducted,
        'classes_attended': classes_attended,
        'attendance_rate': attendance_rate,
    }
    return render(request, 'coaching/student_dashboard.html', context)

# --- Smart Scanners Views (Webcam HTML5 QR & Face) ---

@login_required
@role_required('teacher', 'student')
def scanner_attendance(request):
    # Both teachers and students can open the Attendance scanner
    return render(request, 'coaching/scanner_attendance.html')

@login_required
@teacher_required
def scanner_fees(request):
    # Only teachers can scan for fee collection
    return render(request, 'coaching/scanner_fees.html')

# --- AJAX APIs ---

@csrf_exempt
@login_required
def mark_attendance_api(request):
    """
    API endpoint to record attendance via QR scan.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            qr_token = data.get('qr_token')
            marked_by_type = data.get('marked_by', 'teacher')
            
            profile = StudentProfile.objects.filter(qr_code_token=qr_token).first()
            if not profile:
                return JsonResponse({'success': False, 'message': 'Invalid QR Code. Student not found.'})
            
            today = timezone.localdate()
            
            # Check if already marked for today
            exists = AttendanceRecord.objects.filter(student=profile, date=today).exists()
            if exists:
                return JsonResponse({
                    'success': False, 
                    'message': f'{profile.user.get_full_name()} is already marked present for today.',
                    'student_name': profile.user.get_full_name(),
                    'batch': profile.batch.name if profile.batch else 'None'
                })
                
            # Create Attendance
            record = AttendanceRecord.objects.create(
                student=profile,
                date=today,
                status='present',
                marked_by=marked_by_type
            )
            
            return JsonResponse({
                'success': True,
                'message': 'Attendance marked successfully!',
                'student_name': profile.user.get_full_name(),
                'batch': profile.batch.name if profile.batch else 'None',
                'time': record.time_in.strftime('%I:%M %P')
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
            
    return JsonResponse({'success': False, 'message': 'Invalid HTTP Method.'})

@csrf_exempt
@login_required
def verify_face_api(request):
    """
    API endpoint that verifies a student's face profile.
    If the student does not have face data stored, saves the image.
    If they do, performs simulated facial match and marks attendance.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image') # Base64 Image string
            username = data.get('username')
            
            # Use request.user if username not provided
            target_user = request.user
            if username and request.user.role == 'teacher':
                target_user = User.objects.filter(username=username).first()
                
            if not target_user:
                return JsonResponse({'success': False, 'message': 'Student account not found.'})
                
            profile = StudentProfile.objects.filter(user=target_user).first()
            if not profile:
                return JsonResponse({'success': False, 'message': 'Student profile not found.'})
                
            today = timezone.localdate()
            
            # Check if face is registered
            is_registration = False
            if not profile.face_data:
                profile.face_data = image_data
                profile.save()
                is_registration = True
            
            # Check if already checked in today
            exists = AttendanceRecord.objects.filter(student=profile, date=today).exists()
            if exists:
                return JsonResponse({
                    'success': True,
                    'is_registration': is_registration,
                    'message': f'Face verified! {profile.user.get_full_name()} is already marked present for today.'
                })
                
            # Create Attendance
            record = AttendanceRecord.objects.create(
                student=profile,
                date=today,
                status='present',
                marked_by='self_face'
            )
            
            return JsonResponse({
                'success': True,
                'is_registration': is_registration,
                'message': 'Face verification successful! Attendance marked.',
                'student_name': profile.user.get_full_name(),
                'time': record.time_in.strftime('%I:%M %P')
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
            
    return JsonResponse({'success': False, 'message': 'Invalid HTTP Method.'})

@login_required
@teacher_required
def get_student_by_qr(request, qr_token):
    """
    Find student by QR code and return details for AJAX fee collection.
    """
    profile = StudentProfile.objects.filter(qr_code_token=qr_token, user__is_active=True).first()
    if profile:
        return JsonResponse({
            'success': True,
            'id': profile.id,
            'name': profile.user.get_full_name(),
            'batch': profile.batch.name if profile.batch else 'None',
            'monthly_fee': str(profile.monthly_fee),
            'next_due_date': profile.next_due_date.strftime('%Y-%m-%d'),
            'recommended_due_date': (profile.next_due_date + datetime.timedelta(days=30)).strftime('%Y-%m-%d')
        })
    return JsonResponse({'success': False, 'message': 'Student not found or inactive.'})
