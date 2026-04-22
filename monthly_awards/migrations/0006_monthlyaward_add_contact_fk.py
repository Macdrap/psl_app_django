from django.db import migrations


class Migration(migrations.Migration):
    """
    No-op placeholder. The contact FK is now added in 0004 and renamed in 0005,
    so there is nothing left to do here.
    """

    dependencies = [
        ('monthly_awards', '0005_monthlyaward_remove_old_client_fields'),
        ('clients', '0003_restructure_contacts'),
    ]

    operations = []
