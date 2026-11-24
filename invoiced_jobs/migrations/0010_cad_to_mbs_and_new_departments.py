"""CAD department renamed to MBS, and five new departments.

RenameField renames the column in place (ALTER TABLE ... RENAME COLUMN), so
every existing CAD value is kept and is now the MBS value. The new value
columns default to 0, so existing totals and PSL values are unchanged.
"""
from django.db import migrations, models


NEW_DEPARTMENT_FIELDS = [
    'watercourse_value', 'cctv_drainage_value', 'modelling_3d_value',
    'drone_value', 'engineering_value',
]


class Migration(migrations.Migration):

    dependencies = [
        ('invoiced_jobs', '0009_fix_follow_up_status_default'),
    ]

    operations = [
        migrations.RenameField(
            model_name='invoicedjob',
            old_name='cad_value',
            new_name='mbs_value',
        ),
    ] + [
        migrations.AddField(
            model_name='invoicedjob',
            name=name,
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        )
        for name in NEW_DEPARTMENT_FIELDS
    ]
