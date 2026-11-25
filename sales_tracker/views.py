from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.urls import reverse
from urllib.parse import urlencode
from .models import SalesEnquiry
from .forms import SalesEnquiryAddForm, SalesEnquiryEditForm
from .client_sync import client_referral, promote_new_client
from .survey_types import invoice_fields_from_split
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.template.loader import render_to_string
from django.db.models import Q, Max
from datetime import datetime


def get_or_create_client(company_name, contact_name, email, phone, sector=None, client_status=None):
    """Find or create Client and Contact records from text inputs.

    A Client is looked up by company name alone — no duplicate companies.
    A Contact is scoped to its Client: two different companies can each have
    a 'John Doe', but one company cannot have two 'John Doe' contacts.
    If the contact already exists its details are updated if anything changed.
    sector and client_status are only applied when a brand-new Client is created.
    """
    from clients.models import Contact, Client

    company_name = company_name.strip() if company_name else ''
    contact_name = contact_name.strip() if contact_name else ''
    email = email.strip() if email else None
    phone = phone.strip() if phone else None

    defaults = {}
    if sector:
        defaults['sector'] = sector
    if client_status:
        defaults['client_status'] = client_status

    client, _ = Client.objects.get_or_create(name=company_name, defaults=defaults)

    contact = Contact.objects.filter(client=client, name=contact_name).first()
    if contact:
        if contact.email != email or contact.phone != phone:
            contact.email = email
            contact.phone = phone
            contact.save()
    else:
        contact = Contact.objects.create(
            client=client, name=contact_name, email=email, phone=phone
        )

    return client, contact


