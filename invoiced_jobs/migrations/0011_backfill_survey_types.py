"""Give existing awarded jobs survey types from their invoice values.

Before survey types existed, the only record of which departments worked on a
job was the invoice value split. For each award, every department with a
non-zero value on any of its invoices becomes one of its survey types, and a
sales enquiry gets the survey types of its awards. Existing CAD values were
renamed to MBS in 0010, so CAD jobs come out as MBS.

Only adds codes (never removes), so it is safe to re-run, and a no-op on a
fresh DB. Enquiries that were never awarded keep an empty list: there is no
data to infer them from. The reverse is a no-op.
"""
from django.db import migrations

# Frozen copy of sales_tracker/survey_types.py at the time of this migration.
FIELD_TO_CODE = [
    ('utility_value', 'utility'),
    ('mbs_value', 'mbs'),
    ('topo_value', 'topo'),
    ('contractor_value', 'contractor'),
    ('watercourse_value', 'watercourse'),
    ('cctv_drainage_value', 'cctv_drainage'),
    ('modelling_3d_value', 'modelling_3d'),
    ('drone_value', 'drone'),
    ('engineering_value', 'engineering'),
]
ORDER = {code: i for i, (_, code) in enumerate(FIELD_TO_CODE)}


def _ordered(codes):
    return sorted({c for c in codes if c in ORDER}, key=ORDER.__getitem__)


def backfill(apps, schema_editor):
    InvoicedJob = apps.get_model('invoiced_jobs', 'InvoicedJob')
    MonthlyAward = apps.get_model('monthly_awards', 'MonthlyAward')
    SalesEnquiry = apps.get_model('sales_tracker', 'SalesEnquiry')

    codes_by_award = {}
    fields = [f for f, _ in FIELD_TO_CODE]
    for row in InvoicedJob.objects.values('award_id', *fields):
        codes = codes_by_award.setdefault(row['award_id'], set())
        codes.update(code for field, code in FIELD_TO_CODE if row[field])

    codes_by_sale = {}
    for award in MonthlyAward.objects.all():
        merged = _ordered(set(award.survey_types or []) | codes_by_award.get(award.pk, set()))
        if merged != (award.survey_types or []):
            MonthlyAward.objects.filter(pk=award.pk).update(survey_types=merged)
        if award.sale_id:
            codes_by_sale.setdefault(award.sale_id, set()).update(merged)

    for sale in SalesEnquiry.objects.filter(pk__in=codes_by_sale.keys()):
        merged = _ordered(set(sale.survey_types or []) | codes_by_sale[sale.pk])
        if merged != (sale.survey_types or []):
            # .update() leaves updated_at alone, so no live-refresh storm
            SalesEnquiry.objects.filter(pk=sale.pk).update(survey_types=merged)


class Migration(migrations.Migration):

    dependencies = [
        ('invoiced_jobs', '0010_cad_to_mbs_and_new_departments'),
        ('monthly_awards', '0007_survey_types'),
        ('sales_tracker', '0019_survey_types'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
