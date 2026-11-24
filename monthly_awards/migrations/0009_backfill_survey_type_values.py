"""Give awards the same value-by-survey-type as their sales enquiry.

- Award linked to a sale: copy the sale's split, but only when the award has
  the same value and survey types (they are kept in sync, so this is the norm).
- Manual award (or a linked one that differs): one survey type -> the whole
  value; several -> its invoices' department split if that adds up exactly.
- Otherwise left unsplit ({}).

Never overwrites an existing split; no-op on a fresh DB; re-runnable.
The reverse is a no-op.
"""
from decimal import Decimal

from django.db import migrations

FIELD_BY_CODE = {
    'utility': 'utility_value', 'mbs': 'mbs_value', 'topo': 'topo_value',
    'contractor': 'contractor_value', 'watercourse': 'watercourse_value',
    'cctv_drainage': 'cctv_drainage_value', 'modelling_3d': 'modelling_3d_value',
    'drone': 'drone_value', 'engineering': 'engineering_value',
}
CENTS = Decimal('0.01')


def _from_invoices(InvoicedJob, award, codes):
    totals = {c: Decimal('0') for c in codes}
    other = Decimal('0')
    for row in InvoicedJob.objects.filter(award=award).values(*FIELD_BY_CODE.values()):
        for code, field in FIELD_BY_CODE.items():
            if code in totals:
                totals[code] += row[field] or 0
            else:
                other += row[field] or 0
    if not other and sum(totals.values()) == (award.value or 0):
        return totals
    return None


def backfill(apps, schema_editor):
    MonthlyAward = apps.get_model('monthly_awards', 'MonthlyAward')
    InvoicedJob = apps.get_model('invoiced_jobs', 'InvoicedJob')

    for award in MonthlyAward.objects.exclude(survey_types=[]).filter(survey_type_values={}).select_related('sale'):
        codes = [c for c in award.survey_types if c in FIELD_BY_CODE]
        sale = award.sale
        split = None
        if (sale is not None and sale.survey_type_values and sale.value == award.value
                and list(sale.survey_types) == list(award.survey_types)):
            split = {c: Decimal(str(sale.survey_type_values.get(c) or '0')) for c in codes}
        elif len(codes) == 1:
            split = {codes[0]: award.value or Decimal('0')}
        elif codes and award.value:
            split = _from_invoices(InvoicedJob, award, codes)
        if split is not None:
            MonthlyAward.objects.filter(pk=award.pk).update(
                survey_type_values={c: str(v.quantize(CENTS)) for c, v in split.items()})


class Migration(migrations.Migration):

    dependencies = [
        ('monthly_awards', '0008_survey_type_values'),
        ('sales_tracker', '0021_backfill_survey_type_values'),
        ('invoiced_jobs', '0011_backfill_survey_types'),
    ]

    operations = [
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
