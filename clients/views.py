from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Count, OuterRef, Subquery, IntegerField
from django.db.models.functions import Coalesce
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.views.decorators.http import require_GET

from .models import Client, Contact
from .forms import ClientForm, ContactForm


@login_required
def clients_list(request):
    search_query = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort_by', 'name_asc')

    # Use subqueries for enquiry/award counts to avoid cartesian-product
    # inflation that happens when multiple Count annotations join different tables.
    from sales_tracker.models import SalesEnquiry
    from monthly_awards.models import MonthlyAward as MonthlyAwardModel

    enquiry_sq = (
        SalesEnquiry.objects
        .filter(client=OuterRef('pk'))
        .order_by()          # clear Meta.ordering so it doesn't leak into GROUP BY
        .values('client')
        .annotate(c=Count('pk'))
        .values('c')
    )
    award_sq = (
        MonthlyAwardModel.objects
        .filter(client=OuterRef('pk'))
        .order_by()          # clear Meta.ordering so it doesn't leak into GROUP BY
        .values('client')
        .annotate(c=Count('pk'))
        .values('c')
    )

    clients = Client.objects.prefetch_related('contacts').annotate(
        contact_count=Count('contacts', distinct=True),
        enquiry_count=Coalesce(Subquery(enquiry_sq, output_field=IntegerField()), 0),
        award_count=Coalesce(Subquery(award_sq, output_field=IntegerField()), 0),
    )

    if search_query:
        clients = clients.filter(
            Q(name__icontains=search_query) |
            Q(contacts__name__icontains=search_query) |
            Q(contacts__email__icontains=search_query) |
            Q(contacts__phone__icontains=search_query)
        ).distinct()

    if sort_by == 'name_desc':
        clients = clients.order_by('-name')
    else:
        clients = clients.order_by('name')

    paginator = Paginator(clients, 10)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, 'clients/clients_list.html', {
        'page_obj': page_obj,
        'search_query': search_query,
        'sort_by': sort_by,
    })


@login_required
def client_add(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = Client.objects.create(
                name=form.cleaned_data['company_name'],
                sector=form.cleaned_data['sector'],
                client_status=form.cleaned_data['client_status'],
            )
            messages.success(request, f'Client "{client.name}" added successfully.')
            return redirect('clients_list')
    else:
        form = ClientForm()

    return render(request, 'clients/client_form.html', {
        'form': form,
        'action': 'Add',
    })


@login_required
def client_edit(request, pk):
    client = get_object_or_404(Client, pk=pk)

    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client.name = form.cleaned_data['company_name']
            client.sector = form.cleaned_data['sector']
            client.client_status = form.cleaned_data['client_status']
            client.save()
            messages.success(request, f'Client "{client.name}" updated successfully.')
            return redirect('clients_list')
    else:
        form = ClientForm(instance=client)

    return render(request, 'clients/client_form.html', {
        'form': form,
        'action': 'Edit',
        'client': client,
    })


@login_required
def client_delete(request, pk):
    client = get_object_or_404(Client, pk=pk)

    if request.method == 'POST':
        from django.db.models import ProtectedError
        name = client.name
        try:
            client.delete()
            messages.success(request, f'Client "{name}" deleted successfully.')
            return redirect('clients_list')
        except ProtectedError:
            enquiry_count = client.sales_enquiries.count()
            messages.error(
                request,
                f'"{name}" cannot be deleted because it has {enquiry_count} linked '
                f'sales enquir{"y" if enquiry_count == 1 else "ies"}. '
                f'Please reassign or delete those enquiries first.'
            )
            return redirect('clients_list')

    contact_count = client.contacts.count()
    enquiry_count = client.sales_enquiries.count()
    award_count = client.monthly_awards.count()

    return render(request, 'clients/client_confirm_delete.html', {
        'client': client,
        'contact_count': contact_count,
        'enquiry_count': enquiry_count,
        'award_count': award_count,
    })


@login_required
def contact_list(request, client_pk):
    client = get_object_or_404(Client, pk=client_pk)
    contacts = client.contacts.all().order_by('name')
    return render(request, 'clients/contact_list.html', {
        'client': client,
        'contacts': contacts,
    })


@login_required
def contact_add(request, client_pk):
    client = get_object_or_404(Client, pk=client_pk)

    if request.method == 'POST':
        form = ContactForm(request.POST, client=client)
        if form.is_valid():
            contact = Contact.objects.create(
                client=client,
                name=form.cleaned_data['contact_name'],
                email=form.cleaned_data['email'] or None,
                phone=form.cleaned_data['phone'] or None,
            )
            messages.success(request, f'Contact "{contact.name}" added successfully.')
            return redirect('clients_list')
    else:
        form = ContactForm(client=client)

    return render(request, 'clients/contact_form.html', {
        'form': form,
        'action': 'Add',
        'client': client,
    })


@login_required
def contact_edit(request, client_pk, contact_pk):
    client = get_object_or_404(Client, pk=client_pk)
    contact = get_object_or_404(Contact, pk=contact_pk, client=client)

    if request.method == 'POST':
        form = ContactForm(request.POST, client=client, instance=contact)
        if form.is_valid():
            contact.name = form.cleaned_data['contact_name']
            contact.email = form.cleaned_data['email'] or None
            contact.phone = form.cleaned_data['phone'] or None
            contact.save()
            messages.success(request, f'Contact "{contact.name}" updated successfully.')
            return redirect('clients_list')
    else:
        form = ContactForm(client=client, instance=contact)

    return render(request, 'clients/contact_form.html', {
        'form': form,
        'action': 'Edit',
        'client': client,
        'contact': contact,
    })


@login_required
def contact_delete(request, client_pk, contact_pk):
    client = get_object_or_404(Client, pk=client_pk)
    contact = get_object_or_404(Contact, pk=contact_pk, client=client)

    if request.method == 'POST':
        name = contact.name
        contact.delete()
        messages.success(request, f'Contact "{name}" deleted successfully.')
        return redirect('clients_list')

    return render(request, 'clients/contact_confirm_delete.html', {
        'client': client,
        'contact': contact,
    })


@require_GET
@login_required
def client_autocomplete(request):
    """Return matching clients as JSON for the autocomplete widget."""
    q = request.GET.get('q', '').strip()
    results = []

    if q:
        clients = (
            Client.objects.prefetch_related('contacts')
            .filter(
                Q(name__icontains=q) |
                Q(contacts__name__icontains=q)
            )
            .distinct()
            .order_by('name')[:10]
        )
        for c in clients:
            first_contact = c.contacts.first()
            results.append({
                'id': c.pk,
                'name': c.name,
                'contact_name': first_contact.name if first_contact else '',
                'email': first_contact.email or '' if first_contact else '',
                'phone': first_contact.phone or '' if first_contact else '',
            })

    return JsonResponse(results, safe=False)


@require_GET
@login_required
def client_contacts_api(request, client_pk):
    """Return all contacts for a specific client as JSON."""
    client = get_object_or_404(Client, pk=client_pk)
    contacts = client.contacts.order_by('name')
    data = [
        {
            'id': c.pk,
            'name': c.name,
            'email': c.email or '',
            'phone': c.phone or '',
        }
        for c in contacts
    ]
    return JsonResponse(data, safe=False)
