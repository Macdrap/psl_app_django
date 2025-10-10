from django import forms
from .models import SalesEnquiry


class SalesEnquiryAddForm(forms.ModelForm):
    """Form for adding new enquiries - excludes date, value, and status"""

    class Meta:
        model = SalesEnquiry
        fields = ['job_number', 'location', 'client', 'client_contact', 'email', 'phone']
        widgets = {
            'job_number': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter job number'
            }),
            'location': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter location',
                'rows': 3
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make email and phone not required
        self.fields['email'].required = False
        self.fields['phone'].required = False


class SalesEnquiryEditForm(forms.ModelForm):
    """Form for editing enquiries - includes all fields"""

    class Meta:
        model = SalesEnquiry
        fields = ['job_number', 'date', 'value', 'location', 'client',
                  'client_contact', 'email', 'phone', 'status']
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
            'location': forms.Textarea(attrs={
                'class': 'form-input',
                'placeholder': 'Enter location',
                'rows': 3
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