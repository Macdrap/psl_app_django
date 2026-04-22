from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    """
    Adds nullable client_ref and contact_ref FKs to SalesEnquiry so the
    data migration (0013) can populate them before the old char fields are removed.
    """

    dependencies = [
        ('sales_tracker', '0011_salesenquiry_other_feedback_and_more'),
        ('clients', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesenquiry',
            name='client_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='sales_enquiries',
                to='clients.client',
            ),
        ),
        migrations.AddField(
            model_name='salesenquiry',
            name='contact_ref',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='sales_enquiries',
                to='clients.contact',
            ),
        ),
    ]
