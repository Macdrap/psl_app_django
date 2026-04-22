from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.db.models import Count, Sum, Q
from datetime import datetime, date
from decimal import Decimal

from sales_tracker.models import SalesEnquiry
from clients.models import SECTOR_CHOICES, CLIENT_STATUS_CHOICES


class StatisticExplorerView(LoginRequiredMixin, TemplateView):
    template_name = "statistic_explorer.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get filter parameters
        filter_type = self.request.GET.get('filter_type', 'all')

        # Month/Year filter
        selected_year = self.request.GET.get('year')
        selected_month = self.request.GET.get('month')

        # Date range filter
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')

        # Current date for defaults
        current_year = datetime.now().year
        current_month = datetime.now().month

        # Convert year/month to integers if provided
        if selected_year:
            try:
                selected_year = int(selected_year)
            except (ValueError, TypeError):
                selected_year = current_year
        else:
            selected_year = current_year

        if selected_month:
            try:
                selected_month = int(selected_month)
            except (ValueError, TypeError):
                selected_month = current_month
        else:
            selected_month = current_month

        # Parse date range if provided
        parsed_date_from = None
        parsed_date_to = None
        if date_from:
            try:
                parsed_date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            except ValueError:
                parsed_date_from = None
        if date_to:
            try:
                parsed_date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            except ValueError:
                parsed_date_to = None

        # Base queryset
        enquiries = SalesEnquiry.objects.all()

        # Apply filters based on filter_type
        filter_description = "All Time"

        if filter_type == 'month' and selected_year and selected_month:
            enquiries = enquiries.filter(
                date__year=selected_year,
                date__month=selected_month
            )
            month_names = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December']
            filter_description = f"{month_names[selected_month]} {selected_year}"

        elif filter_type == 'range' and parsed_date_from and parsed_date_to:
            enquiries = enquiries.filter(
                date__gte=parsed_date_from,
                date__lte=parsed_date_to
            )
            filter_description = f"{parsed_date_from.strftime('%d %b %Y')} to {parsed_date_to.strftime('%d %b %Y')}"

        # Aggregate sales data by status
        sales_stats = enquiries.values('status').annotate(
            count=Count('id'),
            total_value=Sum('value')
        )

        # Initialize counters
        sales_data = {
            'awarded': {'count': 0, 'value': Decimal('0.00')},
            'rejected': {'count': 0, 'value': Decimal('0.00')},
            'pending': {'count': 0, 'value': Decimal('0.00')},
        }

        # Populate from query results
        for stat in sales_stats:
            status_key = stat['status'].lower()
            if status_key in sales_data:
                sales_data[status_key]['count'] = stat['count']
                sales_data[status_key]['value'] = stat['total_value'] or Decimal('0.00')

        # Calculate totals
        total_count = sum(d['count'] for d in sales_data.values())
        total_value = sum(d['value'] for d in sales_data.values())

        # Calculate percentages (by count and by value)
        for key in sales_data:
            sales_data[key]['percentage'] = round(
                (sales_data[key]['count'] / total_count) * 100, 1
            ) if total_count else 0
            sales_data[key]['value_percentage'] = round(
                float(sales_data[key]['value']) / float(total_value) * 100, 1
            ) if total_value else 0

        # Aggregate feedback data
        feedback_stats = enquiries.exclude(
            Q(feedback__isnull=True) | Q(feedback='')
        ).values('feedback').annotate(
            count=Count('id')
        )

        # Initialize feedback counters
        feedback_data = {
            'timeframe': {'count': 0},
            'price': {'count': 0},
            'capability': {'count': 0},
            'other': {'count': 0},
        }

        # Populate from query results
        for stat in feedback_stats:
            feedback_key = stat['feedback'].lower()
            if feedback_key in feedback_data:
                feedback_data[feedback_key]['count'] = stat['count']

        # Calculate feedback totals
        feedback_total_count = sum(d['count'] for d in feedback_data.values())

        # Calculate feedback percentages
        for key in feedback_data:
            if feedback_total_count > 0:
                feedback_data[key]['percentage'] = round(
                    (feedback_data[key]['count'] / feedback_total_count) * 100, 1
                )
            else:
                feedback_data[key]['percentage'] = 0

        # ── Referral analysis ─────────────────────────────────────────────────
        from sales_tracker.models import SalesEnquiry as SEModel
        REFERRAL_CHOICES = SEModel.REFERRAL_CHOICES

        referral_stats = (
            enquiries
            .exclude(Q(referral__isnull=True) | Q(referral=''))
            .values('referral', 'status')
            .annotate(count=Count('id'), total_value=Sum('value'))
        )

        referral_data = {}
        for code, label in REFERRAL_CHOICES:
            referral_data[code] = {
                'label': label,
                'awarded': {'count': 0, 'value': Decimal('0.00')},
                'rejected': {'count': 0, 'value': Decimal('0.00')},
                'pending':  {'count': 0, 'value': Decimal('0.00')},
            }

        for stat in referral_stats:
            code   = stat['referral'] or 'other'
            status = (stat['status'] or '').lower()
            if code in referral_data and status in ('awarded', 'rejected', 'pending'):
                referral_data[code][status]['count'] += stat['count']
                referral_data[code][status]['value'] += stat['total_value'] or Decimal('0.00')

        _referral_palette = {'google': '#4285f4', 'recommendation': '#10b981', 'other': '#6b7280'}
        for code, data in referral_data.items():
            tc = data['awarded']['count'] + data['rejected']['count'] + data['pending']['count']
            tv = data['awarded']['value'] + data['rejected']['value'] + data['pending']['value']
            data['total_count'] = tc
            data['total_value'] = tv
            for st in ('awarded', 'rejected', 'pending'):
                data[st]['pct_count'] = round(data[st]['count'] / tc * 100, 1) if tc else 0
                data[st]['pct_value'] = round(float(data[st]['value']) / float(tv) * 100, 1) if tv else 0
            data['color'] = _referral_palette.get(code, '#9ca3af')

        active_referrals = {k: v for k, v in referral_data.items() if v['total_count'] > 0}
        referral_has_data = bool(active_referrals)

        all_ref_count = sum(v['total_count'] for v in active_referrals.values())
        all_ref_value = sum(float(v['total_value']) for v in active_referrals.values())
        for data in active_referrals.values():
            data['pct_of_all_count'] = round(data['total_count'] / all_ref_count * 100, 1) if all_ref_count else 0
            data['pct_of_all_value'] = round(float(data['total_value']) / all_ref_value * 100, 1) if all_ref_value else 0

        referral_labels       = [v['label']             for v in active_referrals.values()]
        referral_total_counts = [v['total_count']        for v in active_referrals.values()]
        referral_total_values = [float(v['total_value']) for v in active_referrals.values()]
        referral_colors       = [v['color']              for v in active_referrals.values()]

        # ── Sector analysis ───────────────────────────────────────────────────
        sector_stats = (
            enquiries
            .filter(client__isnull=False)
            .values('client__sector', 'status')
            .annotate(count=Count('id'), total_value=Sum('value'))
        )

        # Initialise one entry per known sector
        sector_data = {}
        for code, label in SECTOR_CHOICES:
            sector_data[code] = {
                'label': label,
                'awarded': {'count': 0, 'value': Decimal('0.00')},
                'rejected': {'count': 0, 'value': Decimal('0.00')},
                'pending':  {'count': 0, 'value': Decimal('0.00')},
            }

        for stat in sector_stats:
            code   = stat['client__sector'] or 'other'
            status = (stat['status'] or '').lower()
            if code in sector_data and status in ('awarded', 'rejected', 'pending'):
                sector_data[code][status]['count'] = stat['count']
                sector_data[code][status]['value'] = stat['total_value'] or Decimal('0.00')

        # Totals + percentages per sector
        for code, data in sector_data.items():
            tc = data['awarded']['count'] + data['rejected']['count'] + data['pending']['count']
            tv = data['awarded']['value'] + data['rejected']['value'] + data['pending']['value']
            data['total_count'] = tc
            data['total_value'] = tv
            for st in ('awarded', 'rejected', 'pending'):
                data[st]['pct_count'] = round(data[st]['count'] / tc * 100, 1) if tc else 0
                data[st]['pct_value'] = round(float(data[st]['value']) / float(tv) * 100, 1) if tv else 0

        # Assign a distinct colour to each sector (consistent with SECTOR_CHOICES order)
        _palette = ['#6366f1', '#f59e0b', '#10b981', '#3b82f6', '#ec4899', '#8b5cf6', '#6b7280']
        _color_map = {code: _palette[i] for i, (code, _) in enumerate(SECTOR_CHOICES)}
        for code, data in sector_data.items():
            data['color'] = _color_map.get(code, '#9ca3af')

        # Only keep sectors that have at least one enquiry
        active_sectors = {k: v for k, v in sector_data.items() if v['total_count'] > 0}
        sector_has_data = bool(active_sectors)

        # % of all enquiries / all value that each sector represents
        all_sector_count = sum(v['total_count'] for v in active_sectors.values())
        all_sector_value = sum(float(v['total_value']) for v in active_sectors.values())
        for data in active_sectors.values():
            data['pct_of_all_count'] = round(data['total_count'] / all_sector_count * 100, 1) if all_sector_count else 0
            data['pct_of_all_value'] = round(float(data['total_value']) / all_sector_value * 100, 1) if all_sector_value else 0

        # Chart-ready flat lists (same order as active_sectors)
        sector_labels          = [v['label']                        for v in active_sectors.values()]
        sector_awarded_counts  = [v['awarded']['count']             for v in active_sectors.values()]
        sector_rejected_counts = [v['rejected']['count']            for v in active_sectors.values()]
        sector_pending_counts  = [v['pending']['count']             for v in active_sectors.values()]
        sector_awarded_values  = [float(v['awarded']['value'])      for v in active_sectors.values()]
        sector_rejected_values = [float(v['rejected']['value'])     for v in active_sectors.values()]
        sector_pending_values  = [float(v['pending']['value'])      for v in active_sectors.values()]
        sector_total_counts    = [v['total_count']                  for v in active_sectors.values()]
        sector_total_values    = [float(v['total_value'])           for v in active_sectors.values()]
        sector_win_pct_count   = [v['awarded']['pct_count']         for v in active_sectors.values()]
        sector_win_pct_value   = [v['awarded']['pct_value']         for v in active_sectors.values()]
        sector_chart_colors    = [v['color']                        for v in active_sectors.values()]

        # ── Client status analysis ────────────────────────────────────────────
        from clients.models import Client as ClientModel
        _status_palette = {'current': '#10b981', 'new': '#3b82f6', 'dormant': '#9ca3af'}

        # How many CLIENTS exist per status (for the doughnut)
        client_counts_qs = ClientModel.objects.values('client_status').annotate(c=Count('id'))
        client_counts_by_status = {row['client_status']: row['c'] for row in client_counts_qs}
        total_clients = sum(client_counts_by_status.values())

        # Enquiry breakdown per client-status × enquiry-status (for summary rows)
        enquiry_by_cs = (
            enquiries
            .filter(client__isnull=False)
            .values('client__client_status', 'status')
            .annotate(count=Count('id'), total_value=Sum('value'))
        )

        client_status_data = {}
        for code, label in CLIENT_STATUS_CHOICES:
            client_status_data[code] = {
                'label': label,
                'client_count': client_counts_by_status.get(code, 0),
                'pct_clients': round(client_counts_by_status.get(code, 0) / total_clients * 100, 1) if total_clients else 0,
                'color': _status_palette.get(code, '#6b7280'),
                'awarded': {'count': 0, 'value': Decimal('0.00')},
                'pending':  {'count': 0, 'value': Decimal('0.00')},
                'rejected': {'count': 0, 'value': Decimal('0.00')},
            }

        for stat in enquiry_by_cs:
            cs_code    = stat['client__client_status'] or 'current'
            enq_status = (stat['status'] or '').lower()
            if cs_code in client_status_data and enq_status in ('awarded', 'pending', 'rejected'):
                client_status_data[cs_code][enq_status]['count'] = stat['count']
                client_status_data[cs_code][enq_status]['value'] = stat['total_value'] or Decimal('0.00')

        # Compute per-status totals and value %
        for d in client_status_data.values():
            d['total_enquiry_count'] = d['awarded']['count'] + d['pending']['count'] + d['rejected']['count']
            d['total_enquiry_value'] = d['awarded']['value'] + d['pending']['value'] + d['rejected']['value']

        total_all_enquiry_value = sum(d['total_enquiry_value'] for d in client_status_data.values())
        for d in client_status_data.values():
            d['pct_value'] = round(
                float(d['total_enquiry_value']) / float(total_all_enquiry_value) * 100, 1
            ) if total_all_enquiry_value else 0
            # Win rate per client status (% of enquiries awarded, by count and by value)
            tc = d['total_enquiry_count']
            tv = float(d['total_enquiry_value'])
            d['awarded_pct_count'] = round(d['awarded']['count'] / tc * 100, 1) if tc else 0
            d['awarded_pct_value'] = round(float(d['awarded']['value']) / tv * 100, 1) if tv else 0

        active_client_statuses = {k: v for k, v in client_status_data.items() if v['client_count'] > 0}
        client_status_has_data = bool(active_client_statuses)

        # Chart-ready lists
        cs_labels        = [v['label']                       for v in active_client_statuses.values()]
        cs_client_counts = [v['client_count']                for v in active_client_statuses.values()]
        cs_values        = [float(v['total_enquiry_value'])  for v in active_client_statuses.values()]
        cs_colors        = [v['color']                       for v in active_client_statuses.values()]
        cs_total_clients = total_clients

        # Generate year range for dropdown
        year_range = range(2020, current_year + 2)

        # Month names for dropdown
        months = [
            (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
            (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
            (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
        ]

        context.update({
            'filter_type': filter_type,
            'selected_year': selected_year,
            'selected_month': selected_month,
            'date_from': date_from or '',
            'date_to': date_to or '',
            'year_range': year_range,
            'months': months,
            'filter_description': filter_description,

            # Sales data for chart
            'sales_data': sales_data,
            'sales_total_count': total_count,
            'sales_total_value': total_value,

            # Feedback data for chart
            'feedback_data': feedback_data,
            'feedback_total_count': feedback_total_count,

            # Referral data
            'active_referrals':      active_referrals,
            'referral_has_data':     referral_has_data,
            'referral_labels':       referral_labels,
            'referral_total_counts': referral_total_counts,
            'referral_total_values': referral_total_values,
            'referral_colors':       referral_colors,

            # Sector data
            'active_sectors': active_sectors,
            'sector_has_data': sector_has_data,
            'sector_labels':          sector_labels,
            'sector_awarded_counts':  sector_awarded_counts,
            'sector_rejected_counts': sector_rejected_counts,
            'sector_pending_counts':  sector_pending_counts,
            'sector_awarded_values':  sector_awarded_values,
            'sector_rejected_values': sector_rejected_values,
            'sector_pending_values':  sector_pending_values,
            'sector_total_counts':    sector_total_counts,
            'sector_total_values':    sector_total_values,
            'sector_win_pct_count':   sector_win_pct_count,
            'sector_win_pct_value':   sector_win_pct_value,
            'sector_chart_colors':    sector_chart_colors,

            # Client status data
            'active_client_statuses':   active_client_statuses,
            'client_status_has_data':   client_status_has_data,
            'cs_labels':          cs_labels,
            'cs_client_counts':   cs_client_counts,
            'cs_values':          cs_values,
            'cs_colors':          cs_colors,
            'cs_total_clients':   cs_total_clients,
            'cs_total_value':     total_all_enquiry_value,

            # Chart data as JSON-ready values
            'chart_labels': ['Awarded', 'Rejected', 'Pending'],
            'chart_values': [
                sales_data['awarded']['count'],
                sales_data['rejected']['count'],
                sales_data['pending']['count']
            ],
            'chart_colors': ['#10b981', '#ef4444', '#f59e0b'],
        })

        return context


class StatisticExplorerPDFView(LoginRequiredMixin, TemplateView):
    """Generate PDF export of statistics"""

    def get(self, request, *args, **kwargs):
        # Get the same context as the main view
        explorer_view = StatisticExplorerView()
        explorer_view.request = request
        context = explorer_view.get_context_data()

        # Get section toggles from query params
        context['show_sales_status']    = request.GET.get('show_sales_status', 'true') == 'true'
        context['show_feedback']        = request.GET.get('show_feedback', 'true') == 'true'
        context['show_sector']          = request.GET.get('show_sector', 'true') == 'true'
        context['show_client_status']   = request.GET.get('show_client_status', 'true') == 'true'
        context['show_referral']        = request.GET.get('show_referral', 'true') == 'true'

        # Render PDF template
        html_string = render_to_string('statistic_explorer_pdf.html', context)

        # Try to use weasyprint for PDF generation
        try:
            from weasyprint import HTML
            pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()

            response = HttpResponse(pdf_file, content_type='application/pdf')
            filename = f"statistics_{context['filter_description'].replace(' ', '_')}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except ImportError:
            # Fallback: return HTML for printing
            return HttpResponse(html_string, content_type='text/html')