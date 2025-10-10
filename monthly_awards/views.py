from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime
from .models import MonthlyAward
from .forms import MonthlyAwardForm
from invoiced_jobs.models import InvoicedJob


@login_required
def monthly_awards_list(request):
    """Monthly awards list view with year and month filtering"""

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

    # Add invoice count and mismatch flags to each award
    awards_with_flags = []
    for award in awards:
        award.invoice_count = award.get_invoice_count()
        award.has_mismatch = award.has_value_mismatch()
        award.is_missing_invoice = award.has_no_invoices()
        awards_with_flags.append(award)

    # Calculate total value for the month
    total_value = sum(award.value for award in awards_with_flags)

    # Generate year range (2020 to current year + 1)
    year_range = range(2020, current_year + 2)

    # Month names
    months = [
        (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
        (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
        (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
    ]

    awards_count = len(awards_with_flags)

    context = {
        'awards_count': awards_count,
        'awards': awards_with_flags,
        'total_value': total_value,
        'selected_year': selected_year,
        'selected_month': selected_month,
        'year_range': year_range,
        'months': months,
    }
    return render(request, 'monthly_awards_list.html', context)


@login_required
def add_monthly_award(request):
    """Add new monthly award (NO auto-invoice for manual awards)"""
    if request.method == 'POST':
        award_form = MonthlyAwardForm(request.POST)
        if award_form.is_valid():
            award = award_form.save(commit=False)
            award.created_by = request.user
            award.save()

            # ❌ NO AUTO-INVOICE for manually created awards
            messages.success(request, 'Monthly award created! You can now add invoices manually.')
            return redirect('monthly_awards_list')
    else:
        award_form = MonthlyAwardForm()

    return render(request, 'monthly_award_form.html', {
        'award_form': award_form,
        'action': 'Add'
    })


@login_required
def edit_monthly_award(request, pk):
    """Edit existing monthly award"""
    award = get_object_or_404(MonthlyAward, pk=pk)

    if request.method == 'POST':
        award_form = MonthlyAwardForm(request.POST, instance=award)
        if award_form.is_valid():
            updated_award = award_form.save()

            # Update linked sale if exists
            if updated_award.sale:
                sale = updated_award.sale
                sale.job_number = updated_award.job_number
                sale.location = updated_award.location
                sale.client = updated_award.client
                sale.client_contact = updated_award.client_contact
                sale.email = updated_award.email
                sale.phone = updated_award.phone
                sale.value = updated_award.value
                sale.save()

            messages.success(request, 'Monthly award updated successfully!')
            return redirect('monthly_awards_list')
    else:
        award_form = MonthlyAwardForm(instance=award)

    return render(request, 'monthly_award_form.html', {
        'award_form': award_form,
        'action': 'Edit',
        'award': award
    })


@login_required
def delete_monthly_award(request, pk):
    """Delete monthly award (cascade deletes all invoices)"""
    award = get_object_or_404(MonthlyAward, pk=pk)

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

        return redirect('monthly_awards_list')

    context = {
        'award': award,
        'invoice_count': award.get_invoice_count()
    }
    return render(request, 'monthly_award_confirm_delete.html', context)