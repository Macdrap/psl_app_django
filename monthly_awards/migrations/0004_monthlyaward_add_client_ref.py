from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Adds nullable client_ref and contact_ref FKs to MonthlyAward so the
    data migration (sales_tracker.0013) can populate them before the old
    char fields are removed.
    """

    dependencies = [
        ('monthly_awards', '0003_alter_monthlyaward_created_by'),
        ('clients', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='monthlyaward',
            name='client_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='monthly_awards',
                to='clients.client',
            ),
        ),
        migrations.AddField(
            model_name='monthlyaward',
            name='contact_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='monthly_awards',
                to='clients.contact',
            ),
        ),
    ]
