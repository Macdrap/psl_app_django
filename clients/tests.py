"""Regression tests for Clients and Contacts."""
from django.urls import reverse

from clients.models import Client
from psl_app_project.test_utils import LoggedInTestCase


class ClientListTests(LoggedInTestCase):
    def test_counts_are_not_inflated_by_joins(self):
        client = self.make_client('Acme Ltd')
        a = self.make_contact(client, 'A')
        self.make_contact(client, 'B')
        for jn in ('1', '2', '3'):
            self.make_enquiry(job_number=jn, client=client, contact=a)
        self.make_award(client=client)
        resp = self.client.get(reverse('clients_list'))
        self.assertEqual(resp.status_code, 200)
        row = resp.context['page_obj'][0]
        self.assertEqual((row.contact_count, row.enquiry_count, row.award_count), (2, 3, 1))

    def test_quoted_value_badge_counts_priced_quotes_only(self):
        client = self.make_client('Acme Ltd')
        self.make_enquiry(job_number='1', value='1000', status='Awarded', client=client)
        self.make_enquiry(job_number='2', value='250', status='Pending', client=client)
        self.make_enquiry(job_number='3', value='0', status='Pending', client=client)
        self.make_enquiry(job_number='4', value='800', status='Not_Quoted', client=client)
        self.make_client('No Quotes Ltd')
        resp = self.client.get(reverse('clients_list'))
        rows = {c.name: c for c in resp.context['page_obj']}
        self.assertEqual(rows['Acme Ltd'].quoted_value, 1250)
        self.assertIsNone(rows['No Quotes Ltd'].quoted_value)
        self.assertContains(resp, '£1,250 quoted')
        self.assertContains(resp, '?client=Acme%20Ltd#client-analysis-section')

    def test_search_by_contact_email(self):
        self.make_contact(self.make_client('Acme'), 'A', email='finder@example.com')
        self.make_client('Other')
        resp = self.client.get(reverse('clients_list'), {'search': 'finder@'})
        self.assertEqual([c.name for c in resp.context['page_obj']], ['Acme'])

    def test_per_page_only_allows_50_100_200(self):
        for value, expected in (('50', 50), ('200', 200), ('75', 100), ('x', 100)):
            resp = self.client.get(reverse('clients_list'), {'per_page': value})
            self.assertEqual(resp.context['per_page'], expected, value)


class ClientCrudTests(LoggedInTestCase):
    def test_add_client(self):
        self.client.post(reverse('client_add'), {
            'company_name': 'Flood Co', 'sector': 'flood_consultancy', 'client_status': 'new'})
        self.assertEqual(Client.objects.get().sector, 'flood_consultancy')

    def test_duplicate_client_name_rejected(self):
        self.make_client('Acme Ltd')
        resp = self.client.post(reverse('client_add'), {
            'company_name': ' Acme Ltd ', 'sector': 'other', 'client_status': 'current'})
        self.assertEqual(resp.status_code, 200)  # form re-rendered with error
        self.assertEqual(Client.objects.count(), 1)

    def test_client_with_enquiries_cannot_be_deleted(self):
        client = self.make_client('Acme Ltd')
        self.make_enquiry(client=client)
        resp = self.client.post(reverse('client_delete', args=[client.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Client.objects.filter(pk=client.pk).exists())
        self.assertIn('1 sales enquiry linked', self.messages_of(resp)[0])

    def test_client_with_only_awards_cannot_be_deleted_and_message_says_why(self):
        # Regression: message used to say "0 linked sales enquiries".
        client = self.make_client('Acme Ltd')
        self.make_award(client=client)
        self.make_award(client=client, job_number='2')
        resp = self.client.post(reverse('client_delete', args=[client.pk]))
        self.assertTrue(Client.objects.filter(pk=client.pk).exists())
        msg = self.messages_of(resp)[0]
        self.assertIn('2 monthly awards', msg)
        self.assertNotIn('enquir', msg)

    def test_unused_client_can_be_deleted(self):
        client = self.make_client('Lonely Ltd')
        self.make_contact(client)
        self.client.post(reverse('client_delete', args=[client.pk]))
        self.assertFalse(Client.objects.exists())

    def test_contact_add_edit_delete(self):
        client = self.make_client()
        self.client.post(reverse('contact_add', args=[client.pk]),
                         {'contact_name': 'Jane', 'email': 'j@example.com', 'phone': ''})
        contact = client.contacts.get()
        self.client.post(reverse('contact_edit', args=[client.pk, contact.pk]),
                         {'contact_name': 'Jane R', 'email': '', 'phone': '1'})
        contact.refresh_from_db()
        self.assertEqual((contact.name, contact.email, contact.phone), ('Jane R', None, '1'))
        self.client.post(reverse('contact_delete', args=[client.pk, contact.pk]))
        self.assertFalse(client.contacts.exists())

    def test_contact_list_page(self):
        # Regression: the template used to be missing (500).
        client = self.make_client('Acme Ltd')
        self.make_contact(client, 'Zed Smith', email='zed@example.com')
        resp = self.client.get(reverse('contact_list', args=[client.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Zed Smith')
        self.assertContains(resp, 'zed@example.com')
        self.assertContains(resp, reverse('contact_add', args=[client.pk]))

    def test_contact_list_page_empty(self):
        resp = self.client.get(reverse('contact_list', args=[self.make_client().pk]))
        self.assertContains(resp, 'no contacts yet')


class ClientApiTests(LoggedInTestCase):
    def test_autocomplete(self):
        client = self.make_client('Acme Ltd')
        self.make_contact(client, 'John', email='j@example.com')
        data = self.client.get(reverse('client_autocomplete'), {'q': 'acm'}).json()
        self.assertEqual(data, [{'id': client.pk, 'name': 'Acme Ltd', 'contact_name': 'John',
                                 'email': 'j@example.com', 'phone': '', 'last_referral': ''}])
        self.assertEqual(self.client.get(reverse('client_autocomplete')).json(), [])

    def test_contacts_api(self):
        client = self.make_client()
        self.make_contact(client, 'B')
        self.make_contact(client, 'A')
        data = self.client.get(reverse('client_contacts_api', args=[client.pk])).json()
        self.assertEqual([c['name'] for c in data], ['A', 'B'])
