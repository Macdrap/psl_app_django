from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.db.models import Count, Sum, Q
from datetime import datetime, date
from decimal import Decimal

from sales_tracker.models import SalesEnquiry


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

        # Calculate percentages
        for key in sales_data:
            if total_count > 0:
                sales_data[key]['percentage'] = round(
                    (sales_data[key]['count'] / total_count) * 100, 1
                )
            else:
                sales_data[key]['percentage'] = 0

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