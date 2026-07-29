import json
import datetime
import base64
import csv
import numpy as np
from io import BytesIO
from PIL import Image, ImageOps
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from coaching.models import User, Batch, StudentProfile, AttendanceRecord, FeePayment, ClassSchedule, DailyBatchAttendanceLock
from coaching.decorators import super_admin_required, teacher_required, student_required, role_required



# --- Authentication Views ---

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard_redirect')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Auto-create general scanner account if matching scanner/scanner123 credentials and doesn't exist
        if username == 'scanner' and password == 'scanner123':
            if not User.objects.filter(username='scanner').exists():
                User.objects.create_user(
                    username='scanner',
                    password='scanner123',
                    role='student',
                    first_name='General',
                    last_name='Scanner Terminal'
                )
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, "This account is inactive. Please contact the administrator.")
                return render(request, 'coaching/login.html')
            
            # Block regular student logins
            if user.role == 'student' and user.username != 'scanner':
                messages.error(request, "Student accounts are not allowed to log in directly. Please use the shared scanner terminal to check in.")
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
        if request.user.username == 'scanner':
            return redirect('scanner_attendance')
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

    batches = list(Batch.objects.all())
    todays_locks = {lock.batch_id: lock.is_locked for lock in DailyBatchAttendanceLock.objects.filter(date=today)}
    for b in batches:
        b.is_locked_today = todays_locks.get(b.id, False)

    context = {
        'teachers': teachers,
        'total_teachers': total_teachers,
        'total_students': total_students,
        'monthly_revenue': monthly_revenue,
        'overall_attendance': overall_attendance,
        'batches': batches,
        'today': today,
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
            teacher = get_object_or_404(User, id=teacher_id, role='teacher')
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
    
    # Pending Dues count and list (active students who haven't paid this month)
    paid_student_ids = set(
        FeePayment.objects.filter(
            payment_date__gte=first_of_month,
            payment_date__lte=today
        ).values_list('student_id', flat=True)
    )
    overdue_students = StudentProfile.objects.filter(user__is_active=True).exclude(id__in=paid_student_ids)
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
        students = students.exclude(id__in=paid_student_ids)
    elif due_filter == 'cleared':
        students = students.filter(id__in=paid_student_ids)

    todays_att_map = {rec.student_id: rec for rec in AttendanceRecord.objects.filter(date=today)}
    todays_locks = {lock.batch_id: lock.is_locked for lock in DailyBatchAttendanceLock.objects.filter(date=today)}

    # Attach is_paid_this_month, today_record, and is_batch_locked_today helpers
    for student in students:
        student.is_paid_this_month = student.id in paid_student_ids
        student.today_record = todays_att_map.get(student.id)
        student.is_batch_locked_today = todays_locks.get(student.batch_id, False) if student.batch_id else False

    # 3. Calendar classes & events
    classes_this_month = ClassSchedule.objects.filter(date__year=today.year, date__month=today.month)
    
    batches = list(Batch.objects.all())
    for b in batches:
        b.is_locked_today = todays_locks.get(b.id, False)

    # Fetch distinct attendance dates
    attendance_dates = list(AttendanceRecord.objects.values_list('date', flat=True).distinct())
    attendance_dates_json = json.dumps([d.strftime('%Y-%m-%d') for d in attendance_dates])

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
        'attendance_dates_json': attendance_dates_json,
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
        
        class_std = request.POST.get('class_std')
        school = request.POST.get('school_college')
        contact = request.POST.get('contact_number')
        parent_contact = request.POST.get('parent_contact')
        joining_date = request.POST.get('joining_date') or timezone.localdate()
        batch_id = request.POST.get('batch')
        fee = request.POST.get('monthly_fee')
        next_due = request.POST.get('next_due_date')
        face_data = request.POST.get('face_data')
        
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
            class_std=class_std,
            school_college=school,
            contact_number=contact,
            parent_contact=parent_contact,
            joining_date=joining_date,
            batch=batch,
            monthly_fee=fee,
            next_due_date=next_due,
            face_data=face_data
        )
        
        messages.success(request, f"Student {user.get_full_name()} registered successfully!")
        return redirect('teacher_dashboard')
        
    return render(request, 'coaching/register_student.html', {'batches': batches, 'today': timezone.localdate()})

