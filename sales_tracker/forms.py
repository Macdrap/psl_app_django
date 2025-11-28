from django import forms
from .models import SalesEnquiry
from django.db.models import FloatField
from django.db.models.functions import Cast

class SalesEnquiryAddForm(forms.ModelForm):
    """Form for adding new enquiries - excludes date, value, and status"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email and phone not required
        self.fields['email'].required = False
        self.fields['phone'].required = False
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
        fields = ['job_number', 'location', 'client', 'client_contact', 'email', 'phone', 'note']
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
            'client': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter company name'
            }),
            'client_contact': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter contact name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter email address (optional)'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter phone number (optional)'
            }),
        }
        labels = {
            'client': 'Company Name',
            'client_contact': 'Contact Name',
        }


class SalesEnquiryEditForm(forms.ModelForm):
    """Form for editing enquiries - includes all fields"""

    class Meta:
        model = SalesEnquiry
        fields = ['job_number', 'date', 'value', 'location', 'client',
                  'client_contact', 'email', 'phone', 'status', 'note']
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
            'location': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter location',
                'rows': 1
            }),
            'client': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter company name'
            }),
            'client_contact': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter contact name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter email address (optional)'
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter phone number (optional)'
            }),
            'status': forms.Select(attrs={
                'class': 'form-input'
            }),
        }
        labels = {
            'client': 'Company Name',
            'client_contact': 'Contact Name',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email and phone not required
        self.fields['email'].required = False
        self.fields['phone'].required = False
        self.fields['note'].required = False