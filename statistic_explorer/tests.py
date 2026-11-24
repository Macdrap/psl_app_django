"""Smoke/regression tests for the Statistic Explorer."""
import sys
import types
from datetime import date
from decimal import Decimal
from unittest import mock

from django.urls import reverse

from clients.models import SECTOR_CHOICES
from sales_tracker.models import SalesEnquiry
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

    def test_every_referral_source_gets_a_distinct_colour(self):
        # Adding a source to SalesEnquiry.REFERRAL_CHOICES needs a colour in
        # _REFERRAL_PALETTE in statistic_explorer/views.py.
        from statistic_explorer.views import _REFERRAL_PALETTE
        codes = [code for code, _ in SalesEnquiry.REFERRAL_CHOICES]
        self.assertEqual(set(_REFERRAL_PALETTE), set(codes))
        self.assertEqual(len(set(_REFERRAL_PALETTE.values())), len(codes))

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


class ClientAnalysisTests(LoggedInTestCase):
    """Per-client quote table + search in 'Client Analysis'."""

    def rows_by_name(self, resp):
        return {row['name']: row for row in resp.context['client_rows']}

    def test_per_client_counts_values_and_win_rate(self):
        acme = self.make_client('Acme Ltd', sector='architects')
        self.make_enquiry(job_number='1', value='1000', status='Awarded', client=acme)
        self.make_enquiry(job_number='2', value='500', status='Rejected', client=acme)
        self.make_enquiry(job_number='3', value='300', status='Pending', client=acme,
                          date=date(2026, 5, 1))
        self.make_enquiry(job_number='4', value='200', status='Awarded', client=acme,
                          date=date(2026, 6, 15))
        resp = self.client.get(reverse('statistic_explorer'))
        row = self.rows_by_name(resp)['Acme Ltd']
        self.assertEqual(row['sector'], 'Architects')
        self.assertEqual(row['quote_count'], 4)
        self.assertEqual(row['total_value'], Decimal('2000'))
        self.assertEqual(row['avg_value'], Decimal('500'))
        self.assertEqual((row['awarded_count'], row['awarded_value']), (2, Decimal('1200')))
        self.assertEqual((row['rejected_count'], row['rejected_value']), (1, Decimal('500')))
        self.assertEqual((row['pending_count'], row['pending_value']), (1, Decimal('300')))
        self.assertEqual(row['win_rate'], 50.0)        # 2 of 4 quotes
        self.assertEqual(row['win_rate_value'], 60.0)  # £1200 of £2000
        self.assertEqual(row['last_date'], max(date.today(), date(2026, 6, 15)))

    def test_zero_value_and_not_quoted_enquiries_are_excluded(self):
        acme = self.make_client('Acme Ltd')
        self.make_enquiry(job_number='1', value='400', status='Pending', client=acme)
        self.make_enquiry(job_number='2', value='0', status='Pending', client=acme)
        self.make_enquiry(job_number='3', value='900', status='Not_Quoted', client=acme)
        only_unpriced = self.make_client('Unpriced Co')
        self.make_enquiry(job_number='4', value='0', status='Pending', client=only_unpriced)
        resp = self.client.get(reverse('statistic_explorer'))
        rows = self.rows_by_name(resp)
        self.assertEqual(rows['Acme Ltd']['quote_count'], 1)
        self.assertEqual(rows['Acme Ltd']['total_value'], Decimal('400'))
        self.assertNotIn('Unpriced Co', rows)

    def test_sorted_by_total_quoted_highest_first(self):
        for name, value in (('Small', '100'), ('Big', '9000'), ('Mid', '500')):
            self.make_enquiry(job_number=name, value=value, client=self.make_client(name))
        resp = self.client.get(reverse('statistic_explorer'))
        self.assertEqual([r['name'] for r in resp.context['client_rows']], ['Big', 'Mid', 'Small'])

    def test_rows_follow_the_date_filter(self):
        acme = self.make_client('Acme Ltd')
        self.make_enquiry(job_number='1', value='100', client=acme, date=date(2026, 1, 10))
        self.make_enquiry(job_number='2', value='900', client=acme, date=date(2026, 2, 10))
        resp = self.client.get(reverse('statistic_explorer'),
                               {'filter_type': 'month', 'year': 2026, 'month': 2})
        row = self.rows_by_name(resp)['Acme Ltd']
        self.assertEqual((row['quote_count'], row['total_value']), (1, Decimal('900')))

    def test_page_renders_table_search_and_json_data(self):
        self.make_enquiry(job_number='1', value='1234', client=self.make_client('Acme Ltd'))
        resp = self.client.get(reverse('statistic_explorer'))
        self.assertContains(resp, 'id="client-analysis-section"')
        self.assertContains(resp, 'id="clientSearch"')
        self.assertContains(resp, 'id="client-rows-data"')
        self.assertContains(resp, '£1,234')

    def test_no_quotes_shows_empty_message(self):
        resp = self.client.get(reverse('statistic_explorer'))
        self.assertEqual(resp.context['client_rows'], [])
        self.assertContains(resp, 'No client quotes available')

    def test_pdf_shows_top_clients_and_can_be_hidden(self):
        for i in range(25):
            self.make_enquiry(job_number=str(i), value=str(100 + i),
                              client=self.make_client(f'Client {i:02d}'))
        with mock.patch.dict(sys.modules, {'weasyprint': None}):  # HTML fallback
            resp = self.client.get(reverse('statistic_explorer_pdf'))
            hidden = self.client.get(reverse('statistic_explorer_pdf'),
                                     {'show_client_analysis': 'false'})
        self.assertContains(resp, 'Top 20 of 25 Clients')
        self.assertContains(resp, 'Client 24')      # highest value
        self.assertNotContains(resp, 'Client 04')   # 21st by value, outside top 20
        self.assertNotContains(hidden, 'Client Analysis')


