from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum, Q
from django.urls import reverse
from urllib.parse import urlencode
from datetime import datetime
from .models import InvoicedJob
from .forms import InvoicedJobForm
from monthly_awards.models import MonthlyAward


@login_required
def invoiced_jobs_list(request):
    """Invoiced jobs list view with year/month filtering, search, sort, and pagination"""

    # Get year and month from request, default to current
    current_year = datetime.now().year
    current_month = datetime.now().month

    selected_year = request.GET.get('year', current_year)
    selected_month = request.GET.get('month', current_month)

    # Convert to integers
    try:
        selected_year = int(selected_year)
        selected_month = int(selected_month)
    except (ValueError, TypeError):
        selected_year = current_year
        selected_month = current_month

    # Filter invoiced jobs by selected year and month
    jobs = InvoicedJob.objects.filter(
        date__year=selected_year,
        date__month=selected_month
    ).select_related('award')

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        jobs = jobs.filter(
            Q(award__job_number__icontains=search_query) |
            Q(award__location__icontains=search_query) |
            Q(award__client__name__icontains=search_query) |
            Q(award__client__contact__name__icontains=search_query)
        )

    # Add mismatch flags and totals to jobs
    jobs_with_flags = []
    for job in jobs:
        job.has_mismatch = job.award.has_value_mismatch()
        job.award_total = job.award.value
        job.total_invoiced = job.award.get_total_invoiced()
        job.this_invoice_total = (
            job.utility_value +
            job.cad_value +
            job.topo_value +
            job.contractor_value
        )
        jobs_with_flags.append(job)

    # Sort by filter
    sort_by = request.GET.get('sort_by', 'date')

    if sort_by == 'job_number':
        def sort_key(job):
            job_num = job.award.job_number
            try:
                if '.' in job_num:
                    parts = job_num.split('.')
                    return (0, int(parts[0]), int(parts[1]))
                else:
                    return (0, int(job_num), 0)
            except (ValueError, TypeError):
                return (1, job_num, 0)

        jobs_with_flags = sorted(jobs_with_flags, key=sort_key, reverse=True)
    elif sort_by == 'value':
        jobs_with_flags = sorted(jobs_with_flags, key=lambda j: j.this_invoice_total, reverse=True)
    else:
        jobs_with_flags = sorted(jobs_with_flags, key=lambda j: (j.date, j.created_at), reverse=True)

    # Calculate totals for the month (before pagination)
    invoiced_jobs = [j for j in jobs_with_flags if j.status == 'Invoiced']
    pending_jobs = [j for j in jobs_with_flags if j.status == 'Pending']
    utils_jobs = [j for j in jobs_with_flags if j.utility_value > 0]
    topo_jobs = [j for j in jobs_with_flags if j.topo_value > 0]
    cad_jobs = [j for j in jobs_with_flags if j.cad_value > 0]
    contractor_jobs = [j for j in jobs_with_flags if j.contractor_value > 0]

    total_invoiced = sum(j.this_invoice_total for j in invoiced_jobs)
    total_pending = sum(j.this_invoice_total for j in pending_jobs)
    total_value = total_invoiced + total_pending
    contractor_value = sum(j.contractor_value for j in contractor_jobs)
    total_psl_value = total_value - contractor_value
    total_utils = sum(j.utility_value for j in utils_jobs)
    total_topo = sum(j.topo_value for j in topo_jobs)
    total_cad = sum(j.cad_value for j in cad_jobs)
    jobs_count = len(jobs_with_flags)

    # Get per_page value from request, default to 100
    try:
        per_page = int(request.GET.get('per_page', 100))
        if per_page < 1:
            per_page = 10
        elif per_page > 100:
            per_page = 100
    except (ValueError, TypeError):
        per_page = 10

    # Pagination
    current_page = request.GET.get('page', 1)
    paginator = Paginator(jobs_with_flags, per_page)

    try:
        jobs_page = paginator.page(current_page)
    except PageNotAnInteger:
        jobs_page = paginator.page(1)
    except EmptyPage:
        jobs_page = paginator.page(paginator.num_pages)

    # Generate year range (2020 to current year + 1)
    year_range = range(2020, current_year + 2)

    # Month names
    months = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]

    context = {
        'jobs': jobs_page,
        'jobs_count': jobs_count,
        'total_invoiced': total_invoiced,
        'total_pending': total_pending,
        'total_value': total_value,
        'total_psl_value': total_psl_value,
        'total_utils': total_utils,
        'utils_jobs_count':len(utils_jobs),
        'total_topo': total_topo,
        'topo_jobs_count': len(topo_jobs),
        'total_cad': total_cad,
        'cad_jobs_count': len(cad_jobs),
        'invoiced_count': len(invoiced_jobs),
        'pending_count': len(pending_jobs),
        'selected_year': selected_year,
        'selected_month': selected_month,
        'year_range': year_range,
        'months': months,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
    }
    return render(request, 'invoiced_jobs_list.html', context)


