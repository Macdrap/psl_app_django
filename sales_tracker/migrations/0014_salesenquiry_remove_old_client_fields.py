from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sales_tracker', '0013_data_migration_clients'),
        ('clients', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='salesenquiry',
            name='client',
        ),
        migrations.RemoveField(
            model_name='salesenquiry',
            name='client_contact',
        ),
        migrations.RemoveField(
            model_name='salesenquiry',
            name='email',
        ),
        migrations.RemoveField(
            model_name='salesenquiry',
            name='phone',
        ),
        migrations.RenameField(
            model_name='salesenquiry',
            old_name='client_ref',
            new_name='client',
        ),
    ]
