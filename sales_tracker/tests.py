"""Regression tests for the Sales Tracker, including the award/un-award sync
that creates and removes Monthly Awards and Invoiced Jobs."""
from datetime import date
from decimal import Decimal

from django.urls import reverse

from clients.models import Client, Contact
from invoiced_jobs.models import InvoicedJob
from monthly_awards.models import MonthlyAward
from psl_app_project.test_utils import LoggedInTestCase
from sales_tracker.forms import SalesEnquiryAddForm
from sales_tracker.models import SalesEnquiry


def edit_payload(enquiry, **overrides):
    """A complete, valid POST body for the edit form, based on an enquiry."""
    data = {
        'job_number': enquiry.job_number,
        'date': enquiry.date.strftime('%Y-%m-%d'),
        'value': str(enquiry.value),
        'location': enquiry.location,
        'status': enquiry.status,
        'note': '',
        'feedback': '',
        'other_feedback': '',
        'referral': '',
        'company_name': enquiry.client.name,
        'contact_name': enquiry.contact.name,
        'email': '',
        'phone': '',
    }
    data.update(overrides)
    return data


class SalesTrackerListTests(LoggedInTestCase):
    def test_list_renders(self):
        self.make_enquiry(job_number='4242')
        resp = self.client.get(reverse('sales_tracker'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '4242')

    def test_search_matches_client_and_contact(self):
        other = self.make_client('Bravo Surveys')
        self.make_enquiry(job_number='1', client=other, contact=self.make_contact(other, 'Zed Smith'))
        self.make_enquiry(job_number='2')
        for term in ('Bravo', 'Zed'):
            resp = self.client.get(reverse('sales_tracker'), {'search': term})
            self.assertEqual([e.job_number for e in resp.context['enquiries']], ['1'], term)

    def test_sort_by_job_number_is_version_aware(self):
        # Current behaviour: numeric parts compared as integers (9999.10 > 9999.2),
        # and non-numeric job numbers sort ahead of numeric ones.
        for jn in ('9999.2', '9999.10', '100', 'ABC'):
            self.make_enquiry(job_number=jn)
        resp = self.client.get(reverse('sales_tracker'), {'sort_by': 'job_number'})
        self.assertEqual([e.job_number for e in resp.context['enquiries']],
                         ['ABC', '9999.10', '9999.2', '100'])

    def test_per_page_defaults_to_100_and_caps_at_200(self):
        resp = self.client.get(reverse('sales_tracker'))
        self.assertEqual(resp.context['per_page'], 100)
        resp = self.client.get(reverse('sales_tracker'), {'per_page': 500})
        self.assertEqual(resp.context['per_page'], 200)


class AddSalesEnquiryTests(LoggedInTestCase):
    def post_add(self, **overrides):
        data = {
            'job_number': '5001', 'location': 'York', 'note': '',
            'company_name': 'Acme Ltd', 'contact_name': 'John Doe',
            'email': 'john@example.com', 'phone': '0123',
            'sector': 'construction', 'client_status': 'current', 'referral': '',
        }
        data.update(overrides)
        return self.client.post(reverse('add_sales_enquiry'), data)

    def test_add_creates_enquiry_client_and_contact(self):
        resp = self.post_add()
        self.assertEqual(resp.status_code, 302)
        enquiry = SalesEnquiry.objects.get(job_number='5001')
        self.assertEqual(enquiry.status, 'Pending')
        self.assertEqual(enquiry.created_by, self.user)
        self.assertEqual(enquiry.client.name, 'Acme Ltd')
        self.assertEqual(enquiry.client.sector, 'construction')
        self.assertEqual(enquiry.contact.email, 'john@example.com')

    def test_add_reuses_existing_client_by_trimmed_name(self):
        self.post_add(job_number='1')
        self.post_add(job_number='2', company_name='  Acme Ltd  ', contact_name='Jane Roe')
        self.assertEqual(Client.objects.count(), 1)
        self.assertEqual(Contact.objects.filter(client__name='Acme Ltd').count(), 2)

    def test_existing_contact_details_are_updated(self):
        self.post_add(job_number='1')
        self.post_add(job_number='2', email='new@example.com', phone='999')
        contact = Contact.objects.get(name='John Doe')
        self.assertEqual((contact.email, contact.phone), ('new@example.com', '999'))

    def test_referral_only_kept_for_new_clients(self):
        self.post_add(job_number='1', client_status='new', referral='google', company_name='NewCo')
        self.post_add(job_number='2', client_status='current', referral='google', company_name='OldCo')
        self.assertEqual(SalesEnquiry.objects.get(job_number='1').referral, 'google')
        self.assertIsNone(SalesEnquiry.objects.get(job_number='2').referral)

    def test_redirect_keeps_list_state(self):
        resp = self.client.post(
            reverse('add_sales_enquiry') + '?page=3&sort_by=job_number&per_page=200&scroll=850&search=x',
            {'job_number': '1', 'location': 'L', 'company_name': 'A', 'contact_name': 'B'},
        )
        for part in ('page=3', 'sort_by=job_number', 'per_page=200', 'scroll=850', 'search=x'):
            self.assertIn(part, resp['Location'])

    def test_add_form_suggests_next_job_number(self):
        self.make_enquiry(job_number='120')
        self.make_enquiry(job_number='99.5')
        self.assertEqual(SalesEnquiryAddForm().fields['job_number'].initial, 121)


class AwardSyncTests(LoggedInTestCase):
    """Status changes on a sales enquiry drive Monthly Awards and Invoiced Jobs."""

    def setUp(self):
        super().setUp()
        self.enquiry = self.make_enquiry(job_number='7000', value='1500')

    def award(self, **invoice_fields):
        data = edit_payload(self.enquiry, status='Awarded', value='1500')
        data.update({
            'invoice_date': '2026-03-15', 'invoice_utility_value': '500',
            'invoice_cad_value': '200', 'invoice_topo_value': '300',
            'invoice_contractor_value': '500',
        })
        data.update(invoice_fields)
        resp = self.client.post(reverse('edit_sales_enquiry', args=[self.enquiry.pk]), data)
        self.assertEqual(resp.status_code, 302, 'edit form rejected the award POST')
        return resp

    def test_awarding_creates_award_and_invoice(self):
        resp = self.award()
        self.assertEqual(resp.status_code, 302)
        award = MonthlyAward.objects.get(sale=self.enquiry)
        self.assertEqual(award.job_number, '7000')
        self.assertEqual(award.value, Decimal('1500'))
        self.assertEqual(award.client, self.enquiry.client)
        self.assertEqual(award.date, date.today())
        invoice = InvoicedJob.objects.get(award=award)
        self.assertEqual(invoice.date, date(2026, 3, 15))
        self.assertEqual(invoice.status, 'Pending')
        self.assertEqual(invoice.contractor_value, Decimal('500'))
        self.assertEqual(invoice.psl_value, Decimal('1000'))  # utility + cad + topo
        self.assertEqual(invoice.follow_up_status, 'n_a')  # was the invalid "N/A" before
        self.assertFalse(award.has_value_mismatch())

    def test_awarding_with_blank_invoice_values_defaults_to_today_and_zero(self):
        self.award(invoice_date='', invoice_utility_value='0', invoice_cad_value='0',
                   invoice_topo_value='0', invoice_contractor_value='0')
        invoice = InvoicedJob.objects.get(award__sale=self.enquiry)
        self.assertEqual(invoice.date, date.today())
        self.assertEqual(invoice.get_total_invoice_value(), Decimal('0'))

    def test_editing_awarded_enquiry_syncs_award_and_first_invoice(self):
        self.award()
        self.enquiry.refresh_from_db()
        data = edit_payload(self.enquiry, job_number='7000.1', value='2000', location='Hull')
        data.update({'invoice_utility_value': '900'})
        self.client.post(reverse('edit_sales_enquiry', args=[self.enquiry.pk]), data)
        award = MonthlyAward.objects.get(sale=self.enquiry)
        self.assertEqual((award.job_number, award.value, award.location),
                         ('7000.1', Decimal('2000'), 'Hull'))
        invoice = award.invoiced_jobs.get()
        self.assertEqual(invoice.utility_value, Decimal('900'))
        self.assertEqual(invoice.cad_value, Decimal('200'))  # untouched fields keep their value

    def test_unawarding_deletes_award_and_invoices(self):
        self.award()
        self.enquiry.refresh_from_db()
        self.client.post(reverse('edit_sales_enquiry', args=[self.enquiry.pk]),
                         edit_payload(self.enquiry, status='Rejected'))
        self.assertFalse(MonthlyAward.objects.exists())
        self.assertFalse(InvoicedJob.objects.exists())

    def test_deleting_enquiry_cascades_to_award(self):
        self.award()
        self.client.post(reverse('delete_sales_enquiry', args=[self.enquiry.pk]))
        self.assertFalse(SalesEnquiry.objects.exists())
        self.assertFalse(MonthlyAward.objects.exists())
        self.assertFalse(InvoicedJob.objects.exists())

    def test_delete_page_get_does_not_delete(self):
        resp = self.client.get(reverse('delete_sales_enquiry', args=[self.enquiry.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(SalesEnquiry.objects.exists())


class PollEndpointTests(LoggedInTestCase):
    def test_poll_without_changes_returns_json(self):
        self.make_enquiry()
        resp = self.client.get(reverse('sales_tracker_poll'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['has_updates'])
        self.assertEqual(resp.json()['current_count'], 1)

    def test_poll_with_changes_returns_table_html(self):
        # Regression: the partial was deleted in v1.0.7 and this 500'd every 3 s.
        self.make_enquiry(job_number='31337', referral='google')
        resp = self.client.get(reverse('sales_tracker_poll'), {'last_count': '0'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['has_updates'])
        self.assertIn('31337', data['table_html'])
        self.assertIn('Google', data['table_html'])  # same columns as the main page
        self.assertIn('data-enquiry-id=', data['table_html'])

    def test_poll_detects_newer_timestamp(self):
        self.make_enquiry()
        resp = self.client.get(reverse('sales_tracker_poll'),
                               {'last_update': '2000-01-01T00:00:00+00:00', 'last_count': '1'})
        self.assertTrue(resp.json()['has_updates'])

    def test_poll_rows_match_main_page_rows(self):
        for jn in ('1', '2', '3'):
            self.make_enquiry(job_number=jn)
        page = self.client.get(reverse('sales_tracker'), {'per_page': 2, 'page': 2}).content.decode()
        poll = self.client.get(reverse('sales_tracker_poll'),
                               {'per_page': 2, 'page': 2, 'last_count': '0'}).json()['table_html']
        self.assertIn(poll.strip(), page)

    def test_poll_honours_200_per_page_like_main_view(self):
        for i in range(150):
            self.make_enquiry(job_number=str(i))
        html = self.client.get(reverse('sales_tracker_poll'),
                               {'per_page': 200, 'last_count': '0'}).json()['table_html']
        self.assertEqual(html.count('data-enquiry-id='), 150)

    def test_poll_empty_result_shows_message(self):
        resp = self.client.get(reverse('sales_tracker_poll'), {'last_count': '5'})
        self.assertIn('No enquiries found', resp.json()['table_html'])
