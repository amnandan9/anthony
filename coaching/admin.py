from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from coaching.models import User, Batch, StudentProfile, AttendanceRecord, FeePayment, ClassSchedule

# Extend default UserAdmin to support role field editing
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_active')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    fieldsets = UserAdmin.fieldsets + (
        ('Role Parameters', {'fields': ('role',)}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Role Parameters', {'fields': ('role',)}),
    )

@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('name', 'timing', 'created_at')
    search_fields = ('name', 'description')

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user_fullname', 'user', 'batch', 'monthly_fee', 'next_due_date', 'school_college')
    list_filter = ('batch', 'next_due_date')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'school_college')

    def user_fullname(self, obj):
        return obj.user.get_full_name()
    user_fullname.short_description = 'Student Full Name'

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'time_in', 'status', 'marked_by')
    list_filter = ('date', 'status', 'marked_by')
    search_fields = ('student__user__username', 'student__user__first_name', 'student__user__last_name')

@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ('student', 'amount_paid', 'payment_date', 'collected_by')
    list_filter = ('payment_date', 'collected_by')
    search_fields = ('student__user__username', 'student__user__first_name', 'collected_by__username')

@admin.register(ClassSchedule)
class ClassScheduleAdmin(admin.ModelAdmin):
    list_display = ('batch', 'title', 'date', 'start_time', 'end_time', 'is_holiday')
    list_filter = ('date', 'is_holiday', 'batch')
    search_fields = ('title', 'batch__name')
