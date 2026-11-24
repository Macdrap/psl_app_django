from decimal import Decimal

from django import forms
from .models import SalesEnquiry
from django.db.models import FloatField
from django.db.models.functions import Cast
from clients.models import SECTOR_CHOICES, CLIENT_STATUS_CHOICES
from .survey_types import SURVEY_TYPES, SURVEY_TYPE_CHOICES, ordered


class SurveyTypesField(forms.MultipleChoiceField):
    """Tick one or more survey types (departments). Optional; saved in display order."""

    def __init__(self, **kwargs):
        kwargs.setdefault('label', 'Survey Type')
        super().__init__(
            choices=SURVEY_TYPE_CHOICES,
            required=False,
            widget=forms.CheckboxSelectMultiple,
            **kwargs,
        )

    def clean(self, value):
        return ordered(super().clean(value))


class SurveyTypeValuesMixin:
    """Value by survey type: one optional £ field per survey type (value_<code>).

    When any survey type is ticked, the form's `value` (the total) is the sum
    of the ticked types' values and the split is stored on the instance's
    `survey_type_values`. With no survey type ticked, `value` is typed in as
    before (only allowed when `allow_unsplit_value` - old records).
    Used by SalesEnquiryEditForm and MonthlyAwardForm.
    """

    def _setup_survey_type_values(self, total_label):
        self.fields['value'].required = False
        self.fields['value'].label = total_label
        instance = self.instance
        split = instance.get_survey_type_values() if instance.pk else {}
        ticked = ordered(instance.survey_types) if instance.pk else []
        if ticked and not split and instance.value:
            # Never split (legacy data): show the whole value under the first type
            split = {ticked[0]: instance.value}
        for code, label, _, color in SURVEY_TYPES:
            self.fields[f'value_{code}'] = forms.DecimalField(
                required=False, min_value=0, max_digits=10, decimal_places=2,
                label=f'{label} (£)', initial=split.get(code),
                widget=forms.NumberInput(attrs={
                    'class': 'form-input survey-type-value', 'step': '0.01', 'min': '0',
                    'placeholder': '0.00', 'data-survey-type': code,
                }),
            )

    def survey_type_value_fields(self):
        """[{code, label, color, field}] for the template, in survey type order."""
        return [{'code': code, 'label': label, 'color': color, 'field': self[f'value_{code}']}
                for code, label, _, color in SURVEY_TYPES]

    def _clean_survey_type_values(self, cleaned, allow_unsplit_value=True):
        codes = cleaned.get('survey_types') or []
        if codes:
            split = {code: cleaned.get(f'value_{code}') or Decimal('0') for code in codes}
            cleaned['value'] = sum(split.values(), Decimal('0'))
            self._errors.pop('value', None)  # the typed total is ignored here
            self.instance.survey_type_values = {
                code: str(v.quantize(Decimal('0.01'))) for code, v in split.items()}
        else:
            if not allow_unsplit_value:
                self.add_error('survey_types', 'Tick at least one survey type and enter its value.')
            elif cleaned.get('value') is None and 'value' not in self.errors:
                self.add_error('value', 'Enter a value, or tick a survey type and enter its value.')
            self.instance.survey_type_values = {}
        return cleaned


class SalesEnquiryAddForm(forms.ModelForm):
    """Form for adding new enquiries - excludes date, value, and status"""

    company_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter company name'
        }),
        label='Company Name'
    )
    contact_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter contact name'
        }),
        label='Contact Name'
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter email address (optional)'
        })
    )
    phone = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter phone number (optional)'
        })
    )
    sector = forms.ChoiceField(
        choices=SECTOR_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-input'}),
        label='Sector',
    )
    client_status = forms.ChoiceField(
        choices=CLIENT_STATUS_CHOICES,
        required=False,
        initial='current',
        widget=forms.Select(attrs={'class': 'form-input'}),
        label='Client Status',
    )
    referral = forms.ChoiceField(
        choices=[('', '---------')] + SalesEnquiry.REFERRAL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-input'}),
        label='Referral Source',
    )
    survey_types = SurveyTypesField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get the highest job number from the database
        last_job = SalesEnquiry.objects.annotate(
            job_number_int=Cast('job_number', FloatField())
        ).order_by('-job_number_int').first()

        if last_job:
            self.fields['job_number'].initial = int(float(last_job.job_number) + 1)
        else:
            self.fields['job_number'].initial = "1"

    class Meta:
        model = SalesEnquiry
        fields = ['job_number', 'location', 'survey_types', 'note', 'referral']
        widgets = {
            'job_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter job number'
            }),
            'note': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter notes (optional)',
                'rows': 1
            }),
            'location': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter location',
                'rows': 1
            }),
        }


class SalesEnquiryEditForm(SurveyTypeValuesMixin, forms.ModelForm):
    """Form for editing enquiries - includes all fields"""

    company_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter company name'
        }),
        label='Company Name'
    )
    contact_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter contact name'
        }),
        label='Contact Name'
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter email address (optional)'
        })
    )
    phone = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter phone number (optional)'
        })
    )
    survey_types = SurveyTypesField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['note'].required = False
        self.fields['feedback'].required = False
        # Value is the sum of the survey type values when any type is ticked;
        # typed in directly only when no survey type is ticked (old enquiries).
        self._setup_survey_type_values('Total Value (£)')
        # Pre-populate client fields from the FKs on the enquiry itself
        if self.instance and self.instance.pk:
            if self.instance.client_id:
                self.fields['company_name'].initial = self.instance.client.name
            if self.instance.contact_id:
                self.fields['contact_name'].initial = self.instance.contact.name
                self.fields['email'].initial = self.instance.contact.email
                self.fields['phone'].initial = self.instance.contact.phone

    def clean(self):
        cleaned = super().clean()
        # Awarding needs the value split by survey type: it becomes the award's
        # and the invoice's department values. (self.instance.status is still
        # the saved status here.) Already-awarded old jobs can still be edited.
        newly_awarded = cleaned.get('status') == 'Awarded' and self.instance.status != 'Awarded'
        return self._clean_survey_type_values(cleaned, allow_unsplit_value=not newly_awarded)

    class Meta:
        model = SalesEnquiry
        fields = ['job_number', 'date', 'value', 'location', 'survey_types', 'status', 'note', 'feedback',
                  'other_feedback', 'referral']
        widgets = {
            'job_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter job number'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'value': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter value',
                'step': '0.01'
            }),
            'note': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter notes (optional)',
                'rows': 1
            }),
            'feedback': forms.Select(attrs={
                'class': 'form-input',
                'placeholder': 'Enter feedback (optional)',
            }),
            'other_feedback': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter Other Feedback',
                'rows': 1
            }),
            'location': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter location',
                'rows': 1
            }),
            'status': forms.Select(attrs={
                'class': 'form-input'
            }),
            'referral': forms.Select(attrs={
                'class': 'form-input'
            }),
        }
