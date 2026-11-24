from decimal import Decimal

from django import forms
from .models import InvoicedJob
from monthly_awards.models import MonthlyAward
from sales_tracker.survey_types import SURVEY_TYPES, DEPARTMENT_VALUE_FIELDS


def _department_widgets(placeholder=None):
    return {
        field: forms.NumberInput(attrs={
            'class': 'form-input department-value',
            'placeholder': placeholder or f'Enter {label} value',
            'step': '0.01',
            'min': '0',
        })
        for _, label, field, _ in SURVEY_TYPES
    }


DEPARTMENT_LABELS = {field: f'{label} Value (£)' for _, label, field, _ in SURVEY_TYPES}


class DepartmentValuesMixin:
    """Department values are optional: blank means £0."""

    def _make_departments_optional(self):
        for field in DEPARTMENT_VALUE_FIELDS:
            self.fields[field].required = False

    def clean(self):
        cleaned = super().clean()
        for field in DEPARTMENT_VALUE_FIELDS:
            if field in cleaned and cleaned[field] is None:
                cleaned[field] = Decimal('0')
        return cleaned


class InvoicedJobForm(DepartmentValuesMixin, forms.ModelForm):
    """Form for creating/editing invoiced jobs with better award selection"""

    award_search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Search by job number, client, or location...',
            'id': 'award_search'
        }),
        label='Search Award'
    )

    class Meta:
        model = InvoicedJob
        fields = ['award', 'description', 'date', *DEPARTMENT_VALUE_FIELDS,
                  'status', 'follow_up_status', 'followed_up_date']
        widgets = {
            'award': forms.Select(attrs={
                'class': 'form-input',
                'required': True,
                'id': 'award_select'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter description (optional)',
                'rows': 2
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            **_department_widgets(),
            'status': forms.Select(attrs={
                'class': 'form-input'
            }),
            'follow_up_status': forms.Select(attrs={
                'class': 'form-input',

            }),
            'followed_up_date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
        }
        labels = {
            'award': 'Monthly Award',
            'description': 'Description',
            'date': 'Projected Invoice Date',
            **DEPARTMENT_LABELS,
            'follow_up_status': 'Follow-Up Status',
            'followed_up_date': 'Follow-Up Date',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._make_departments_optional()
        # Show awards with better formatting
        awards = MonthlyAward.objects.all().order_by('-date')

        # Create choice list with formatted options
        choices = [('', '-- Select a monthly award --')]
        for award in awards:
            label = f"#{award.job_number} - {award.client} | £{award.value:,.2f} | {award.date.strftime('%d/%m/%Y')}"
            choices.append((award.id, label))

        self.fields['award'].choices = choices

    def department_fields(self):
        """Bound fields of the department values, in survey type order (for templates)."""
        return [self[field] for field in DEPARTMENT_VALUE_FIELDS]


class QuickInvoiceForm(DepartmentValuesMixin, forms.ModelForm):
    """Simplified form for quickly adding invoice data to an award"""

    class Meta:
        model = InvoicedJob
        fields = ['description', 'date', *DEPARTMENT_VALUE_FIELDS, 'status']
        widgets = {
            'description': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter description (optional)',
                'rows': 2
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            **_department_widgets(placeholder='0.00'),
            'status': forms.Select(attrs={
                'class': 'form-input'
            }),
        }
        labels = {
            'description': 'Description',
            'date': 'Projected Invoice Date',
            **DEPARTMENT_LABELS,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._make_departments_optional()
