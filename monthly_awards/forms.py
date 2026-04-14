from django import forms
from .models import MonthlyAward
from sales_tracker.models import SalesEnquiry


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Pre-populate client fields from existing FK
        if self.instance and self.instance.pk and self.instance.client:
            client = self.instance.client
            self.fields['company_name'].initial = client.name
            self.fields['contact_name'].initial = client.contact.name
            self.fields['email'].initial = client.contact.email
            self.fields['phone'].initial = client.contact.phone

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
