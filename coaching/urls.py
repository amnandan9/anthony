from django.urls import path
from coaching import views

urlpatterns = [
    # Authentication URLs
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Dashboard Redirect Router
    path('dashboard/', views.dashboard_redirect, name='dashboard_redirect'),
    
    # Specific Dashboards
    path('dashboard/admin/', views.super_admin_dashboard, name='super_admin_dashboard'),
    path('dashboard/teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),
    
    # Super Admin Actions
    path('teacher/manage/', views.manage_teacher, name='manage_teacher'),
    path('teacher/manage/<int:teacher_id>/', views.manage_teacher, name='toggle_teacher'),
    
    # Teacher Actions
    path('student/register/', views.register_student, name='register_student'),
    path('student/edit/<int:student_id>/', views.edit_student, name='edit_student'),
    path('student/<int:student_id>/', views.student_detail, name='student_detail'),
    path('student/collect-fee/<int:student_id>/', views.collect_fee, name='collect_fee'),
    path('schedule/add/', views.add_class_schedule, name='add_class_schedule'),
    
    # Scanning Views
    path('scanner/attendance/', views.scanner_attendance, name='scanner_attendance'),
    path('scanner/fees/', views.scanner_fees, name='scanner_fees'),
    
    # QR Print Sheet
    path('print/qr/', views.print_qr_sheet, name='print_qr_sheet'),
    path('print/qr/<str:batch_id>/', views.print_qr_sheet, name='print_qr_sheet_batch_old'),
    path('print/qr/batch/<str:batch_id>/', views.print_qr_sheet, name='print_qr_sheet_batch'),
    path('print/qr/student/<str:username>/', views.print_qr_sheet, name='print_qr_sheet_student'),
    
    # Export
    path('export/attendance/', views.export_attendance_csv, name='export_attendance_csv'),

    # AJAX API Endpoints
    path('api/mark-attendance/', views.mark_attendance_api, name='mark_attendance_api'),
    path('api/verify-face/', views.verify_face_api, name='verify_face_api'),
    path('api/get-student-qr/<str:qr_token>/', views.get_student_by_qr, name='get_student_by_qr'),
    path('api/update-profile-photo/', views.update_profile_photo_api, name='update_profile_photo_api'),
]
