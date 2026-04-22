from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sales_tracker', '0015_salesenquiry_add_contact_fk'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesenquiry',
            name='referral',
            field=models.CharField(
                blank=True,
                null=True,
                max_length=20,
                choices=[
                    ('google', 'Google'),
                    ('recommendation', 'Recommendation'),
                    ('other', 'Other'),
                ],
            ),
        ),
    ]