@login_required
def sales_tracker(request):
    """Sales tracker list view with pagination"""
    enquiries = SalesEnquiry.objects.all()

    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        enquiries = enquiries.filter(
            Q(job_number__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(client__name__icontains=search_query) |
            Q(contact__name__icontains=search_query) |
            Q(contact__email__icontains=search_query)
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

    # Get per_page value from request, default to 100
    try:
        per_page = int(request.GET.get('per_page', 100))
        # Limit to reasonable values
        if per_page < 1:
            per_page = 10
        elif per_page > 200:
            per_page = 200
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

    # Get total count - use len() if enquiries is a list, count() if queryset
    if isinstance(enquiries, list):
        total_count = len(enquiries)
    else:
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
    per_page = request.GET.get('per_page', '100')
    scroll_pos = request.GET.get('scroll', '0')  # Get scroll position

    if request.method == 'POST':
        form = SalesEnquiryAddForm(request.POST)
        if form.is_valid():
            enquiry = form.save(commit=False)
            enquiry.created_by = request.user

            # Find or create Client from text inputs
            company_name = form.cleaned_data['company_name']
            contact_name = form.cleaned_data['contact_name']
            email = form.cleaned_data.get('email') or None
            phone = form.cleaned_data.get('phone') or None
            sector = form.cleaned_data.get('sector') or None
            client_status = form.cleaned_data.get('client_status') or None
            client, contact = get_or_create_client(company_name, contact_name, email, phone, sector, client_status)
            enquiry.client = client
            enquiry.contact = contact

            # Referral source is per enquiry. Left blank, it defaults to the
            # referral of the client's previous enquiry (the form pre-fills
            # that too when a client is picked from the dropdown).
            enquiry.referral = form.cleaned_data.get('referral') or client_referral(client)

            enquiry.save()
            promote_new_client(client)
            messages.success(request, 'Sales enquiry added successfully!')
            # Redirect back to the same page with filters and scroll
            params = {
                'page': page,
                'sort_by': sort_by,
                'per_page': per_page,
                'scroll': scroll_pos
            }
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
        'scroll_pos': scroll_pos,
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
    per_page = request.GET.get('per_page', '100')
    scroll_pos = request.GET.get('scroll', '0')  # Get scroll position

    # Get existing invoice data if job is already awarded
    existing_invoice = None
    existing_award = None
    if enquiry.status == 'Awarded':
        from monthly_awards.models import MonthlyAward
        from invoiced_jobs.models import InvoicedJob

        try:
            existing_award = MonthlyAward.objects.filter(sale=enquiry).first()
            if existing_award:
                existing_invoice = InvoicedJob.objects.filter(award=existing_award).first()
        except:
            pass

    if request.method == 'POST':
        form = SalesEnquiryEditForm(request.POST, instance=enquiry)
        if form.is_valid():
            updated_enquiry = form.save(commit=False)

            # Find or create Client from text inputs
            company_name = form.cleaned_data['company_name']
            contact_name = form.cleaned_data['contact_name']
            email = form.cleaned_data.get('email') or None
            phone = form.cleaned_data.get('phone') or None
            client, contact = get_or_create_client(company_name, contact_name, email, phone)
            updated_enquiry.client = client
            updated_enquiry.contact = contact
            updated_enquiry.save()
            # Referral is per enquiry; moving it to a `new` client may promote it
            promote_new_client(client)

            from monthly_awards.models import MonthlyAward
            from invoiced_jobs.models import InvoicedJob
            from django.utils import timezone

            # On awarding, the award (and its invoice) start from the quote's
            # value by survey type; what was actually awarded is then edited on
            # Monthly Awards.
            new_split = updated_enquiry.get_survey_type_values()

            def parse_invoice_date():
                raw = request.POST.get('invoice_date', '')
                try:
                    return datetime.strptime(raw, '%Y-%m-%d').date() if raw else None
                except ValueError:
                    return None

            # If status changed to "Awarded", create Monthly Award AND its invoice
            if old_status != 'Awarded' and updated_enquiry.status == 'Awarded':
                award = MonthlyAward.objects.create(
                    sale=updated_enquiry,
                    job_number=updated_enquiry.job_number,
                    location=updated_enquiry.location,
                    client=updated_enquiry.client,
                    contact=updated_enquiry.contact,
                    value=updated_enquiry.value,
                    survey_types=updated_enquiry.survey_types,
                    survey_type_values=updated_enquiry.survey_type_values,
                    date=timezone.now().date(),
                    created_by=request.user
                )
                invoice_date = parse_invoice_date() or timezone.now().date()
                InvoicedJob.objects.create(
                    award=award,
                    date=invoice_date,
                    status='Pending',
                    created_by=request.user,
                    **invoice_fields_from_split(new_split),
                )

                messages.success(
                    request,
                    f'Sales enquiry awarded! Monthly award and invoice created for {invoice_date.strftime("%d %b %Y")}.'
                )

            # If status changed FROM "Awarded", delete linked awards (cascade deletes invoices)
            elif old_status == 'Awarded' and updated_enquiry.status != 'Awarded':
                deleted_count = MonthlyAward.objects.filter(sale=updated_enquiry).delete()[0]
                if deleted_count > 0:
                    messages.success(request,
                                     f'Status updated. {deleted_count} linked award(s) and invoice(s) removed.')
                else:
                    messages.success(request, 'Sales enquiry updated successfully!')

            # If status is still "Awarded": job details follow the enquiry. The
            # award's value/survey types/split are what was awarded and can
            # differ from the quote - they are edited on Monthly Awards only.
            elif updated_enquiry.status == 'Awarded':
                MonthlyAward.objects.filter(sale=updated_enquiry).update(
                    job_number=updated_enquiry.job_number,
                    location=updated_enquiry.location,
                    client=updated_enquiry.client,
                    contact=updated_enquiry.contact,
                )
                awards = list(MonthlyAward.objects.filter(sale=updated_enquiry))
                invoice_updated = False
                invoice_date = parse_invoice_date()
                first_invoice = InvoicedJob.objects.filter(award=awards[0]).first() if awards else None
                if invoice_date and first_invoice and first_invoice.date != invoice_date:
                    first_invoice.date = invoice_date
                    first_invoice.save()
                    invoice_updated = True
                if invoice_updated:
                    messages.success(request, 'Sales enquiry, linked awards, and invoice updated successfully!')
                else:
                    messages.success(request, 'Sales enquiry and linked awards updated successfully!')
            else:
                messages.success(request, 'Sales enquiry updated successfully!')

            # Redirect back to the same page with filters and scroll
            params = {
                'page': page,
                'sort_by': sort_by,
                'per_page': per_page,
                'scroll': scroll_pos
            }
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
        'scroll_pos': scroll_pos,
        'existing_invoice': existing_invoice,
        'existing_award': existing_award,
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
    per_page = request.GET.get('per_page', '100')
    scroll_pos = request.GET.get('scroll', '0')  # Get scroll position

    if request.method == 'POST':
        enquiry.delete()
        messages.success(request, 'Sales enquiry deleted successfully!')
        # Redirect back to the same page with filters and scroll
        params = {
            'page': page,
            'sort_by': sort_by,
            'per_page': per_page,
            'scroll': scroll_pos
        }
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
        'scroll_pos': scroll_pos,
    }
    return render(request, 'sales_enquiry_confirm_delete.html', context)


@login_required
@require_GET
def sales_tracker_poll(request):
    """
    API endpoint for polling updates.
    Returns latest data timestamp and optionally full table HTML.
    Detects: additions/edits (via timestamp) AND deletions (via count).
    """
    from .models import SalesEnquiry

    # Get filter parameters
    search_query = request.GET.get('search', '')
    sort_by = request.GET.get('sort_by', 'date')

    # Match main view's per_page handling exactly
    try:
        per_page = int(request.GET.get('per_page', 100))
        if per_page < 1:
            per_page = 10
        elif per_page > 200:
            per_page = 200
    except (ValueError, TypeError):
        per_page = 10

    page = request.GET.get('page', 1)

    # Get latest_update from ALL records (same as main view)
    latest_update = SalesEnquiry.objects.aggregate(
        latest=Max('updated_at')
    )['latest']

    # Build queryset with filters
    enquiries = SalesEnquiry.objects.all()

    if search_query:
        enquiries = enquiries.filter(
            Q(job_number__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(client__name__icontains=search_query) |
            Q(contact__name__icontains=search_query) |
            Q(contact__email__icontains=search_query)
        )

    # Get current count (filtered)
    current_count = enquiries.count()

    # Get client's last known values
    client_last_update = request.GET.get('last_update', '')
    client_last_count = request.GET.get('last_count', '')

    # Check if there are new updates (timestamp changed OR count changed)
    has_updates = False
    latest_str = latest_update.isoformat() if latest_update else ''

    # Check timestamp (detects adds and edits)
    if latest_str and client_last_update:
        if client_last_update < latest_str:
            has_updates = True

    # Check count (detects deletions AND additions)
    if client_last_count:
        try:
            if int(client_last_count) != current_count:
                has_updates = True
        except (ValueError, TypeError):
            pass

    response_data = {
        'has_updates': has_updates,
        'latest_update': latest_str,
        'current_count': current_count,
    }

    # If there are updates, include the updated data
    if has_updates:
        # Rebuild queryset fresh to ensure clean ordering
        enquiries = SalesEnquiry.objects.all()

        if search_query:
            enquiries = enquiries.filter(
                Q(job_number__icontains=search_query) |
                Q(location__icontains=search_query) |
                Q(client__name__icontains=search_query) |
                Q(contact__name__icontains=search_query) |
                Q(contact__email__icontains=search_query)
            )

        # Apply sorting - MUST match main view exactly
        if sort_by == 'job_number':
            # Convert to list first, then sort
            enquiries_list = list(enquiries)

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

            enquiries_list = sorted(enquiries_list, key=sort_key, reverse=True)
        else:
            # Sort by date - apply order_by then convert to list
            enquiries_list = list(enquiries.order_by('-date', '-created_at'))

        total_value = sum(e.value for e in enquiries_list)

        # Apply pagination
        paginator = Paginator(enquiries_list, per_page)
        try:
            enquiries_page = paginator.page(page)
        except PageNotAnInteger:
            enquiries_page = paginator.page(1)
        except EmptyPage:
            enquiries_page = paginator.page(paginator.num_pages)

        # Render table body HTML
        response_data['table_html'] = render_to_string(
            'partials/table_body.html',
            {
                'enquiries': enquiries_page,
                'sort_by': sort_by,
                'search_query': search_query,
                'per_page': per_page,
            }
        )
        response_data['total_value'] = float(total_value)
        response_data['sort_by'] = sort_by  # For debugging

    return JsonResponse(response_data)
