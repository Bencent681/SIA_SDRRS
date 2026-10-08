from .roles import is_registrar


def sdrrs_context(request):
    user = getattr(request, 'user', None)
    registrar = is_registrar(user)
    return {
        'is_registrar': registrar,
        'is_student': bool(user and user.is_authenticated and not registrar),
    }
