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

    def test_website_contact_form_referral_saved(self):
        self.post_add(job_number='1', client_status='new', referral='website_form', company_name='WebCo')
        self.assertEqual(SalesEnquiry.objects.get(job_number='1').referral, 'website_form')
        resp = self.client.get(reverse('sales_tracker'))
        self.assertContains(resp, 'Website Contact Form')

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


class ClientReferralAndStatusTests(LoggedInTestCase):
    """Referral source is shared by all of a client's enquiries, and a `new`
    client becomes `current` once it has more than one enquiry."""

    post_add = AddSalesEnquiryTests.post_add

    def referrals(self, client_name):
        return set(SalesEnquiry.objects.filter(client__name=client_name)
                   .values_list('referral', flat=True))

    def edit(self, enquiry, **overrides):
        resp = self.client.post(reverse('edit_sales_enquiry', args=[enquiry.pk]),
                                edit_payload(enquiry, **overrides))
        self.assertEqual(resp.status_code, 302, 'edit form rejected the POST')
        enquiry.refresh_from_db()
        return resp

    # ---- referral ----------------------------------------------------------

    def test_new_enquiry_for_existing_client_inherits_referral(self):
        self.post_add(job_number='1', company_name='NewCo', client_status='new', referral='google')
        self.post_add(job_number='2', company_name='NewCo', client_status='current', referral='')
        self.assertEqual(SalesEnquiry.objects.get(job_number='2').referral, 'google')

    def test_referral_given_on_add_applies_to_clients_earlier_enquiries(self):
        acme = self.make_client('Acme Ltd')
        self.make_enquiry(job_number='1', client=acme)
        self.post_add(job_number='2', company_name='Acme Ltd', client_status='new', referral='recommendation')
        self.assertEqual(self.referrals('Acme Ltd'), {'recommendation'})

    def test_editing_referral_updates_all_of_that_clients_enquiries_only(self):
        acme, bravo = self.make_client('Acme Ltd'), self.make_client('Bravo Ltd')
        first = self.make_enquiry(job_number='1', client=acme, referral='google')
        self.make_enquiry(job_number='2', client=acme, referral='google')
        self.make_enquiry(job_number='3', client=bravo, contact=self.make_contact(bravo), referral='google')
        self.edit(first, referral='other')
        self.assertEqual(self.referrals('Acme Ltd'), {'other'})
        self.assertEqual(self.referrals('Bravo Ltd'), {'google'})

    def test_clearing_referral_clears_it_for_the_whole_client(self):
        acme = self.make_client('Acme Ltd')
        first = self.make_enquiry(job_number='1', client=acme, referral='google')
        self.make_enquiry(job_number='2', client=acme, referral='google')
        self.edit(first, referral='')
        self.assertEqual(self.referrals('Acme Ltd'), {None})

    def test_moving_enquiry_to_another_client_takes_that_clients_referral(self):
        acme, bravo = self.make_client('Acme Ltd'), self.make_client('Bravo Ltd')
        moved = self.make_enquiry(job_number='1', client=acme, referral='google')
        self.make_enquiry(job_number='2', client=bravo, contact=self.make_contact(bravo),
                          referral='recommendation')
        self.edit(moved, company_name='Bravo Ltd', referral='google')
        self.assertEqual(moved.client, bravo)
        self.assertEqual(self.referrals('Bravo Ltd'), {'recommendation'})

    def test_moving_enquiry_to_client_without_referral_carries_it_over(self):
        acme, bravo = self.make_client('Acme Ltd'), self.make_client('Bravo Ltd')
        moved = self.make_enquiry(job_number='1', client=acme, referral='google')
        self.make_enquiry(job_number='2', client=bravo, contact=self.make_contact(bravo))
        self.edit(moved, company_name='Bravo Ltd', referral='google')
        self.assertEqual(self.referrals('Bravo Ltd'), {'google'})

    def test_moving_sale_via_award_edit_takes_new_clients_referral_and_status(self):
        from monthly_awards.tests import award_payload
        acme = self.make_client('Acme Ltd')
        bravo = self.make_client('Bravo Ltd', client_status='new')
        sale = self.make_enquiry(job_number='8000', value='1200', status='Awarded', client=acme,
                                 referral='google')
        self.make_enquiry(job_number='2', client=bravo, contact=self.make_contact(bravo), referral='other')
        award = self.make_award(sale=sale, job_number='8000', value='1200')
        self.client.post(reverse('edit_monthly_award', args=[award.pk]),
                         award_payload(company_name='Bravo Ltd'))
        sale.refresh_from_db()
        bravo.refresh_from_db()
        self.assertEqual((sale.client, sale.referral), (bravo, 'other'))
        self.assertEqual(bravo.client_status, 'current')

    # ---- new -> current ----------------------------------------------------

    def test_new_client_becomes_current_on_second_enquiry(self):
        self.post_add(job_number='1', company_name='NewCo', client_status='new', referral='google')
        self.assertEqual(Client.objects.get(name='NewCo').client_status, 'new')
        self.post_add(job_number='2', company_name='NewCo', client_status='current')
        self.assertEqual(Client.objects.get(name='NewCo').client_status, 'current')

    def test_dormant_client_is_not_changed(self):
        self.make_client('Sleepy Ltd', client_status='dormant')
        self.post_add(job_number='1', company_name='Sleepy Ltd')
        self.post_add(job_number='2', company_name='Sleepy Ltd')
        self.assertEqual(Client.objects.get(name='Sleepy Ltd').client_status, 'dormant')

    def test_moving_enquiry_onto_new_client_promotes_it(self):
        acme = self.make_client('Acme Ltd')
        newco = self.make_client('NewCo', client_status='new')
        self.make_enquiry(job_number='1', client=newco, contact=self.make_contact(newco))
        moved = self.make_enquiry(job_number='2', client=acme)
        self.edit(moved, company_name='NewCo')
        newco.refresh_from_db()
        self.assertEqual(newco.client_status, 'current')

    # ---- migration 0017 ----------------------------------------------------

    def test_migration_0017_syncs_existing_referrals_and_statuses(self):
        import importlib
        from django.apps import apps
        migration = importlib.import_module('sales_tracker.migrations.0017_sync_client_referral_and_status')
        mixed = self.make_client('Mixed Ltd', client_status='new')
        c_mixed = self.make_contact(mixed)
        self.make_enquiry(job_number='1', client=mixed, contact=c_mixed, date=date(2026, 3, 1))
        self.make_enquiry(job_number='2', client=mixed, contact=c_mixed, date=date(2026, 1, 1),
                          referral='recommendation')
        self.make_enquiry(job_number='3', client=mixed, contact=c_mixed, date=date(2026, 2, 1),
                          referral='google')
        plain = self.make_client('Plain Ltd', client_status='new')
        self.make_enquiry(job_number='4', client=plain, contact=self.make_contact(plain))
        sleepy = self.make_client('Sleepy Ltd', client_status='dormant')
        c_sleepy = self.make_contact(sleepy)
        self.make_enquiry(job_number='5', client=sleepy, contact=c_sleepy)
        self.make_enquiry(job_number='6', client=sleepy, contact=c_sleepy)

        migration.sync_existing(apps, None)

        self.assertEqual(self.referrals('Mixed Ltd'), {'recommendation'})  # earliest wins
        self.assertEqual(self.referrals('Plain Ltd'), {None})
        statuses = dict(Client.objects.values_list('name', 'client_status'))
        self.assertEqual((statuses['Mixed Ltd'], statuses['Plain Ltd'], statuses['Sleepy Ltd']),
                         ('current', 'new', 'dormant'))
