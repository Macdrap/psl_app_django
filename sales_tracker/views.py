from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
from urllib.parse import urlencode
from .models import SalesEnquiry
from .forms import SalesEnquiryAddForm, SalesEnquiryEditForm
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.template.loader import render_to_string
from django.db.models import Q, Max


@login_required
def sales_tracker(request):
    """Sales tracker list view with pagination"""
    enquiries = SalesEnquiry.objects.all()

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        from django.db.models import Q
        enquiries = enquiries.filter(
            Q(job_number__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(client__icontains=search_query)
        )

    # Sort by filter
    sort_by = request.GET.get('sort_by', 'date')

    if sort_by == 'job_number':
        enquiries = list(enquiries)

        def sort_key(enquiry):
            job_num = enquiry.job_number
            try:
                if '.' in job_num:
                    parts = job_num.split('.')
                    return (0, int(parts[0]), int(parts[1]))
                else:
                    return (0, int(job_num), 0)
            except (ValueError, TypeError):
                return (1, job_num, 0)

        enquiries = sorted(enquiries, key=sort_key, reverse=True)
    else:
        enquiries = enquiries.order_by('-date', '-created_at')

    # Get current page and per_page values
    current_page = request.GET.get('page', 1)

    # Get per_page value from request, default to 10
    try:
        per_page = int(request.GET.get('per_page', 100))
        # Limit to reasonable values
        if per_page < 1:
            per_page = 10
        elif per_page > 100:
            per_page = 100
    except (ValueError, TypeError):
        per_page = 10

    # Pagination
    paginator = Paginator(enquiries, per_page)

    try:
        enquiries_page = paginator.page(current_page)
    except PageNotAnInteger:
        enquiries_page = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page
        enquiries_page = paginator.page(paginator.num_pages)

    latest_update = SalesEnquiry.objects.aggregate(
        latest=Max('updated_at')
    )['latest']
    total_count = enquiries.count()

    context = {
        'enquiries': enquiries_page,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
        'latest_update': latest_update.isoformat() if latest_update else '',
        'total_count': total_count,
    }
    return render(request, 'sales_tracker.html', context)


@login_required
def add_sales_enquiry(request):
    """Add new sales enquiry"""
    # Get the page, sort, search, and per_page from the request
    page = request.GET.get('page', '1')
    sort_by = request.GET.get('sort_by', 'date')
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '10')

    if request.method == 'POST':
        form = SalesEnquiryAddForm(request.POST)
        if form.is_valid():
            enquiry = form.save(commit=False)
            enquiry.created_by = request.user
            enquiry.save()
            messages.success(request, 'Sales enquiry added successfully!')
            # Redirect back to the same page with filters
            params = {'page': page, 'sort_by': sort_by, 'per_page': per_page}
            if search_query:
                params['search'] = search_query
            redirect_url = f"{reverse('sales_tracker')}?{urlencode(params)}"
            return redirect(redirect_url)
    else:
        form = SalesEnquiryAddForm()

    context = {
        'form': form,
        'action': 'Add',
        'is_add_form': True,
        'page': page,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
    }
    return render(request, 'sales_enquiry_form.html', context)


@login_required
def edit_sales_enquiry(request, pk):
    """Edit existing sales enquiry"""
    enquiry = get_object_or_404(SalesEnquiry, pk=pk)
    old_status = enquiry.status

    # Get the page, sort, search, and per_page from the request
    page = request.GET.get('page', '1')
    sort_by = request.GET.get('sort_by', 'date')
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '10')

    if request.method == 'POST':
        form = SalesEnquiryEditForm(request.POST, instance=enquiry)
        if form.is_valid():
            updated_enquiry = form.save()

            from monthly_awards.models import MonthlyAward
            from invoiced_jobs.models import InvoicedJob
            from django.utils import timezone

            # If status changed to "Awarded", create Monthly Award AND auto-create invoice
            if old_status != 'Awarded' and updated_enquiry.status == 'Awarded':
                award = MonthlyAward.objects.create(
                    sale=updated_enquiry,
                    job_number=updated_enquiry.job_number,
                    location=updated_enquiry.location,
                    client=updated_enquiry.client,
                    client_contact=updated_enquiry.client_contact,
                    email=updated_enquiry.email,
                    phone=updated_enquiry.phone,
                    value=updated_enquiry.value,
                    date=timezone.now().date(),
                    created_by=request.user
                )

                # ✅ AUTO-CREATE invoice only for sales tracker awards
                InvoicedJob.objects.create(
                    award=award,
                    date=timezone.now().date(),
                    utility_value=0,
                    cad_value=0,
                    topo_value=0,
                    contractor_value=0,
                    status='Pending',
                    created_by=request.user
                )

                messages.success(request, 'Sales enquiry awarded! Monthly award and invoice created automatically.')

            # If status changed FROM "Awarded", delete linked awards (cascade deletes invoices)
            elif old_status == 'Awarded' and updated_enquiry.status != 'Awarded':
                deleted_count = MonthlyAward.objects.filter(sale=updated_enquiry).delete()[0]
                if deleted_count > 0:
                    messages.success(request,
                                     f'Status updated. {deleted_count} linked award(s) and invoice(s) removed.')
                else:
                    messages.success(request, 'Sales enquiry updated successfully!')

            # If status is still "Awarded", update linked awards
            elif updated_enquiry.status == 'Awarded':
                MonthlyAward.objects.filter(sale=updated_enquiry).update(
                    job_number=updated_enquiry.job_number,
                    location=updated_enquiry.location,
                    client=updated_enquiry.client,
                    client_contact=updated_enquiry.client_contact,
                    email=updated_enquiry.email,
                    phone=updated_enquiry.phone,
                    value=updated_enquiry.value
                )
                messages.success(request, 'Sales enquiry and linked awards updated successfully!')
            else:
                messages.success(request, 'Sales enquiry updated successfully!')

            # Redirect back to the same page with filters
            params = {'page': page, 'sort_by': sort_by, 'per_page': per_page}
            if search_query:
                params['search'] = search_query
            redirect_url = f"{reverse('sales_tracker')}?{urlencode(params)}"
            return redirect(redirect_url)
    else:
        form = SalesEnquiryEditForm(instance=enquiry)

    context = {
        'form': form,
        'action': 'Edit',
        'enquiry': enquiry,
        'is_add_form': False,
        'page': page,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
    }
    return render(request, 'sales_enquiry_form.html', context)


