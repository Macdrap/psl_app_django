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
        # what the browser posts back for the current survey types / split
        'survey_types': list(enquiry.survey_types),
        **{f'value_{code}': str(v) for code, v in enquiry.get_survey_type_values().items()},
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

    SPLIT = {'survey_types': ['utility', 'mbs', 'topo', 'contractor'], 'value_utility': '500',
             'value_mbs': '200', 'value_topo': '300', 'value_contractor': '500'}  # = £1,500

    def award(self, **fields):
        data = edit_payload(self.enquiry, status='Awarded', invoice_date='2026-03-15', **self.SPLIT)
        data.update(fields)
        resp = self.client.post(reverse('edit_sales_enquiry', args=[self.enquiry.pk]), data)
        self.assertEqual(resp.status_code, 302, 'edit form rejected the award POST')
        self.enquiry.refresh_from_db()
        return resp

    def test_awarding_creates_award_and_invoice_from_the_value_by_survey_type(self):
        resp = self.award()
        self.assertEqual(resp.status_code, 302)
        award = MonthlyAward.objects.get(sale=self.enquiry)
        self.assertEqual(award.job_number, '7000')
        self.assertEqual(award.value, Decimal('1500'))
        self.assertEqual(award.client, self.enquiry.client)
        self.assertEqual(award.date, date.today())
        self.assertEqual(award.survey_type_values, self.enquiry.survey_type_values)
        invoice = InvoicedJob.objects.get(award=award)
        self.assertEqual(invoice.date, date(2026, 3, 15))
        self.assertEqual(invoice.status, 'Pending')
        self.assertEqual((invoice.utility_value, invoice.mbs_value, invoice.topo_value, invoice.contractor_value),
                         (Decimal('500'), Decimal('200'), Decimal('300'), Decimal('500')))
        self.assertEqual(invoice.psl_value, Decimal('1000'))  # everything except contractor
        self.assertEqual(invoice.follow_up_status, 'n_a')  # was the invalid "N/A" before
        self.assertFalse(award.has_value_mismatch())

    def test_old_department_fields_in_the_post_are_ignored(self):
        self.award(invoice_utility_value='9999')
        invoice = InvoicedJob.objects.get(award__sale=self.enquiry)
        self.assertEqual(invoice.utility_value, Decimal('500'))

    def test_awarding_needs_a_survey_type(self):
        data = edit_payload(self.enquiry, status='Awarded', survey_types=[], value='1500')
        resp = self.client.post(reverse('edit_sales_enquiry', args=[self.enquiry.pk]), data)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('survey_types', resp.context['form'].errors)
        self.assertFalse(MonthlyAward.objects.exists())

    def test_awarding_with_blank_invoice_date_defaults_to_today(self):
        self.award(invoice_date='')
        invoice = InvoicedJob.objects.get(award__sale=self.enquiry)
        self.assertEqual(invoice.date, date.today())

    def test_editing_awarded_enquiry_syncs_job_details_but_not_values(self):
        self.award()
        data = edit_payload(self.enquiry, job_number='7000.1', location='Hull', value_utility='900')
        self.client.post(reverse('edit_sales_enquiry', args=[self.enquiry.pk]), data)
        self.enquiry.refresh_from_db()
        self.assertEqual(self.enquiry.value, Decimal('1900'))  # the quote changed
        award = MonthlyAward.objects.get(sale=self.enquiry)
        self.assertEqual((award.job_number, award.location), ('7000.1', 'Hull'))
        self.assertEqual(award.value, Decimal('1500'))  # what was awarded is unchanged
        self.assertEqual(award.get_survey_type_values()['utility'], Decimal('500'))
        invoice = award.invoiced_jobs.get()
        self.assertEqual(invoice.utility_value, Decimal('500'))
        self.assertFalse(award.has_value_mismatch())

    def test_edit_page_shows_what_was_awarded(self):
        self.award()
        award = MonthlyAward.objects.get(sale=self.enquiry)
        resp = self.client.get(reverse('edit_sales_enquiry', args=[self.enquiry.pk]))
        self.assertContains(resp, 'Awarded: <strong>£1,500.00</strong>')
        self.assertContains(resp, reverse('edit_monthly_award', args=[award.pk]))

    def test_unchanged_split_leaves_a_hand_edited_invoice_alone(self):
        self.award()
        invoice = InvoicedJob.objects.get(award__sale=self.enquiry)
        invoice.utility_value = Decimal('250')  # e.g. part-invoiced on Invoiced Jobs
        invoice.save()
        self.client.post(reverse('edit_sales_enquiry', args=[self.enquiry.pk]),
                         edit_payload(self.enquiry, note='called client'))
        invoice.refresh_from_db()
        self.assertEqual(invoice.utility_value, Decimal('250'))


    def test_invoice_date_can_be_changed_while_awarded(self):
        self.award()
        self.client.post(reverse('edit_sales_enquiry', args=[self.enquiry.pk]),
                         edit_payload(self.enquiry, invoice_date='2026-06-30'))
        self.assertEqual(InvoicedJob.objects.get(award__sale=self.enquiry).date, date(2026, 6, 30))

    def test_edit_page_has_no_second_allocation_in_the_award_modal(self):
        self.award()
        resp = self.client.get(reverse('edit_sales_enquiry', args=[self.enquiry.pk]))
        self.assertNotContains(resp, 'Department Value Allocation')
        self.assertNotContains(resp, 'name="invoice_utility_value"')
        self.assertContains(resp, 'name="invoice_date"')
        self.assertContains(resp, 'name="value_utility"')

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


