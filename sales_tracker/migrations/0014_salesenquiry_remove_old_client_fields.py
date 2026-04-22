from django.db import migrations


class Migration(migrations.Migration):
    """
    Removes the four old char fields (client, client_contact, email, phone)
    and renames client_ref → client and contact_ref → contact.
    """

    dependencies = [
        ('sales_tracker', '0013_data_migration_clients'),
        ('clients', '0002_client_name_unique'),
    ]

    operations = [
        migrations.RemoveField(model_name='salesenquiry', name='client'),
        migrations.RemoveField(model_name='salesenquiry', name='client_contact'),
        migrations.RemoveField(model_name='salesenquiry', name='email'),
        migrations.RemoveField(model_name='salesenquiry', name='phone'),
        migrations.RenameField(model_name='salesenquiry', old_name='client_ref', new_name='client'),
        migrations.RenameField(model_name='salesenquiry', old_name='contact_ref', new_name='contact'),
    ]
