from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def get_role(user):
    if not user.is_authenticated:
        return None
    if user.is_staff:
        return "admin"
    if hasattr(user, "workerprofile"):
        return "worker"
    if hasattr(user, "businessprofile"):
        return "business"
    return None


def role_required(role):
    """Authentication + role check. Object-ownership is checked inside each view."""
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if get_role(request.user) != role:
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


worker_required = role_required("worker")
business_required = role_required("business")