@login_required
def add_invoiced_job(request):
    """Add new invoiced job"""
    # Get filter params to return to the same view state
    page = request.GET.get('page', '1')
    sort_by = request.GET.get('sort_by', 'date')
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '10')
    year = request.GET.get('year', '')
    month = request.GET.get('month', '')
    scroll_pos = request.GET.get('scroll', '0')

    if request.method == 'POST':
        form = InvoicedJobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.created_by = request.user
            job.save()
            messages.success(request, 'Invoice added successfully!')

            params = {'page': page, 'sort_by': sort_by, 'per_page': per_page, 'scroll': scroll_pos}
            if search_query:
                params['search'] = search_query
            if year:
                params['year'] = year
            if month:
                params['month'] = month
            redirect_url = f"{reverse('invoiced_jobs_list')}?{urlencode(params)}"
            return redirect(redirect_url)
    else:
        form = InvoicedJobForm()

    context = {
        'form': form,
        'action': 'Add',
        'page': page,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
        'year': year,
        'month': month,
        'scroll_pos': scroll_pos,
    }
    return render(request, 'invoiced_job_form.html', context)


@login_required
def edit_invoiced_job(request, pk):
    """Edit existing invoiced job"""
    job = get_object_or_404(InvoicedJob, pk=pk)

    # Get filter params
    page = request.GET.get('page', '1')
    sort_by = request.GET.get('sort_by', 'date')
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '10')
    year = request.GET.get('year', '')
    month = request.GET.get('month', '')
    scroll_pos = request.GET.get('scroll', '0')

    if request.method == 'POST':
        scroll_pos = request.POST.get('scroll', scroll_pos)
        form = InvoicedJobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, 'Invoice updated successfully!')

            params = {'page': page, 'sort_by': sort_by, 'per_page': per_page, 'scroll': scroll_pos}
            if search_query:
                params['search'] = search_query
            if year:
                params['year'] = year
            if month:
                params['month'] = month
            redirect_url = f"{reverse('invoiced_jobs_list')}?{urlencode(params)}"
            return redirect(redirect_url)
    else:
        form = InvoicedJobForm(instance=job)

    context = {
        'form': form,
        'action': 'Edit',
        'job': job,
        'page': page,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
        'year': year,
        'month': month,
        'scroll_pos': scroll_pos,
    }
    return render(request, 'invoiced_job_form.html', context)


@login_required
def delete_invoiced_job(request, pk):
    """Delete invoiced job"""
    job = get_object_or_404(InvoicedJob, pk=pk)

    # Get filter params
    page = request.GET.get('page', '1')
    sort_by = request.GET.get('sort_by', 'date')
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '10')
    year = request.GET.get('year', '')
    month = request.GET.get('month', '')
    scroll_pos = request.GET.get('scroll', '0')

    if request.method == 'POST':
        scroll_pos = request.POST.get('scroll', scroll_pos)
        award = job.award
        job.delete()

        if award.has_no_invoices():
            messages.warning(request, 'Invoice deleted. Warning: Award now has no invoices!')
        else:
            messages.success(request, 'Invoice deleted successfully!')

        params = {'page': page, 'sort_by': sort_by, 'per_page': per_page, 'scroll': scroll_pos}
        if search_query:
            params['search'] = search_query
        if year:
            params['year'] = year
        if month:
            params['month'] = month
        redirect_url = f"{reverse('invoiced_jobs_list')}?{urlencode(params)}"
        return redirect(redirect_url)

    context = {
        'job': job,
        'page': page,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
        'year': year,
        'month': month,
        'scroll_pos': scroll_pos,
    }
    return render(request, 'invoiced_job_confirm_delete.html', context)


@login_required
def add_invoice_to_award(request, award_pk):
    """Quick add invoice directly from monthly awards page"""
    award = get_object_or_404(MonthlyAward, pk=award_pk)

    # Get filter params (from monthly awards page)
    page = request.GET.get('page', '1')
    sort_by = request.GET.get('sort_by', 'date')
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '10')
    year = request.GET.get('year', '')
    month = request.GET.get('month', '')

    if request.method == 'POST':
        form = InvoicedJobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.award = award  # Force this award
            job.created_by = request.user
            job.save()
            messages.success(request, f'Invoice added to award #{award.job_number}!')

            # Redirect back to monthly awards with filters
            params = {'page': page, 'sort_by': sort_by, 'per_page': per_page}
            if search_query:
                params['search'] = search_query
            if year:
                params['year'] = year
            if month:
                params['month'] = month
            redirect_url = f"{reverse('monthly_awards_list')}?{urlencode(params)}"
            return redirect(redirect_url)
    else:
        # Pre-fill the form with this award
        form = InvoicedJobForm(initial={'award': award.id})

    context = {
        'form': form,
        'action': 'Add Invoice',
        'award': award,
        'page': page,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
        'year': year,
        'month': month,
    }
    return render(request, 'invoiced_job_form.html', context)