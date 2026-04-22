from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Finalises the Contact model after the data migration has populated all rows:
    - Makes Contact.client non-nullable.
    - Adds unique_together so one company cannot have two contacts with the same name.
    Depends on sales_tracker.0013 (the data migration) so that every Contact
    already has a client set before we enforce NOT NULL.
    """

    dependencies = [
        ('clients', '0001_initial'),
        ('sales_tracker', '0013_data_migration_clients'),
    ]

    operations = [
        migrations.AlterField(
            model_name='contact',
            name='client',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='contacts',
                to='clients.client',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='contact',
            unique_together={('client', 'name')},
        ),
    ]