class SurveyTypeTests(LoggedInTestCase):
    """Survey types (departments): chosen on any enquiry, synced to its award."""

    def setUp(self):
        super().setUp()
        self.enquiry = self.make_enquiry(job_number='9100', value='1000')

    def post_edit(self, **overrides):
        data = edit_payload(self.enquiry, **overrides)
        resp = self.client.post(reverse('edit_sales_enquiry', args=[self.enquiry.pk]), data)
        self.assertEqual(resp.status_code, 302, 'edit form rejected the POST')
        self.enquiry.refresh_from_db()
        return resp

    def test_add_saves_several_survey_types_in_display_order(self):
        self.client.post(reverse('add_sales_enquiry'), {
            'job_number': '9200', 'location': 'York', 'company_name': 'Acme Ltd',
            'contact_name': 'John Doe', 'survey_types': ['drone', 'mbs', 'utility'],
        })
        self.assertEqual(SalesEnquiry.objects.get(job_number='9200').survey_types,
                         ['utility', 'mbs', 'drone'])

    def test_survey_types_are_optional(self):
        self.client.post(reverse('add_sales_enquiry'), {
            'job_number': '9201', 'location': 'York', 'company_name': 'Acme Ltd', 'contact_name': 'John Doe',
        })
        self.assertEqual(SalesEnquiry.objects.get(job_number='9201').survey_types, [])

    def test_unknown_survey_type_is_rejected(self):
        resp = self.client.post(reverse('edit_sales_enquiry', args=[self.enquiry.pk]),
                                edit_payload(self.enquiry, survey_types=['cad']))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('survey_types', resp.context['form'].errors)

    def test_edit_sets_survey_types_without_awarding(self):
        self.post_edit(survey_types=['watercourse', 'cctv_drainage'])
        self.assertEqual(self.enquiry.survey_types, ['watercourse', 'cctv_drainage'])
        self.assertEqual(self.enquiry.status, 'Pending')
        self.assertFalse(MonthlyAward.objects.exists())

    def test_awarding_puts_every_survey_type_value_on_the_invoice(self):
        values = {'utility': '0', 'mbs': '300', 'topo': '0', 'contractor': '100', 'watercourse': '50',
                  'cctv_drainage': '50', 'modelling_3d': '100', 'drone': '150', 'engineering': '250'}
        self.post_edit(status='Awarded', survey_types=list(values), invoice_date='2026-04-01',
                       **{f'value_{c}': v for c, v in values.items()})
        self.assertEqual(self.enquiry.value, Decimal('1000'))
        award = MonthlyAward.objects.get(sale=self.enquiry)
        invoice = award.invoiced_jobs.get()
        self.assertEqual(
            [invoice.mbs_value, invoice.watercourse_value, invoice.cctv_drainage_value,
             invoice.modelling_3d_value, invoice.drone_value, invoice.engineering_value],
            [Decimal(v) for v in ('300', '50', '50', '100', '150', '250')])
        self.assertEqual(invoice.psl_value, Decimal('900'))  # everything except contractor
        self.assertFalse(award.has_value_mismatch())
        self.assertEqual(award.survey_types, list(values))

    def test_editing_awarded_enquiry_leaves_award_survey_types(self):
        self.post_edit(status='Awarded', survey_types=['topo'], invoice_date='2026-04-01', value_topo='1000')
        self.post_edit(survey_types=['topo', 'drone'], value_topo='1000', value_drone='0')
        self.assertEqual(self.enquiry.survey_types, ['topo', 'drone'])
        self.assertEqual(MonthlyAward.objects.get(sale=self.enquiry).survey_types, ['topo'])

    def test_edit_page_shows_a_value_input_per_survey_type(self):
        resp = self.client.get(reverse('edit_sales_enquiry', args=[self.enquiry.pk]))
        from sales_tracker.survey_types import SURVEY_TYPES
        for code, _, _, _ in SURVEY_TYPES:
            self.assertContains(resp, f'name="value_{code}"')
            self.assertContains(resp, f'value="{code}"')  # survey type checkbox
        self.assertNotContains(resp, 'CAD')

    def test_list_and_live_refresh_show_survey_type_badges(self):
        self.enquiry.survey_types = ['mbs', 'cctv_drainage']
        self.enquiry.save()
        page = self.client.get(reverse('sales_tracker'))
        self.assertContains(page, '<th>Survey Type</th>', html=True)
        self.assertContains(page, 'data-survey-type="mbs"')
        self.assertContains(page, 'CCTV Drainage')
        poll = self.client.get(reverse('sales_tracker_poll'), {'last_count': '0'}).json()['table_html']
        self.assertIn('data-survey-type="cctv_drainage"', poll)

    def test_ordered_drops_unknown_codes_and_duplicates(self):
        from sales_tracker.survey_types import ordered
        self.assertEqual(ordered(['topo', 'cad', 'utility', 'topo']), ['utility', 'topo'])