@login_required
@teacher_required
def edit_student(request, student_id):
    profile = get_object_or_404(StudentProfile, id=student_id)
    batches = Batch.objects.all()
    
    if request.method == 'POST':
        user = profile.user
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.save()
        
        profile.class_std = request.POST.get('class_std')
        profile.school_college = request.POST.get('school_college')
        profile.contact_number = request.POST.get('contact_number')
        profile.parent_contact = request.POST.get('parent_contact')
        profile.joining_date = request.POST.get('joining_date')
        profile.monthly_fee = request.POST.get('monthly_fee')
        profile.next_due_date = request.POST.get('next_due_date')
        
        face_data = request.POST.get('face_data')
        if face_data:
            profile.face_data = face_data
            
        batch_id = request.POST.get('batch')
        profile.batch = Batch.objects.filter(id=batch_id).first() if batch_id else None
        profile.save()
        
        messages.success(request, f"Student {user.get_full_name()} updated successfully.")
        return redirect('student_detail', student_id=student_id)
        
    return render(request, 'coaching/edit_student.html', {'profile': profile, 'batches': batches})

@login_required
@teacher_required
def student_detail(request, student_id):
    profile = get_object_or_404(StudentProfile, id=student_id)
    payments = FeePayment.objects.filter(student=profile)
    attendance = AttendanceRecord.objects.filter(student=profile)
    
    # Statistics calculations
    classes_conducted = ClassSchedule.objects.filter(
        batch=profile.batch,
        date__gte=profile.joining_date,
        date__lte=timezone.localdate(),
        is_holiday=False
    ).count()
    
    classes_attended = attendance.filter(status='present').count()
    attendance_rate = int((classes_attended / classes_conducted * 100)) if classes_conducted > 0 else 100
    
    # 12-Month Payment History calculation
    payment_history = []
    today = timezone.localdate()
    current_year = today.year
    current_month = today.month
    
    for i in range(12):
        m = current_month - i
        y = current_year
        while m <= 0:
            m += 12
            y -= 1
            
        first_of_month = datetime.date(y, m, 1)
        month_label = first_of_month.strftime('%b %Y') # e.g. Jul 2026
        
        enroll_month_first = profile.joining_date.replace(day=1)
        if first_of_month < enroll_month_first:
            continue  # Prior to enrollment month
            
        next_m = m + 1
        next_y = y
        if next_m > 12:
            next_m = 1
            next_y += 1
        next_month_first = datetime.date(next_y, next_m, 1)
        
        pmt = FeePayment.objects.filter(
            student=profile,
            payment_date__gte=first_of_month,
            payment_date__lt=next_month_first
        ).first()
        
        if pmt:
            payment_history.append({
                'month_name': month_label,
                'status': 'Paid',
                'amount': pmt.amount_paid,
                'date': pmt.payment_date,
                'is_paid': True
            })
        else:
            payment_history.append({
                'month_name': month_label,
                'status': 'Not Paid',
                'amount': 0.00,
                'date': None,
                'is_paid': False
            })
            
    context = {
        'profile': profile,
        'payments': payments,
        'payment_history': payment_history,
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
        profile = get_object_or_404(StudentProfile, id=student_id)
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
        
        messages.success(request, f"Fee payment of ₹{amount} recorded for {profile.user.get_full_name()}. Next due: {next_due}.")
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
        
        batch = get_object_or_404(Batch, id=batch_id)
        
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
    from django.http import Http404
    raise Http404("Student portal has been disabled.")

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
    API endpoint to record attendance via QR scan, with lock check and batch time late calculation.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            qr_token = data.get('qr_token')
            marked_by_type = data.get('marked_by', 'teacher')
            
            profile = StudentProfile.objects.filter(
                Q(qr_code_token=qr_token) | Q(user__username=qr_token), 
                user__is_active=True
            ).first()
            if not profile:
                return JsonResponse({'success': False, 'message': 'Invalid Card Token/QR. Student not found.'})
            
            today = timezone.localdate()
            
            # Check Daily Attendance Submission Lock
            if profile.batch:
                lock = DailyBatchAttendanceLock.objects.filter(batch=profile.batch, date=today).first()
                if lock and lock.is_locked:
                    return JsonResponse({
                        'success': False,
                        'is_locked': True,
                        'message': f'Attendance for batch "{profile.batch.name}" has been submitted and locked for today ({today.strftime("%d-%m-%Y")}). No further attendance allowed.',
                        'student_name': profile.user.get_full_name(),
                        'batch': profile.batch.name
                    })
            
            # Calculate current month fee status
            first_of_month = today.replace(day=1)
            has_paid = FeePayment.objects.filter(
                student=profile,
                payment_date__gte=first_of_month,
                payment_date__lte=today
            ).exists()
            fee_status_str = "Paid" if has_paid else "Not Paid"
            
            # Calculate streak (attendance count this month)
            streak = AttendanceRecord.objects.filter(
                student=profile,
                date__gte=first_of_month,
                date__lte=today,
                status__in=['present', 'late']
            ).count()
            
            # Calculate check-in time and status relative to batch start time
            batch_start_time = datetime.time(9, 0)
            if profile.batch:
                schedule = ClassSchedule.objects.filter(batch=profile.batch, date=today, is_holiday=False).first()
                if schedule:
                    batch_start_time = schedule.start_time
                else:
                    batch_start_time = profile.batch.get_effective_start_time()

            now_local = timezone.localtime()
            current_time = now_local.time()
            now_dt = datetime.datetime.combine(today, current_time)
            start_dt = datetime.datetime.combine(today, batch_start_time)
            diff_minutes = int((now_dt - start_dt).total_seconds() / 60)

            if diff_minutes > 20:
                determined_status = 'late'
                minutes_late = diff_minutes
            else:
                determined_status = 'present'
                minutes_late = max(0, diff_minutes)

            if minutes_late <= 0:
                timing_summary = "On time"
            elif determined_status == 'late':
                timing_summary = f"{minutes_late} mins late (Late)"
            else:
                timing_summary = f"{minutes_late} mins late (Present)"
            
            effective_note = ""
            if profile.individual_note and profile.individual_note.strip():
                effective_note = profile.individual_note.strip()
            elif profile.batch and profile.batch.daily_note and profile.batch.daily_note.strip():
                effective_note = profile.batch.daily_note.strip()

            # Check if already marked for today
            existing_record = AttendanceRecord.objects.filter(student=profile, date=today).first()
            if existing_record:
                batch = profile.batch
                batch_attendance_percentage = 0
                if batch:
                    total_students = StudentProfile.objects.filter(batch=batch, user__is_active=True).count()
                    if total_students > 0:
                        present_today = AttendanceRecord.objects.filter(
                            student__batch=batch,
                            date=today,
                            status__in=['present', 'late']
                        ).count()
                        batch_attendance_percentage = int((present_today / total_students) * 100)
                        
                return JsonResponse({
                    'success': False, 
                    'already_marked': True,
                    'message': f'{profile.user.get_full_name()} is already marked {existing_record.get_status_display().lower()} for today ({existing_record.minutes_late} mins late).',
                    'student_name': profile.user.get_full_name(),
                    'batch': profile.batch.name if profile.batch else 'None',
                    'daily_note': effective_note,
                    'school': profile.school_college,
                    'fee_status': fee_status_str,
                    'status': existing_record.status,
                    'minutes_late': existing_record.minutes_late,
                    'timing_summary': f"{existing_record.minutes_late} mins late" if existing_record.minutes_late > 0 else "On time",
                    'time': existing_record.time_in.strftime('%I:%M %p'),
                    'batch_attendance_percentage': batch_attendance_percentage,
                    'next_due': profile.next_due_date.strftime('%d-%m-%Y')
                })
                
            # Create Attendance Record
            record = AttendanceRecord.objects.create(
                student=profile,
                date=today,
                status=determined_status,
                minutes_late=minutes_late,
                marked_by=marked_by_type
            )
            
            # Calculate running batch attendance percentage
            batch = profile.batch
            batch_attendance_percentage = 0
            if batch:
                total_students = StudentProfile.objects.filter(batch=batch, user__is_active=True).count()
                if total_students > 0:
                    present_today = AttendanceRecord.objects.filter(
                        student__batch=batch,
                        date=today,
                        status__in=['present', 'late']
                    ).count()
                    batch_attendance_percentage = int((present_today / total_students) * 100)
            
            return JsonResponse({
                'success': True,
                'message': 'Attendance marked successfully!',
                'student_name': profile.user.get_full_name(),
                'batch': profile.batch.name if profile.batch else 'None',
                'daily_note': effective_note,
                'time': record.time_in.strftime('%I:%M %p'),
                'school': profile.school_college,
                'fee_status': fee_status_str,
                'status': record.status,
                'minutes_late': record.minutes_late,
                'timing_summary': timing_summary,
                'batch_attendance_percentage': batch_attendance_percentage,
                'next_due': profile.next_due_date.strftime('%d-%m-%Y')
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
            
    return JsonResponse({'success': False, 'message': 'Invalid HTTP Method.'})

@csrf_exempt
@login_required
@role_required('teacher', 'super_admin')
def toggle_attendance_lock_api(request):
    """
    API endpoint for Teachers and Admins to submit/lock or unlock attendance for a batch on a date.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            batch_id = data.get('batch_id')
            date_str = data.get('date')
            lock_state = data.get('is_locked', True)

            if not batch_id:
                return JsonResponse({'success': False, 'message': 'Batch ID is required.'})

            batch = get_object_or_404(Batch, id=batch_id)
            lock_date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else timezone.localdate()

            lock_obj, created = DailyBatchAttendanceLock.objects.get_or_create(
                batch=batch,
                date=lock_date,
                defaults={'is_locked': lock_state, 'locked_by': request.user}
            )
            if not created:
                lock_obj.is_locked = lock_state
                lock_obj.locked_by = request.user
                lock_obj.save()

            status_str = "submitted and locked" if lock_obj.is_locked else "unlocked for editing"
            return JsonResponse({
                'success': True,
                'is_locked': lock_obj.is_locked,
                'batch_id': batch.id,
                'batch_name': batch.name,
                'date': lock_date.strftime('%Y-%m-%d'),
                'message': f'Attendance for batch "{batch.name}" on {lock_date.strftime("%d-%m-%Y")} is now {status_str}.'
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    return JsonResponse({'success': False, 'message': 'Invalid HTTP Method.'})

@csrf_exempt
@login_required
@role_required('teacher', 'super_admin')
def toggle_student_attendance_api(request):
    """
    API endpoint for Teachers and Admins to toggle attendance status ('present' or 'absent') for an individual student.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid HTTP Method.'}, status=405)

    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        target_action = data.get('action') # 'present', 'absent', or 'toggle'
        today = timezone.localdate()

        student = get_object_or_404(StudentProfile, id=student_id)

        # Check Daily Batch Lock
        if student.batch:
            lock = DailyBatchAttendanceLock.objects.filter(batch=student.batch, date=today).first()
            if lock and lock.is_locked:
                return JsonResponse({
                    'success': False,
                    'is_locked': True,
                    'message': f'Attendance for batch "{student.batch.name}" is submitted and locked for today. Unlock the batch to modify.'
                })

        record = AttendanceRecord.objects.filter(student=student, date=today).first()

        if target_action == 'absent':
            if record:
                record.delete()
            return JsonResponse({
                'success': True,
                'status': 'absent',
                'minutes_late': 0,
                'message': f'Marked {student.user.get_full_name()} as Absent.'
            })
        else: # 'present' or toggle
            if target_action == 'toggle' and record and record.status in ['present', 'late']:
                record.delete()
                return JsonResponse({
                    'success': True,
                    'status': 'absent',
                    'minutes_late': 0,
                    'message': f'Marked {student.user.get_full_name()} as Absent.'
                })

            batch_start_time = datetime.time(9, 0)
            if student.batch:
                schedule = ClassSchedule.objects.filter(batch=student.batch, date=today, is_holiday=False).first()
                if schedule:
                    batch_start_time = schedule.start_time
                else:
                    batch_start_time = student.batch.get_effective_start_time()

            now_local = timezone.localtime()
            current_time = now_local.time()
            now_dt = datetime.datetime.combine(today, current_time)
            start_dt = datetime.datetime.combine(today, batch_start_time)
            diff_minutes = int((now_dt - start_dt).total_seconds() / 60)

            if diff_minutes > 20:
                determined_status = 'late'
                minutes_late = diff_minutes
            else:
                determined_status = 'present'
                minutes_late = max(0, diff_minutes)

            if record:
                record.status = determined_status
                record.minutes_late = minutes_late
                record.marked_by = 'teacher'
                record.save()
            else:
                record = AttendanceRecord.objects.create(
                    student=student,
                    date=today,
                    status=determined_status,
                    minutes_late=minutes_late,
                    marked_by='teacher'
                )

            timing_str = "On time" if minutes_late == 0 else f"{minutes_late}m late"
            return JsonResponse({
                'success': True,
                'status': record.status,
                'minutes_late': record.minutes_late,
                'timing_str': timing_str,
                'message': f'Marked {student.user.get_full_name()} as {record.get_status_display()} ({timing_str}).'
            })

    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
@teacher_required
def get_student_by_qr(request, qr_token):
    """
    Find student by QR code token or unique username, and return details for AJAX fee collection.
    """
    profile = StudentProfile.objects.filter(
        Q(qr_code_token=qr_token) | Q(user__username=qr_token), 
        user__is_active=True
    ).first()
    
    if profile:
        return JsonResponse({
            'success': True,
            'id': profile.id,
            'name': profile.user.get_full_name(),
            'batch': profile.batch.name if profile.batch else 'None',
            'monthly_fee': str(profile.monthly_fee),
            'next_due_date': profile.next_due_date.strftime('%Y-%m-%d'),
            'recommended_due_date': (profile.next_due_date + datetime.timedelta(days=30)).strftime('%Y-%m-%d'),
        })
    return JsonResponse({'success': False, 'message': 'Student not found or inactive.'})

@login_required
@role_required('teacher', 'super_admin')
def print_qr_sheet(request, batch_id=None, username=None):
    if batch_id:
        batch = get_object_or_404(Batch, id=batch_id)
        students = StudentProfile.objects.filter(batch=batch, user__is_active=True).order_by('user__first_name')
        title = f"QR Cards - {batch.name}"
    elif username:
        student = get_object_or_404(StudentProfile, user__username=username, user__is_active=True)
        students = [student]
        title = f"QR Card - {student.user.get_full_name()}"
    else:
        students = StudentProfile.objects.filter(user__is_active=True).order_by('batch__name', 'user__first_name')
        title = "All Student QR Cards"
    
    return render(request, 'coaching/print_qr.html', {
        'students': students,
        'title': title
    })

@login_required
@role_required('teacher', 'super_admin')
def export_attendance_csv(request):
    batch_id = request.GET.get('batch')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    records = AttendanceRecord.objects.all()
    
    if batch_id:
        records = records.filter(student__batch_id=batch_id)
    if start_date_str:
        records = records.filter(date__gte=start_date_str)
    if end_date_str:
        records = records.filter(date__lte=end_date_str)
        
    records = records.select_related('student__user', 'student__batch').order_by('-date', 'student__user__first_name')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="attendance_export_{timezone.localdate().strftime("%Y-%m-%d")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Student ID (Username)', 'Student Name', 'Batch', 'Check-In Time', 'Status', 'Minutes Late', 'Marked By'])
    
    for r in records:
        writer.writerow([
            r.date.strftime('%Y-%m-%d'),
            r.student.user.username,
            r.student.user.get_full_name(),
            r.student.batch.name if r.student.batch else 'None',
            r.time_in.strftime('%I:%M %p') if r.time_in else '-',
            r.get_status_display(),
            r.minutes_late,
            r.get_marked_by_display()
        ])
        
    return response

@csrf_exempt
def public_student_info(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            qr_token = data.get('qr_token')
            if not qr_token:
                return JsonResponse({'success': False, 'message': 'No QR code token provided.'})
            
            profile = StudentProfile.objects.filter(
                Q(qr_code_token=qr_token) | Q(user__username=qr_token), 
                user__is_active=True
            ).first()
            
            if not profile:
                return JsonResponse({'success': False, 'message': 'Student profile not found.'})
            
            # Save device IP tracking
            x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded:
                client_ip = x_forwarded.split(',')[0].strip()
            else:
                client_ip = request.META.get('REMOTE_ADDR')
            
            profile.last_scanned_ip = client_ip
            profile.last_scanned_at = timezone.now()
            profile.save(update_fields=['last_scanned_ip', 'last_scanned_at'])

            # Determine fee payment status & notifications
            today = timezone.localdate()
            has_paid = FeePayment.objects.filter(
                student=profile,
                payment_date__gte=today.replace(day=1),
                payment_date__lte=today
            ).exists()
            fee_status_str = "Paid" if has_paid else "Not Paid"

            fee_reminder_msg = ""
            if not has_paid:
                if profile.next_due_date < today:
                    fee_reminder_msg = f"⚠️ FEE REMINDER: Payment is OVERDUE since {profile.next_due_date.strftime('%d-%m-%Y')}. Please submit your fee."
                else:
                    days_left = (profile.next_due_date - today).days
                    if days_left <= 7:
                        fee_reminder_msg = f"🔔 FEE REMINDER: Next fee due date is {profile.next_due_date.strftime('%d-%m-%Y')} ({days_left} days remaining)."

            effective_note = ""
            if profile.individual_note and profile.individual_note.strip():
                effective_note = profile.individual_note.strip()
            elif profile.batch and profile.batch.daily_note and profile.batch.daily_note.strip():
                effective_note = profile.batch.daily_note.strip()

            face_data = profile.face_data or profile.user.face_data or ""

            return JsonResponse({
                'success': True,
                'student_name': profile.user.get_full_name(),
                'username': profile.user.username,
                'batch': profile.batch.name if profile.batch else 'None',
                'daily_note': effective_note,
                'school': profile.school_college,
                'class_std': profile.class_std or 'N/A',
                'face_data': face_data,
                'fee_status': fee_status_str,
                'fee_reminder_msg': fee_reminder_msg,
                'next_due': profile.next_due_date.strftime('%d-%m-%Y'),
                'scanned_ip': client_ip,
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

@csrf_exempt
@login_required
def update_profile_photo_api(request):
    """
    API endpoint for logged-in users (teachers, admins) to update their profile photo from gallery.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image')
            if not image_data:
                return JsonResponse({'success': False, 'message': 'No image data provided.'}, status=400)
                
            request.user.face_data = image_data
            request.user.save()
            return JsonResponse({'success': True, 'message': 'Profile photo updated successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False, 'message': 'Invalid HTTP Method.'}, status=405)

@csrf_exempt
@login_required
@role_required('teacher', 'super_admin')
def save_batch_note_api(request):
    """
    API endpoint for teachers and admins to save a daily assignment note/teacher tip for a batch.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            batch_id = data.get('batch_id')
            daily_note = data.get('daily_note', '')
            
            batch = get_object_or_404(Batch, id=batch_id)
            batch.daily_note = daily_note
            batch.save()
            
            return JsonResponse({'success': True, 'message': f'Assignment note for "{batch.name}" saved successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False, 'message': 'Invalid HTTP Method.'}, status=405)

@csrf_exempt
@login_required
@role_required('teacher', 'super_admin')
def save_student_note_api(request):
    """
    API endpoint for teachers and admins to save an individual homework/task note for a student.
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            student_id = data.get('student_id')
            individual_note = data.get('individual_note', '')
            
            profile = get_object_or_404(StudentProfile, id=student_id)
            profile.individual_note = individual_note
            profile.save()
            
            return JsonResponse({'success': True, 'message': f'Individual task for {profile.user.get_full_name()} saved successfully!'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=400)
    return JsonResponse({'success': False, 'message': 'Invalid HTTP Method.'}, status=405)
            
    return JsonResponse({'success': False, 'message': 'Invalid HTTP Method.'})

