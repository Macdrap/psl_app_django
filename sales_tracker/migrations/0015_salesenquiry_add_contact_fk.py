from django.db import migrations


class Migration(migrations.Migration):
    """
    No-op placeholder. The contact FK is now added in 0012 and renamed in 0014,
    so there is nothing left to do here.
    """

    dependencies = [
        ('sales_tracker', '0014_salesenquiry_remove_old_client_fields'),
        ('clients', '0003_restructure_contacts'),
    ]

    operations = []
