from django import forms
from .models import SalesEnquiry
from django.db.models import FloatField
from django.db.models.functions import Cast
from clients.models import SECTOR_CHOICES, CLIENT_STATUS_CHOICES


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
        fields = ['job_number', 'location', 'note', 'referral']
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


class SalesEnquiryEditForm(forms.ModelForm):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['note'].required = False
        self.fields['feedback'].required = False
        # Pre-populate client fields from the FKs on the enquiry itself
        if self.instance and self.instance.pk:
            if self.instance.client_id:
                self.fields['company_name'].initial = self.instance.client.name
            if self.instance.contact_id:
                self.fields['contact_name'].initial = self.instance.contact.name
                self.fields['email'].initial = self.instance.contact.email
                self.fields['phone'].initial = self.instance.contact.phone

    class Meta:
        model = SalesEnquiry
        fields = ['job_number', 'date', 'value', 'location', 'status', 'note', 'feedback', 'other_feedback', 'referral']
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
