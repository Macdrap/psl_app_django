"""Shared helpers for the test suite.

Run everything with:  python manage.py test
Tests run against a throwaway Postgres database (test_<DB_NAME>) that Django
creates and drops automatically - your real data is never touched.
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings

from clients.models import Client, Contact
from invoiced_jobs.models import InvoicedJob
from monthly_awards.models import MonthlyAward
from sales_tracker.models import SalesEnquiry


@override_settings(SECURE_SSL_REDIRECT=False)
class LoggedInTestCase(TestCase):
    """TestCase with a logged-in user and small factory helpers."""

    def setUp(self):
        self.user = User.objects.create_user('tester')
        self.client.force_login(self.user)

    # ---- factories -------------------------------------------------------

    @staticmethod
    def make_client(name='Acme Ltd', **kwargs):
        return Client.objects.create(name=name, **kwargs)

    @staticmethod
    def make_contact(client, name='John Doe', **kwargs):
        return Contact.objects.create(client=client, name=name, **kwargs)

    def make_enquiry(self, job_number='1000', value='0', status='Pending', client=None, contact=None, **kwargs):
        client = client or Client.objects.get_or_create(name='Acme Ltd')[0]
        contact = contact or Contact.objects.get_or_create(client=client, name='John Doe')[0]
        return SalesEnquiry.objects.create(
            job_number=job_number, value=Decimal(value), status=status,
            location=kwargs.pop('location', 'Leeds'), client=client, contact=contact,
            created_by=self.user, **kwargs,
        )

    def make_award(self, sale=None, job_number='1000', value='1000', award_date=None, client=None, **kwargs):
        client = client or (sale.client if sale else Client.objects.get_or_create(name='Acme Ltd')[0])
        return MonthlyAward.objects.create(
            sale=sale, job_number=job_number, value=Decimal(value),
            location=kwargs.pop('location', 'Leeds'), client=client,
            date=award_date or date.today(), created_by=self.user, **kwargs,
        )

    def make_invoice(self, award, utility='0', cad='0', topo='0', contractor='0',
                     status='Pending', invoice_date=None, **kwargs):
        return InvoicedJob.objects.create(
            award=award, utility_value=Decimal(utility), cad_value=Decimal(cad),
            topo_value=Decimal(topo), contractor_value=Decimal(contractor),
            status=status, date=invoice_date or date.today(), created_by=self.user, **kwargs,
        )

    @staticmethod
    def messages_of(response):
        return [str(m) for m in get_messages(response.wsgi_request)]