@login_required
def delete_sales_enquiry(request, pk):
    """Delete sales enquiry"""
    enquiry = get_object_or_404(SalesEnquiry, pk=pk)

    # Get the page, sort, search, and per_page from the request
    page = request.GET.get('page', '1')
    sort_by = request.GET.get('sort_by', 'date')
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '10')

    if request.method == 'POST':
        enquiry.delete()
        messages.success(request, 'Sales enquiry deleted successfully!')
        # Redirect back to the same page with filters
        params = {'page': page, 'sort_by': sort_by, 'per_page': per_page}
        if search_query:
            params['search'] = search_query
        redirect_url = f"{reverse('sales_tracker')}?{urlencode(params)}"
        return redirect(redirect_url)

    context = {
        'enquiry': enquiry,
        'page': page,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
    }
    return render(request, 'sales_enquiry_confirm_delete.html', context)


@require_GET
def sales_tracker_poll(request):
    """
    API endpoint for polling updates.
    Returns latest data timestamp and optionally full table HTML.
    """
    from .models import SalesEnquiry

    # Get the latest update timestamp from the database
    latest_update = SalesEnquiry.objects.aggregate(
        latest=Max('updated_at')
    )['latest']

    # Get client's last known update time
    client_last_update = request.GET.get('last_update', '')

    # Check if there are new updates
    has_updates = False
    if latest_update:
        latest_str = latest_update.isoformat()
        if not client_last_update or client_last_update < latest_str:
            has_updates = True

    response_data = {
        'has_updates': has_updates,
        'latest_update': latest_update.isoformat() if latest_update else None,
    }

    # If there are updates, include the updated data
    if has_updates:
        # Get filter parameters (same as your main view)
        year = request.GET.get('year')
        month = request.GET.get('month')
        status = request.GET.get('status')
        search_query = request.GET.get('search', '')
        sort_by = request.GET.get('sort_by', 'date')
        per_page = request.GET.get('per_page', 100)
        page = request.GET.get('page', 1)

        # Convert per_page to int
        try:
            per_page = int(per_page)
            if per_page not in [10, 25, 50, 100]:
                per_page = 100
        except (ValueError, TypeError):
            per_page = 100

        # Build queryset with filters
        enquiries = SalesEnquiry.objects.all()

        if year:
            enquiries = enquiries.filter(date__year=int(year))
        if month:
            enquiries = enquiries.filter(date__month=int(month))
        if status:
            enquiries = enquiries.filter(status=status)
        if search_query:
            enquiries = enquiries.filter(
                Q(job_number__icontains=search_query) |
                Q(location__icontains=search_query) |
                Q(client__icontains=search_query)
            )

        # Sort
        if sort_by == 'job_number':
            enquiries = list(enquiries)

            def sort_key(item):
                job_num = item.job_number
                try:
                    if '.' in job_num:
                        parts = job_num.split('.')
                        return (0, -int(parts[0]), -int(parts[1]))
                    else:
                        return (0, -int(job_num), 0)
                except (ValueError, TypeError):
                    return (1, job_num, 0)

            enquiries.sort(key=sort_key)
        elif sort_by == 'value':
            enquiries = enquiries.order_by('-value', '-date')
        else:
            enquiries = enquiries.order_by('-date', '-created_at')

        # Calculate totals BEFORE pagination
        if not isinstance(enquiries, list):
            enquiries_list = list(enquiries)
        else:
            enquiries_list = enquiries

        total_value = sum(e.value for e in enquiries_list)
        total_count = len(enquiries_list)

        # Apply pagination
        paginator = Paginator(enquiries_list, per_page)
        try:
            enquiries_page = paginator.page(page)
        except PageNotAnInteger:
            enquiries_page = paginator.page(1)
        except EmptyPage:
            enquiries_page = paginator.page(paginator.num_pages)

        # Render table body HTML (only the current page's rows)
        response_data['table_html'] = render_to_string(
            'partials/table_body.html',
            {'enquiries': enquiries_page}
        )
        response_data['total_value'] = float(total_value)
        response_data['count'] = total_count

    return JsonResponse(response_data)
