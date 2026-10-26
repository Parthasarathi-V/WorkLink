from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def _role(attr):
    def deco(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if getattr(request.user, attr, None) is None:
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return login_required(wrapper)
    return deco


worker_required = _role("workerprofile")
business_required = _role("businessprofile")


def staff_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return login_required(wrapper)
