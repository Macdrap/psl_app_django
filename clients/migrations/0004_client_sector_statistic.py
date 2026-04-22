from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0003_restructure_contacts'),
    ]

    operations = [
        migrations.AddField(
            model_name='client',
            name='sector',
            field=models.CharField(
                choices=[
                    ('architects', 'Architects'),
                    ('local_authority', 'Local Authority'),
                    ('consulting_engineer', 'Consulting Engineer'),
                    ('construction', 'Construction'),
                    ('government_agency', 'Government Agency'),
                    ('retail', 'Retail'),
                    ('other', 'Other'),
                ],
                default='other',
                max_length=50,
            ),
        ),
        migrations.AddField(
            model_name='client',
            name='client_status',
            field=models.CharField(
                choices=[
                    ('current', 'Current'),
                    ('new', 'New'),
                    ('dormant', 'Dormant'),
                ],
                default='current',
                max_length=20,
            ),
        ),
    ]
