from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('monthly_awards', '0004_monthlyaward_add_client_ref'),
        ('sales_tracker', '0013_data_migration_clients'),
        ('clients', '0001_initial'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='monthlyaward',
            name='client',
        ),
        migrations.RemoveField(
            model_name='monthlyaward',
            name='client_contact',
        ),
        migrations.RemoveField(
            model_name='monthlyaward',
            name='email',
        ),
        migrations.RemoveField(
            model_name='monthlyaward',
            name='phone',
        ),
        migrations.RenameField(
            model_name='monthlyaward',
            old_name='client_ref',
            new_name='client',
        ),
    ]
