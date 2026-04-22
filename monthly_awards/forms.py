from django import forms
from .models import MonthlyAward
from sales_tracker.models import SalesEnquiry
from clients.models import SECTOR_CHOICES, CLIENT_STATUS_CHOICES


class MonthlyAwardForm(forms.ModelForm):
    """Form for creating/editing monthly awards"""

    company_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter company name',
        }),
        label='Company Name'
    )
    contact_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter contact name',
        }),
        label='Contact Name'
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter email address (optional)',
        })
    )
    phone = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter phone number (optional)',
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-populate client fields from the FKs on the award itself
        if self.instance and self.instance.pk:
            if self.instance.client_id:
                self.fields['company_name'].initial = self.instance.client.name
            if self.instance.contact_id:
                self.fields['contact_name'].initial = self.instance.contact.name
                self.fields['email'].initial = self.instance.contact.email
                self.fields['phone'].initial = self.instance.contact.phone

    class Meta:
        model = MonthlyAward
        fields = ['job_number', 'date', 'location', 'value']
        widgets = {
            'job_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter job number',
                'id': 'id_job_number'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'location': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter location',
                'rows': 3,
                'id': 'id_location'
            }),
            'value': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter value',
                'step': '0.01',
                'id': 'id_value'
            }),
        }
        labels = {
            'date': 'Date Awarded',
        }
