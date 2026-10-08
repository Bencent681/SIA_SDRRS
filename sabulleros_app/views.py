from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import DocumentRequestForm, DocumentRequestManageForm, StudentSignUpForm
from .models import DocumentRequest
from .roles import is_registrar, registrar_required

STATUS_PENDING = DocumentRequest.Status.PENDING
STATUS_READY = DocumentRequest.Status.READY
STATUS_RELEASED = DocumentRequest.Status.RELEASED
STATUS_CHOICES = {c[0] for c in DocumentRequest.Status.choices}
DOCUMENT_TYPE_CHOICES = {c[0] for c in DocumentRequest.DocumentType.choices}


def signup(request):
    """Register a student account and sign the new student in."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        form = StudentSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Your student account is ready. Welcome to SDRRS!')
            return redirect('dashboard')
    else:
        form = StudentSignUpForm()

    return render(request, 'registration/signup.html', {'form': form})


def _apply_search(queryset, query):
    """Filter by Request ID, Student ID or Student Name."""
    query = query.strip()
    if not query:
        return queryset

    if query.upper().startswith('REQ-') and query[4:].isdigit():
        return queryset.filter(request_id=int(query[4:]))

    condition = Q(student_id__icontains=query) | Q(student_name__icontains=query)
    if query.isdigit():
        condition |= Q(request_id=int(query))
    return queryset.filter(condition)


def _counts(queryset):
    return {
        'total_requests': queryset.count(),
        'pending_count': queryset.filter(status=STATUS_PENDING).count(),
        'ready_count': queryset.filter(status=STATUS_READY).count(),
        'released_count': queryset.filter(status=STATUS_RELEASED).count(),
    }


@login_required
def dashboard(request):
    """Dashboard summary built from live database queries."""
    registrar = is_registrar(request.user)

    if registrar:
        queryset = DocumentRequest.objects.all()
        context = {
            'scope_label': 'All Requests',
            'attention_requests': queryset.filter(
                status__in=[STATUS_PENDING, STATUS_READY]
            )[:8],
        }
    else:
        queryset = DocumentRequest.objects.filter(student_account=request.user)
        context = {
            'scope_label': 'My Requests',
            'attention_requests': queryset.filter(status=STATUS_PENDING)[:8],
            'released_requests': queryset.filter(
                status=STATUS_RELEASED,
                release_date__isnull=False,
            ).order_by('-release_date')[:5],
        }

    context.update(_counts(queryset))
    context['recent_requests'] = queryset[:8]
    return render(request, 'sdrrs/dashboard.html', context)


@login_required
def request_list(request):
    """Students see their own requests; registrar/admin see everything."""
    registrar = is_registrar(request.user)

    if registrar:
        queryset = DocumentRequest.objects.all()
    else:
        queryset = DocumentRequest.objects.filter(student_account=request.user)

    # Search + filters (registrar/admin only)
    status = request.GET.get('status', '').strip()
    document_type = request.GET.get('document_type', '').strip()
    student_id = request.GET.get('student_id', '').strip()
    query = request.GET.get('q', '').strip()

    if registrar:
        if query:
            queryset = _apply_search(queryset, query)
        if student_id:
            queryset = queryset.filter(student_id__icontains=student_id)
        if document_type in DOCUMENT_TYPE_CHOICES:
            queryset = queryset.filter(document_type=document_type)
        elif document_type:
            document_type = ''

    base = queryset  # search + type/ID filters applied, no status filter yet
    if registrar and status in STATUS_CHOICES:
        results = base.filter(status=status)
    else:
        status = ''
        results = base

    tab_counts = {
        'all_count': base.count(),
        'pending_count': base.filter(status=STATUS_PENDING).count(),
        'ready_count': base.filter(status=STATUS_READY).count(),
        'released_count': base.filter(status=STATUS_RELEASED).count(),
    }

    context = {
        'requests': results,
        'registrar': registrar,
        'status_filter': status,
        'document_type_filter': document_type,
        'student_id_filter': student_id,
        'query': query,
        'status_choices': DocumentRequest.Status.choices,
        'document_type_choices': DocumentRequest.DocumentType.choices,
    }
    context.update(tab_counts)
    return render(request, 'sdrrs/request_list.html', context)


@login_required
def request_create(request):
    """Submit a new document request (always starts as Pending)."""
    if request.method == 'POST':
        form = DocumentRequestForm(request.POST, user=request.user)
        if form.is_valid():
            document_request = form.save(commit=False)
            if is_registrar(request.user):
                document_request.student_account = form.cleaned_data['student_account']
            else:
                document_request.student_account = request.user
            document_request.status = STATUS_PENDING
            document_request.release_date = None
            document_request.save()
            messages.success(request, 'Document request submitted successfully.')
            return redirect('request_detail', document_request.pk)
    else:
        form = DocumentRequestForm(user=request.user)

    return render(
        request,
        'sdrrs/request_form.html',
        {'form': form, 'is_edit': False},
    )


@login_required
def request_detail(request, pk):
    """Request details: full record for staff, read-only own record for students."""
    document_request = get_object_or_404(DocumentRequest, pk=pk)

    if not is_registrar(request.user) and document_request.student_account_id != request.user.pk:
        messages.error(request, 'You can only view your own document requests.')
        return redirect('request_list')

    context = {
        'object': document_request,
        'is_edit': True,
    }
    if is_registrar(request.user):
        context['form'] = DocumentRequestManageForm(
            instance=document_request, user=request.user
        )
    return render(request, 'sdrrs/request_detail.html', context)


@login_required
@registrar_required
def request_edit(request, pk):
    """Registrar/admin edit form for a request."""
    document_request = get_object_or_404(DocumentRequest, pk=pk)

    if request.method == 'POST':
        form = DocumentRequestManageForm(
            request.POST, instance=document_request, user=request.user
        )
        if form.is_valid():
            document_request = form.save(commit=False)
            student_account = form.cleaned_data.get('student_account')
            if student_account is not None:
                document_request.student_account = student_account
            document_request.save()
            messages.success(request, 'Request updated successfully.')
            return redirect('request_detail', document_request.pk)
    else:
        form = DocumentRequestManageForm(instance=document_request, user=request.user)

    return render(
        request,
        'sdrrs/request_form.html',
        {'form': form, 'is_edit': True, 'object': document_request},
    )


@login_required
@registrar_required
def request_delete(request, pk):
    """Delete a request; GET shows the confirmation page, POST deletes."""
    document_request = get_object_or_404(DocumentRequest, pk=pk)

    if request.method == 'POST':
        document_request.delete()
        messages.success(request, 'Document request deleted successfully.')
        return redirect('request_list')

    return render(
        request,
        'sdrrs/request_confirm_delete.html',
        {'object': document_request},
    )


@login_required
@registrar_required
@require_POST
def mark_ready(request, pk):
    document_request = get_object_or_404(DocumentRequest, pk=pk)

    if document_request.status == STATUS_PENDING:
        document_request.status = STATUS_READY
        document_request.save(update_fields=['status'])
        messages.success(request, 'Document marked as ready for release.')
    else:
        messages.error(
            request,
            f'Only pending requests can be marked as ready '
            f'(current status: {document_request.status}).',
        )
    return redirect('request_detail', document_request.pk)


@login_required
@registrar_required
@require_POST
def mark_released(request, pk):
    document_request = get_object_or_404(DocumentRequest, pk=pk)

    if document_request.status == STATUS_READY:
        document_request.status = STATUS_RELEASED
        document_request.release_date = timezone.now()
        document_request.save(update_fields=['status', 'release_date'])
        messages.success(request, 'Document released successfully.')
    elif document_request.status == STATUS_PENDING:
        messages.error(
            request,
            'The request must be marked as Ready before it can be released.',
        )
    else:
        messages.error(request, 'This document has already been released.')
    return redirect('request_detail', document_request.pk)
