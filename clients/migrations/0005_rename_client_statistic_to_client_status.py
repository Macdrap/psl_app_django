from django.db import migrations


class Migration(migrations.Migration):
    """
    Renames the DB column from client_statistic to client_status using raw SQL,
    bypassing Django's state machinery entirely (the state is already correct
    because migration 0004 was edited after it was applied).
    """

    dependencies = [
        ('clients', '0004_client_sector_statistic'),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE clients_client RENAME COLUMN client_statistic TO client_status;",
            reverse_sql="ALTER TABLE clients_client RENAME COLUMN client_status TO client_statistic;",
        ),
    ]
