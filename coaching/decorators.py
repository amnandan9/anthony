from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import redirect_to_login

def role_required(*roles):
    """
    Decorator for views that checks whether the user has one of the specified roles,
    redirecting to the log-in page if necessary, or raising PermissionDenied.
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if request.user.role in roles or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped_view
    return decorator

def super_admin_required(view_func):
    return role_required('super_admin')(view_func)

def teacher_required(view_func):
    return role_required('teacher', 'super_admin')(view_func)

def student_required(view_func):
    return role_required('student')(view_func)
