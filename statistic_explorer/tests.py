"""Smoke/regression tests for the Statistic Explorer."""
import sys
import types
from datetime import date
from decimal import Decimal
from unittest import mock

from django.urls import reverse

from clients.models import SECTOR_CHOICES
from psl_app_project.test_utils import LoggedInTestCase


class StatisticExplorerTests(LoggedInTestCase):
    def setUp(self):
        super().setUp()
        for i, (code, _label) in enumerate(SECTOR_CHOICES):
            client = self.make_client(f'Client {code}', sector=code)
            self.make_enquiry(job_number=str(i), value='100', client=client,
                              contact=self.make_contact(client),
                              status=['Pending', 'Awarded', 'Rejected'][i % 3],
                              referral='google' if i % 2 else None)

    def test_page_renders_for_each_filter_type(self):
        for params in ({}, {'filter_type': 'month', 'year': 2026, 'month': 1},
                       {'filter_type': 'range', 'date_from': '2020-01-01', 'date_to': '2030-12-31'}):
            resp = self.client.get(reverse('statistic_explorer'), params)
            self.assertEqual(resp.status_code, 200, params)

    def test_every_sector_gets_a_distinct_colour(self):
        # Adding a sector to SECTOR_CHOICES needs a new colour in the palette
        # in statistic_explorer/views.py (see commit db3ef43).
        resp = self.client.get(reverse('statistic_explorer'))
        colours = resp.context['sector_chart_colors']
        self.assertEqual(len(colours), len(SECTOR_CHOICES))
        self.assertEqual(len(set(colours)), len(colours))

    def test_pdf_export_returns_pdf_when_weasyprint_works(self):
        fake = types.ModuleType('weasyprint')

        class FakeHTML:
            def __init__(self, string, base_url=None):
                assert 'Statistic' in string or '<html' in string.lower()

            def write_pdf(self):
                return b'%PDF-1.7 fake'

        fake.HTML = FakeHTML
        with mock.patch.dict(sys.modules, {'weasyprint': fake}):
            resp = self.client.get(reverse('statistic_explorer_pdf'),
                                   {'filter_type': 'month', 'year': 2026, 'month': 3})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertEqual(resp.content, b'%PDF-1.7 fake')
        self.assertIn('statistics_March_2026.pdf', resp['Content-Disposition'])

    def test_pdf_export_falls_back_to_html_when_weasyprint_missing(self):
        with mock.patch.dict(sys.modules, {'weasyprint': None}):  # -> ImportError
            resp = self.client.get(reverse('statistic_explorer_pdf'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp['Content-Type'].startswith('text/html'))
        self.assertContains(resp, 'window.print()')

    def test_pdf_export_falls_back_when_system_libraries_missing(self):
        # On Windows, importing weasyprint raises OSError (no Pango libraries).
        real_import = __import__

        def failing_import(name, *args, **kwargs):
            if name == 'weasyprint':
                raise OSError('cannot load library pango')
            return real_import(name, *args, **kwargs)

        with mock.patch.dict(sys.modules), mock.patch('builtins.__import__', failing_import):
            sys.modules.pop('weasyprint', None)
            resp = self.client.get(reverse('statistic_explorer_pdf'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp['Content-Type'].startswith('text/html'))


class QuoteValueStatsTests(LoggedInTestCase):
    """Average / lowest / highest quote value in 'Sales Enquiries by Status'."""

    def test_average_lowest_highest_ignore_zero_value_quotes(self):
        self.make_enquiry(job_number='1', value='100', status='Awarded')
        self.make_enquiry(job_number='2', value='300', status='Rejected')
        self.make_enquiry(job_number='3', value='500', status='Pending')
        self.make_enquiry(job_number='4', value='0', status='Pending')  # unpriced
        resp = self.client.get(reverse('statistic_explorer'))
        stats = resp.context['quote_value_stats']
        self.assertEqual(stats['priced_count'], 3)
        self.assertEqual(stats['avg'], Decimal('300'))
        self.assertEqual(stats['min'], Decimal('100'))
        self.assertEqual(stats['max'], Decimal('500'))
        self.assertContains(resp, 'Average Quote')
        self.assertContains(resp, '£300.00')
        self.assertContains(resp, '£0 quotes excluded')

    def test_stats_follow_the_date_filter(self):
        self.make_enquiry(job_number='1', value='100', date=date(2026, 1, 10))
        self.make_enquiry(job_number='2', value='900', date=date(2026, 2, 10))
        resp = self.client.get(reverse('statistic_explorer'),
                               {'filter_type': 'month', 'year': 2026, 'month': 2})
        stats = resp.context['quote_value_stats']
        self.assertEqual(stats['priced_count'], 1)
        self.assertEqual(stats['min'], Decimal('900'))
        self.assertEqual(stats['max'], Decimal('900'))

    def test_no_priced_quotes_shows_message_instead_of_values(self):
        self.make_enquiry(job_number='1', value='0')
        resp = self.client.get(reverse('statistic_explorer'))
        self.assertEqual(resp.context['quote_value_stats']['priced_count'], 0)
        self.assertIsNone(resp.context['quote_value_stats']['avg'])
        self.assertContains(resp, 'No priced quotes in this period')

    def test_pdf_shows_quote_value_stats(self):
        self.make_enquiry(job_number='1', value='250')
        with mock.patch.dict(sys.modules, {'weasyprint': None}):  # HTML fallback
            resp = self.client.get(reverse('statistic_explorer_pdf'))
        self.assertContains(resp, 'Highest Quote')
        self.assertContains(resp, '£250.00')
