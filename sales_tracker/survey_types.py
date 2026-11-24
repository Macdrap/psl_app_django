"""Survey types (departments) — the single list every app uses.

A job (SalesEnquiry, and its MonthlyAward) can have one or more survey types,
stored as a list of codes in `survey_types`. Each survey type also has its own
value column on InvoicedJob (`<field>`), so an invoice can be split between
departments.

Adding a survey type:
  1. add a row below (code, label, InvoicedJob field, colour);
  2. add the matching DecimalField to invoiced_jobs.models.InvoicedJob;
  3. run makemigrations (the choices on SalesEnquiry/MonthlyAward change too).
Tests check every survey type has a colour and an InvoicedJob field.
Never change an existing code: it is stored in the database.
"""

# (code, label, InvoicedJob value field, colour). Order = display order.
SURVEY_TYPES = [
    ('utility',       'Utility',       'utility_value',       '#aa4646'),
    ('mbs',           'MBS',           'mbs_value',           '#9a7b1c'),
    ('topo',          'Topo',          'topo_value',          '#466ea0'),
    ('contractor',    'Contractor',    'contractor_value',    '#4b5563'),
    ('watercourse',   'Watercourse',   'watercourse_value',   '#0369a1'),
    ('cctv_drainage', 'CCTV Drainage', 'cctv_drainage_value', '#6d28d9'),
    ('modelling_3d',  '3D Modelling',  'modelling_3d_value',  '#be185d'),
    ('drone',         'Drone Survey',  'drone_value',         '#0f766e'),
    ('engineering',   'Engineering',   'engineering_value',   '#c2410c'),
]

SURVEY_TYPE_CHOICES = [(code, label) for code, label, _, _ in SURVEY_TYPES]
SURVEY_TYPE_LABELS = dict(SURVEY_TYPE_CHOICES)
SURVEY_TYPE_COLORS = {code: color for code, _, _, color in SURVEY_TYPES}
# InvoicedJob value field per survey type, e.g. 'mbs' -> 'mbs_value'
SURVEY_TYPE_FIELDS = {code: field for code, _, field, _ in SURVEY_TYPES}
DEPARTMENT_VALUE_FIELDS = [field for _, _, field, _ in SURVEY_TYPES]

# The one department whose work is not PSL's own: PSL value = total - contractor.
CONTRACTOR = 'contractor'

_ORDER = {code: i for i, code in enumerate(SURVEY_TYPE_LABELS)}


def ordered(codes):
    """Known codes only, without duplicates, in display order."""
    return sorted({c for c in (codes or []) if c in _ORDER}, key=_ORDER.__getitem__)


def badges(codes):
    """[{'code', 'label', 'color'}] for templates (survey_type_badges.html)."""
    return [{'code': c, 'label': SURVEY_TYPE_LABELS[c], 'color': SURVEY_TYPE_COLORS[c]}
            for c in ordered(codes)]


def split_values(codes, stored):
    """{code: Decimal} value per survey type from a stored {code: "600.00"} split,
    for the given survey types; {} when the value was never split."""
    from decimal import Decimal
    if not stored:
        return {}
    return {code: Decimal(str(stored.get(code) or '0')) for code in ordered(codes)}


def split_breakdown(split):
    """'MBS £600.00, Topo £400.00' from a {code: Decimal} split (£0 types left out)."""
    return ', '.join(f'{SURVEY_TYPE_LABELS[code]} £{v:,.2f}' for code, v in split.items() if v)


def invoice_fields_from_split(split):
    """{InvoicedJob field: Decimal} for every department: the split, 0 elsewhere."""
    from decimal import Decimal
    return {field: split.get(code, Decimal('0')) for code, _, field, _ in SURVEY_TYPES}
