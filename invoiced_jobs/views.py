from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime
from django.db.models import Sum, Q
from .models import InvoicedJob
from .forms import InvoicedJobForm
from monthly_awards.models import MonthlyAward


@login_required
def invoiced_jobs_list(request):
    """Invoiced jobs list view with year, month filtering, and mismatch detection"""

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

    # Add mismatch flags to jobs
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

    # Calculate totals for the month
    invoiced_jobs = [j for j in jobs_with_flags if j.status == 'Invoiced']
    pending_jobs = [j for j in jobs_with_flags if j.status == 'Pending']

    total_invoiced = sum(
        job.utility_value + job.cad_value +
        job.topo_value + job.contractor_value
        for job in invoiced_jobs
    )
    total_pending = sum(job.utility_value + job.cad_value +
        job.topo_value + job.contractor_value for job in pending_jobs)
    total_value = total_invoiced + total_pending

    # Generate year range (2020 to current year + 1)
    year_range = range(2020, current_year + 2)

    # Month names
    months = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]

    context = {
        'jobs': jobs_with_flags,
        'total_invoiced': total_invoiced,
        'total_pending': total_pending,
        'total_value': total_value,
        'invoiced_count': len(invoiced_jobs),
        'pending_count': len(pending_jobs),
        'selected_year': selected_year,
        'selected_month': selected_month,
        'year_range': year_range,
        'months': months,
    }
    return render(request, 'invoiced_jobs_list.html', context)


@login_required
def add_invoiced_job(request):
    """Add new invoiced job"""
    if request.method == 'POST':
        form = InvoicedJobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.created_by = request.user
            job.save()
            messages.success(request, 'Invoice added successfully!')
            return redirect('invoiced_jobs_list')
    else:
        form = InvoicedJobForm()

    context = {
        'form': form,
        'action': 'Add'
    }
    return render(request, 'invoiced_job_form.html', context)


@login_required
def edit_invoiced_job(request, pk):
    """Edit existing invoiced job"""
    job = get_object_or_404(InvoicedJob, pk=pk)

    if request.method == 'POST':
        form = InvoicedJobForm(request.POST, instance=job)
        if form.is_valid():
            form.save()
            messages.success(request, 'Invoice updated successfully!')
            return redirect('invoiced_jobs_list')
    else:
        form = InvoicedJobForm(instance=job)

    context = {
        'form': form,
        'action': 'Edit',
        'job': job
    }
    return render(request, 'invoiced_job_form.html', context)


@login_required
def delete_invoiced_job(request, pk):
    """Delete invoiced job"""
    job = get_object_or_404(InvoicedJob, pk=pk)

    if request.method == 'POST':
        award = job.award
        job.delete()

        # Check if award now has no invoices
        if award.has_no_invoices():
            messages.warning(request, 'Invoice deleted. Warning: Award now has no invoices!')
        else:
            messages.success(request, 'Invoice deleted successfully!')

        return redirect('invoiced_jobs_list')

    context = {
        'job': job
    }
    return render(request, 'invoiced_job_confirm_delete.html', context)


@login_required
def add_invoice_to_award(request, award_pk):
    """Quick add invoice directly from monthly awards page"""
    award = get_object_or_404(MonthlyAward, pk=award_pk)

    if request.method == 'POST':
        form = InvoicedJobForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.award = award  # Force this award
            job.created_by = request.user
            job.save()
            messages.success(request, f'Invoice added to award #{award.job_number}!')
            return redirect('monthly_awards_list')
    else:
        # Pre-fill the form with this award
        form = InvoicedJobForm(initial={'award': award.id})

    context = {
        'form': form,
        'action': 'Add Invoice',
        'award': award
    }
    return render(request, 'invoiced_job_form.html', context)