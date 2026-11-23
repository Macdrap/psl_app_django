"""Project-wide checks: every page needs login, every page renders, and the
models have no un-generated migrations."""
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from psl_app_project.test_utils import LoggedInTestCase

PAGES = [
    'dashboard', 'sales_tracker', 'add_sales_enquiry', 'monthly_awards_list', 'add_monthly_award',
    'invoiced_jobs_list', 'add_invoiced_job', 'statistic_explorer', 'clients_list', 'client_add',
]


@override_settings(SECURE_SSL_REDIRECT=False)
class LoginRequiredTests(TestCase):
    def test_every_page_redirects_anonymous_users_to_login(self):
        for name in PAGES + ['sales_tracker_poll', 'client_autocomplete', 'statistic_explorer_pdf']:
            resp = self.client.get(reverse(name))
            self.assertEqual(resp.status_code, 302, name)
            self.assertIn(reverse('login'), resp['Location'], name)

    def test_login_page_renders(self):
        self.assertEqual(self.client.get(reverse('login')).status_code, 200)


class SmokeTests(LoggedInTestCase):
    def test_every_page_renders(self):
        award = self.make_award(sale=self.make_enquiry(status='Awarded'))
        self.make_invoice(award)
        for name in PAGES:
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)


class MigrationTests(TestCase):
    def test_no_missing_migrations(self):
        # Fails if a model was changed (including choices) without running makemigrations.
        out = StringIO()
        try:
            call_command('makemigrations', '--check', '--dry-run', stdout=out, stderr=out)
        except SystemExit:
            self.fail(f'Missing migrations - run "python manage.py makemigrations":\n{out.getvalue()}')