class SurveyTypeValueTests(LoggedInTestCase):
    """Edit form: a value per ticked survey type; the total is their sum."""

    def setUp(self):
        super().setUp()
        self.enquiry = self.make_enquiry(job_number='9300', value='0')

    def post(self, **overrides):
        resp = self.client.post(reverse('edit_sales_enquiry', args=[self.enquiry.pk]),
                                edit_payload(self.enquiry, **overrides))
        self.enquiry.refresh_from_db()
        return resp

    def test_total_is_the_sum_of_the_ticked_survey_type_values(self):
        resp = self.post(survey_types=['mbs', 'topo'], value_mbs='600', value_topo='400.50',
                         value_drone='999', value='5')  # unticked type and typed total are ignored
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(self.enquiry.value, Decimal('1000.50'))
        self.assertEqual(self.enquiry.get_survey_type_values(),
                         {'mbs': Decimal('600'), 'topo': Decimal('400.50')})

    def test_blank_survey_type_value_counts_as_zero(self):
        self.post(survey_types=['mbs', 'topo'], value_mbs='250', value_topo='')
        self.assertEqual(self.enquiry.value, Decimal('250'))
        self.assertEqual(self.enquiry.get_survey_type_values()['topo'], Decimal('0'))

    def test_without_survey_types_the_total_is_typed_in_as_before(self):
        self.enquiry.survey_types = ['mbs']
        self.enquiry.survey_type_values = {'mbs': '100'}
        self.enquiry.save()
        self.post(survey_types=[], value='750')
        self.assertEqual(self.enquiry.value, Decimal('750'))
        self.assertEqual(self.enquiry.survey_type_values, {})

    def test_without_survey_types_a_value_is_required(self):
        resp = self.post(survey_types=[], value='')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('value', resp.context['form'].errors)

    def test_negative_survey_type_value_is_rejected(self):
        resp = self.post(survey_types=['mbs'], value_mbs='-5')
        self.assertEqual(resp.status_code, 200)
        self.assertIn('value_mbs', resp.context['form'].errors)

    def test_edit_form_shows_stored_split(self):
        self.enquiry.survey_types = ['utility', 'drone']
        self.enquiry.survey_type_values = {'utility': '300.00', 'drone': '200.00'}
        self.enquiry.value = Decimal('500')
        self.enquiry.save()
        form = self.client.get(reverse('edit_sales_enquiry', args=[self.enquiry.pk])).context['form']
        self.assertEqual(form['value_utility'].value(), Decimal('300.00'))
        self.assertEqual(form['value_drone'].value(), Decimal('200.00'))
        self.assertIsNone(form['value_mbs'].value())
        self.assertEqual(form.fields['value'].label, 'Total Value (£)')

    def test_never_split_value_shows_under_first_type_so_saving_keeps_the_total(self):
        self.enquiry.survey_types = ['mbs', 'topo']
        self.enquiry.value = Decimal('800')
        self.enquiry.save()
        resp = self.client.get(reverse('edit_sales_enquiry', args=[self.enquiry.pk]))
        form = resp.context['form']
        self.assertEqual(form['value_mbs'].value(), Decimal('800'))
        self.assertIsNone(form['value_topo'].value())
        self.post(survey_types=['mbs', 'topo'], value_mbs='800', value_topo='')
        self.assertEqual(self.enquiry.value, Decimal('800'))

    def test_awarding_uses_the_split_total_as_award_value(self):
        self.post(status='Awarded', survey_types=['mbs', 'topo'], value_mbs='600', value_topo='400',
                  invoice_date='2026-04-01')
        award = MonthlyAward.objects.get(sale=self.enquiry)
        self.assertEqual(award.value, Decimal('1000'))
        invoice = award.invoiced_jobs.get()
        self.assertEqual((invoice.mbs_value, invoice.topo_value), (Decimal('600'), Decimal('400')))
        self.assertFalse(award.has_value_mismatch())

    def test_list_value_tooltip_shows_the_split(self):
        self.enquiry.survey_types = ['mbs', 'topo']
        self.enquiry.survey_type_values = {'mbs': '600', 'topo': '400'}
        self.enquiry.save()
        resp = self.client.get(reverse('sales_tracker'))
        self.assertContains(resp, 'title="MBS £600.00, Topo £400.00"')

    def test_migration_0021_splits_existing_values_where_known(self):
        import importlib
        from django.apps import apps
        migration = importlib.import_module('sales_tracker.migrations.0021_backfill_survey_type_values')
        single = self.make_enquiry(job_number='a', value='500', survey_types=['topo'])
        matched = self.make_enquiry(job_number='b', value='1000', status='Awarded', survey_types=['mbs', 'topo'])
        award = self.make_award(sale=matched, value='1000')
        self.make_invoice(award, mbs='700')
        self.make_invoice(award, topo='300')
        unmatched = self.make_enquiry(job_number='c', value='900', status='Awarded', survey_types=['mbs', 'topo'])
        self.make_invoice(self.make_award(sale=unmatched, value='900'), mbs='100')
        no_invoice = self.make_enquiry(job_number='d', value='400', survey_types=['utility', 'drone'])
        kept = self.make_enquiry(job_number='e', value='50', survey_types=['mbs'],
                                 survey_type_values={'mbs': '50.00'})
        SalesEnquiry.objects.filter(pk=matched.pk).update(survey_types=['mbs', 'topo'])

        migration.backfill(apps, None)
        migration.backfill(apps, None)  # re-runnable
        for e in (single, matched, unmatched, no_invoice, kept):
            e.refresh_from_db()
        self.assertEqual(single.survey_type_values, {'topo': '500.00'})
        self.assertEqual(matched.survey_type_values, {'mbs': '700.00', 'topo': '300.00'})
        self.assertEqual(unmatched.survey_type_values, {})
        self.assertEqual(no_invoice.survey_type_values, {})
        self.assertEqual(kept.survey_type_values, {'mbs': '50.00'})
