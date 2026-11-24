"""Split existing enquiry values between their survey types where it is known.

- One survey type: the whole value belongs to it.
- Several survey types: use the department split of the job's invoices, but
  only when those invoice values add up exactly to the enquiry value.
- Anything else is left unsplit ({}); the edit form shows the whole value
  under the first survey type until someone splits it.

Never overwrites a split that already exists; no-op on a fresh DB; re-runnable.
The reverse is a no-op.
"""
from decimal import Decimal

from django.db import migrations

# Frozen copy of sales_tracker/survey_types.py at the time of this migration.
FIELD_BY_CODE = {
    'utility': 'utility_value', 'mbs': 'mbs_value', 'topo': 'topo_value',
    'contractor': 'contractor_value', 'watercourse': 'watercourse_value',
    'cctv_drainage': 'cctv_drainage_value', 'modelling_3d': 'modelling_3d_value',
    'drone': 'drone_value', 'engineering': 'engineering_value',
}


def backfill(apps, schema_editor):
    SalesEnquiry = apps.get_model('sales_tracker', 'SalesEnquiry')
    InvoicedJob = apps.get_model('invoiced_jobs', 'InvoicedJob')

    for enquiry in SalesEnquiry.objects.exclude(survey_types=[]).filter(survey_type_values={}):
        codes = [c for c in enquiry.survey_types if c in FIELD_BY_CODE]
        value = enquiry.value or Decimal('0')
        split = None
        if len(codes) == 1:
            split = {codes[0]: value}
        elif codes and value:
            totals = {c: Decimal('0') for c in codes}
            other = Decimal('0')
            for row in InvoicedJob.objects.filter(award__sale=enquiry).values(*FIELD_BY_CODE.values()):
                for code, field in FIELD_BY_CODE.items():
                    if code in totals:
                        totals[code] += row[field] or 0
                    else:
                        other += row[field] or 0
            if not other and sum(totals.values()) == value:
                split = totals
        if split is not None:
            SalesEnquiry.objects.filter(pk=enquiry.pk).update(
                survey_type_values={c: str(v.quantize(Decimal('0.01'))) for c, v in split.items()})


class Migration(migrations.Migration):

    dependencies = [
        ('sales_tracker', '0020_survey_type_values'),
        ('invoiced_jobs', '0011_backfill_survey_types'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
