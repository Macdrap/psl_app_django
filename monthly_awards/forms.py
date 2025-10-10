from django import forms
from .models import MonthlyAward
from sales_tracker.models import SalesEnquiry


class MonthlyAwardForm(forms.ModelForm):
    """Form for creating/editing monthly awards"""

    class Meta:
        model = MonthlyAward
        fields = ['job_number', 'date', 'location', 'client',
                  'client_contact', 'email', 'phone', 'value']
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
            'client': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter company name',
                'id': 'id_client'
            }),
            'client_contact': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter contact name',
                'id': 'id_client_contact'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter email address (optional)',
                'id': 'id_email'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter phone number (optional)',
                'id': 'id_phone'
            }),
            'value': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter value',
                'step': '0.01',
                'id': 'id_value'
            }),
        }
        labels = {
            'client': 'Company Name',
            'client_contact': 'Contact Name',
            'date': 'Date Awarded',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email and phone not required
        self.fields['email'].required = False
        self.fields['phone'].required = False