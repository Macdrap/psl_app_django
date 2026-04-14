from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.urls import reverse
from urllib.parse import urlencode
from datetime import datetime
from .models import MonthlyAward
from .forms import MonthlyAwardForm
from invoiced_jobs.models import InvoicedJob


def get_or_create_client(company_name, contact_name, email, phone):
    """Find or create Client and Contact records from text inputs."""
    from clients.models import Contact, Client

    email = email.strip() if email else None
    phone = phone.strip() if phone else None

    contact_qs = Contact.objects.filter(name=contact_name, email=email, phone=phone)
    if contact_qs.exists():
        contact = contact_qs.first()
    else:
        contact = Contact.objects.create(name=contact_name, email=email, phone=phone)

    client_qs = Client.objects.filter(name=company_name, contact=contact)
    if client_qs.exists():
        client = client_qs.first()
    else:
        client = Client.objects.create(name=company_name, contact=contact)

    return client


@login_required
def monthly_awards_list(request):
    """Monthly awards list view with year/month filtering, search, sort, and pagination"""

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

    # Filter awards by selected year and month
    awards = MonthlyAward.objects.filter(
        date__year=selected_year,
        date__month=selected_month
    )

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        awards = awards.filter(
            Q(job_number__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(client__name__icontains=search_query) |
            Q(client__contact__name__icontains=search_query)
        )

    # Sort by filter
    sort_by = request.GET.get('sort_by', 'date')

    if sort_by == 'job_number':
        awards = list(awards)

        def sort_key(award):
            job_num = award.job_number
            try:
                if '.' in job_num:
                    parts = job_num.split('.')
                    return (0, int(parts[0]), int(parts[1]))
                else:
                    return (0, int(job_num), 0)
            except (ValueError, TypeError):
                return (1, job_num, 0)

        awards = sorted(awards, key=sort_key, reverse=True)
    elif sort_by == 'value':
        awards = awards.order_by('-value', '-date')
    else:
        awards = awards.order_by('-date', '-created_at')

    # Add invoice count and mismatch flags to each award
    awards_with_flags = []
    for award in awards:
        award.invoice_count = award.get_invoice_count()
        award.has_mismatch = award.has_value_mismatch()
        award.is_missing_invoice = award.has_no_invoices()
        awards_with_flags.append(award)

    # Calculate total value for the month (before pagination)
    total_value = sum(award.value for award in awards_with_flags)
    awards_count = len(awards_with_flags)

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
    paginator = Paginator(awards_with_flags, per_page)

    try:
        awards_page = paginator.page(current_page)
    except PageNotAnInteger:
        awards_page = paginator.page(1)
    except EmptyPage:
        awards_page = paginator.page(paginator.num_pages)

    # Generate year range (2020 to current year + 1)
    year_range = range(2020, current_year + 2)

    # Month names
    months = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]

    context = {
        'awards': awards_page,
        'awards_count': awards_count,
        'total_value': total_value,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'year_range': year_range,
        'months': months,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
    }
    return render(request, 'monthly_awards_list.html', context)


@login_required
def add_monthly_award(request):
    """Add new monthly award (NO auto-invoice for manual awards)"""
    # Get filter params to return to the same view state
    page = request.GET.get('page', '1')
    sort_by = request.GET.get('sort_by', 'date')
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '10')
    year = request.GET.get('year', '')
    month = request.GET.get('month', '')

    if request.method == 'POST':
        award_form = MonthlyAwardForm(request.POST)
        if award_form.is_valid():
            award = award_form.save(commit=False)
            award.created_by = request.user

            # Find or create Client from text inputs
            company_name = award_form.cleaned_data['company_name']
            contact_name = award_form.cleaned_data['contact_name']
            email = award_form.cleaned_data.get('email') or None
            phone = award_form.cleaned_data.get('phone') or None
            award.client = get_or_create_client(company_name, contact_name, email, phone)

            award.save()

            messages.success(request, 'Monthly award created! You can now add invoices manually.')

            # Redirect back with filters
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
        award_form = MonthlyAwardForm()

    return render(request, 'monthly_award_form.html', {
        'award_form': award_form,
        'action': 'Add',
        'page': page,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
        'year': year,
        'month': month,
    })


@login_required
def edit_monthly_award(request, pk):
    """Edit existing monthly award"""
    award = get_object_or_404(MonthlyAward, pk=pk)

    # Get filter params
    page = request.GET.get('page', '1')
    sort_by = request.GET.get('sort_by', 'date')
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '10')
    year = request.GET.get('year', '')
    month = request.GET.get('month', '')

    if request.method == 'POST':
        award_form = MonthlyAwardForm(request.POST, instance=award)
        if award_form.is_valid():
            updated_award = award_form.save(commit=False)

            # Find or create Client from text inputs
            company_name = award_form.cleaned_data['company_name']
            contact_name = award_form.cleaned_data['contact_name']
            email = award_form.cleaned_data.get('email') or None
            phone = award_form.cleaned_data.get('phone') or None
            updated_award.client = get_or_create_client(company_name, contact_name, email, phone)
            updated_award.save()

            # Update linked sale if exists
            if updated_award.sale:
                sale = updated_award.sale
                sale.job_number = updated_award.job_number
                sale.location = updated_award.location
                sale.client = updated_award.client
                sale.value = updated_award.value
                sale.save()

            messages.success(request, 'Monthly award updated successfully!')

            # Redirect back with filters
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
        award_form = MonthlyAwardForm(instance=award)

    return render(request, 'monthly_award_form.html', {
        'award_form': award_form,
        'action': 'Edit',
        'award': award,
        'page': page,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
        'year': year,
        'month': month,
    })


@login_required
def delete_monthly_award(request, pk):
    """Delete monthly award (cascade deletes all invoices)"""
    award = get_object_or_404(MonthlyAward, pk=pk)

    # Get filter params
    page = request.GET.get('page', '1')
    sort_by = request.GET.get('sort_by', 'date')
    search_query = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '10')
    year = request.GET.get('year', '')
    month = request.GET.get('month', '')

    if request.method == 'POST':
        # Revert sale status if linked
        if award.sale:
            award.sale.status = 'Pending'
            award.sale.save()

        invoice_count = award.get_invoice_count()
        award.delete()

        if invoice_count > 0:
            messages.success(request,
                             f'Monthly award and {invoice_count} linked invoice(s) deleted! Sale reverted to Pending.')
        else:
            messages.success(request, 'Monthly award deleted successfully!')

        # Redirect back with filters
        params = {'page': page, 'sort_by': sort_by, 'per_page': per_page}
        if search_query:
            params['search'] = search_query
        if year:
            params['year'] = year
        if month:
            params['month'] = month
        redirect_url = f"{reverse('monthly_awards_list')}?{urlencode(params)}"
        return redirect(redirect_url)

    context = {
        'award': award,
        'invoice_count': award.get_invoice_count(),
        'page': page,
        'sort_by': sort_by,
        'search_query': search_query,
        'per_page': per_page,
        'year': year,
        'month': month,
    }
    return render(request, 'monthly_award_confirm_delete.html', context)
