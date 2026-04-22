from django.db import migrations


class Migration(migrations.Migration):
    """
    No-op placeholder. The restructure it originally performed is now
    handled directly in clients.0001_initial and clients.0002_client_name_unique.
    """

    dependencies = [
        ('clients', '0002_client_name_unique'),
    ]

    operations = []
