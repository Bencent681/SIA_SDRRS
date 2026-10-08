from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

REGISTRAR_GROUP_NAME = 'Registrar'


def is_registrar(user):
    """True for users allowed to manage all document requests."""
    if not user or not user.is_authenticated:
        return False
    return bool(
        user.is_staff
        or user.is_superuser
        or user.groups.filter(name=REGISTRAR_GROUP_NAME).exists()
    )


def registrar_required(view_func):
    """Allow only registrar staff / administrators to access a view."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not is_registrar(request.user):
            messages.error(
                request,
                'You do not have permission to access that page.',
            )
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)

    return _wrapped