class ReferralConversionTests(LoggedInTestCase):
    """'New Client Conversion' in Referral Analysis: do referred new clients
    come back for more enquiries and win work?"""

    def enquiry(self, client, job, when, status='Pending', value='100', referral=None):
        return self.make_enquiry(job_number=job, value=value, status=status, client=client,
                                 contact=self.make_contact(client, name=f'Contact {job}'),
                                 date=when, referral=referral)

    def setUp(self):
        super().setUp()
        # Google: one converted (came back + award), one one-off.
        g1 = self.make_client('Google Converted', client_status='new')
        self.enquiry(g1, 'g1a', date(2026, 3, 1), 'Rejected', referral='google')
        self.enquiry(g1, 'g1b', date(2026, 6, 1), 'Awarded', value='2000', referral='google')
        g2 = self.make_client('Google One-off', client_status='new')
        self.enquiry(g2, 'g2a', date(2026, 3, 5), referral='google')
        # Recommendation: awarded on its only enquiry.
        r1 = self.make_client('Recommended Once', client_status='new')
        self.enquiry(r1, 'r1a', date(2026, 4, 2), 'Awarded', value='500', referral='recommendation')
        # Other: came back twice, nothing awarded yet.
        o1 = self.make_client('Other Returner', client_status='new')
        self.enquiry(o1, 'o1a', date(2026, 3, 9), 'Rejected', referral='other')
        self.enquiry(o1, 'o1b', date(2026, 5, 9), 'Pending', referral='other')
        # Legacy client: no referral recorded -> not in the cohort.
        legacy = self.make_client('Legacy Ltd')
        self.enquiry(legacy, 'l1', date(2026, 3, 1), 'Awarded')
        self.enquiry(legacy, 'l2', date(2026, 3, 2), 'Awarded')

    def get(self, **params):
        return self.client.get(reverse('statistic_explorer'), params)

    def test_outcome_per_client_and_legacy_clients_excluded(self):
        resp = self.get()
        outcomes = {c['name']: c['outcome'] for c in resp.context['conversion_clients']}
        self.assertEqual(outcomes, {
            'Google Converted': 'converted',
            'Google One-off': 'one_off',
            'Recommended Once': 'awarded_once',
            'Other Returner': 'returned',
        })

    def test_summary_per_source_and_total(self):
        sources = self.get().context['conversion_sources']
        self.assertEqual(list(sources), ['google', 'recommendation', 'other', 'total'])
        g = sources['google']
        self.assertEqual((g['clients'], g['returned'], g['awarded'], g['converted']), (2, 1, 1, 1))
        self.assertEqual((g['returned_pct'], g['converted_pct']), (50.0, 50.0))
        self.assertEqual(g['enquiries_per_client'], 1.5)
        self.assertEqual((g['awarded_jobs'], g['awarded_value']), (1, Decimal('2000')))
        t = sources['total']
        self.assertEqual((t['clients'], t['returned'], t['awarded'], t['converted']), (4, 2, 2, 1))
        self.assertEqual(t['converted_pct'], 25.0)
        self.assertEqual([o['count'] for o in t['outcomes']], [1, 1, 1, 1])

    def test_period_picks_first_enquiry_but_follow_up_runs_to_today(self):
        # March: Google Converted's first enquiry is in March; its award in
        # June still counts. Recommended Once (first enquiry April) is out.
        resp = self.get(filter_type='month', year=2026, month=3)
        names = {c['name']: c for c in resp.context['conversion_clients']}
        self.assertEqual(set(names), {'Google Converted', 'Google One-off', 'Other Returner'})
        self.assertEqual(names['Google Converted']['outcome'], 'converted')
        self.assertEqual(names['Google Converted']['enquiry_count'], 2)

    def test_client_whose_first_enquiry_was_earlier_is_not_new_in_a_later_period(self):
        # June: Google Converted had an enquiry, but it was won in March.
        resp = self.get(filter_type='month', year=2026, month=6)
        self.assertEqual(resp.context['conversion_clients'], [])
        self.assertEqual(resp.context['conversion_sources'], {})
        self.assertContains(resp, 'No new clients with a referral source')

    def test_page_and_pdf_render_the_section(self):
        resp = self.get()
        self.assertContains(resp, 'New Client Conversion')
        self.assertContains(resp, 'Show the 4 clients')
        self.assertContains(resp, 'outcome-pill outcome-converted')
        with mock.patch.dict(sys.modules, {'weasyprint': None}):  # HTML fallback
            pdf = self.client.get(reverse('statistic_explorer_pdf'))
            hidden = self.client.get(reverse('statistic_explorer_pdf'), {'show_referral': 'false'})
        self.assertContains(pdf, 'New Client Conversion by Referral Source')
        self.assertNotContains(hidden, 'New Client Conversion')


