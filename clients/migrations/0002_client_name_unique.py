from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Add a unique constraint on clients_client.name.
    Depends on the data migration so the table is already deduplicated
    before the constraint is applied.
    """

    dependencies = [
        ('clients', '0001_initial'),
        ('sales_tracker', '0013_data_migration_clients'),
    ]

    operations = [
        migrations.AlterField(
            model_name='client',
            name='name',
            field=models.CharField(max_length=255, unique=True),
        ),
    ]