class SurveyTypeAnalysisTests(LoggedInTestCase):
    """Survey Type Analysis: quoted from the enquiries, awarded from the awards."""

    def setUp(self):
        super().setUp()
        d = date(2026, 3, 10)
        job1 = self.make_enquiry(job_number='1', value='1000', status='Awarded', date=d, survey_types=['mbs', 'topo'],
                                 survey_type_values={'mbs': '600.00', 'topo': '400.00'})
        # less was awarded than quoted: MBS £450 instead of £600
        self.make_award(sale=job1, value='850', survey_types=['mbs', 'topo'],
                        survey_type_values={'mbs': '450.00', 'topo': '400.00'})
        self.make_enquiry(job_number='2', value='500', status='Rejected', date=d, survey_types=['mbs'],
                          survey_type_values={'mbs': '500.00'})
        self.make_enquiry(job_number='3', value='0', status='Pending', date=d, survey_types=['topo'])  # not a quote
        self.make_enquiry(job_number='4', value='200', status='Pending', date=d)                       # untagged
        job5 = self.make_enquiry(job_number='5', value='800', status='Awarded', date=date(2025, 1, 5),
                                 survey_types=['drone'], survey_type_values={'drone': '800.00'})
        self.make_award(sale=job5, value='800', survey_types=['drone'], survey_type_values={'drone': '800.00'})
        # manual award (no enquiry): not part of the Statistic Explorer
        self.make_award(job_number='M1', value='5000', survey_types=['mbs'], survey_type_values={'mbs': '5000.00'})

    def stats(self, **params):
        resp = self.client.get(reverse('statistic_explorer'), params)
        self.assertEqual(resp.status_code, 200)
        st = resp.context['survey_type_data']
        return resp, st, {r['code']: r for r in st['rows']}

    def test_per_type_figures_and_awarded_total(self):
        _, st, rows = self.stats(filter_type='month', year=2026, month=3)
        self.assertEqual(set(rows), {'mbs', 'topo'})
        mbs, topo = rows['mbs'], rows['topo']
        self.assertEqual((mbs['enquiries'], mbs['quotes'], mbs['quoted_value']), (2, 2, Decimal('1100')))
        self.assertEqual((mbs['awarded_count'], mbs['awarded_value'], mbs['rejected_count']),
                         (1, Decimal('450'), 1))  # the award's value, not the quote's £600
        self.assertEqual((mbs['win_rate'], mbs['win_rate_value']), (50.0, 40.9))
        self.assertEqual((topo['enquiries'], topo['quotes'], topo['awarded_value'], topo['win_rate']),
                         (2, 1, Decimal('400'), 100.0))
        self.assertEqual((mbs['awarded_pct'], topo['awarded_pct']), (52.9, 47.1))
        self.assertEqual((st['total_awarded'], st['total_quoted']), (Decimal('850'), Decimal('1500')))
        self.assertEqual((st['untagged'], st['multi_type']), (1, 1))

    def test_follows_the_date_filter(self):
        _, _, rows = self.stats()
        self.assertIn('drone', rows)
        _, st, rows = self.stats(filter_type='range', date_from='2025-01-01', date_to='2025-12-31')
        self.assertEqual(set(rows), {'drone'})
        self.assertEqual(st['total_awarded'], Decimal('800'))

    def test_page_and_pdf_show_awarded_total_and_no_dept_share(self):
        resp, _, _ = self.stats(filter_type='month', year=2026, month=3)
        self.assertContains(resp, 'Survey Type Analysis')
        self.assertContains(resp, 'id="surveyTypeShareChart"')
        self.assertContains(resp, 'id="st-awarded"')
        self.assertContains(resp, 'Awarded value total')
        self.assertNotContains(resp, 'Dept. Share')
        with mock.patch.dict(sys.modules, {'weasyprint': None}):  # HTML fallback
            pdf = self.client.get(reverse('statistic_explorer_pdf'))
            hidden = self.client.get(reverse('statistic_explorer_pdf'), {'show_survey_type': 'false'})
        self.assertContains(pdf, 'Survey Type Analysis')
        self.assertContains(pdf, 'Awarded value total')
        self.assertNotContains(pdf, 'Dept. Share')
        self.assertNotContains(hidden, 'Survey Type Analysis')

    def test_no_survey_types_shows_empty_message(self):
        from monthly_awards.models import MonthlyAward
        SalesEnquiry.objects.update(survey_types=[])
        _, st, rows = self.stats()
        self.assertEqual(set(rows), {'mbs', 'topo', 'drone'})  # awards still have survey types
        MonthlyAward.objects.update(survey_types=[])
        resp, st, _ = self.stats()
        self.assertFalse(st['has_data'])
        self.assertContains(resp, 'No survey type data available')


class SurveyTypeSplitStatsTests(LoggedInTestCase):
    def test_values_add_up_and_never_split_jobs_count_under_their_first_type(self):
        job1 = self.make_enquiry(job_number='1', value='1000', status='Awarded', survey_types=['mbs', 'topo'],
                                 survey_type_values={'mbs': '600', 'topo': '400'})
        self.make_award(sale=job1, value='1000', survey_types=['mbs', 'topo'],
                        survey_type_values={'mbs': '600', 'topo': '400'})
        job2 = self.make_enquiry(job_number='2', value='500', status='Awarded', survey_types=['mbs', 'topo'])  # never split
        self.make_award(sale=job2, value='500', survey_types=['mbs', 'topo'])
        st = self.client.get(reverse('statistic_explorer')).context['survey_type_data']
        rows = {r['code']: r for r in st['rows']}
        self.assertEqual((rows['mbs']['quoted_value'], rows['mbs']['awarded_value']), (Decimal('1100'), Decimal('1100')))
        self.assertEqual(rows['topo']['awarded_value'], Decimal('400'))
        self.assertEqual((rows['mbs']['awarded_count'], rows['topo']['awarded_count']), (2, 2))
        self.assertEqual(st['total_awarded'], Decimal('1500'))  # = the two jobs' real values
