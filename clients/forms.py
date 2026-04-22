from django import forms
from .models import Client, Contact, SECTOR_CHOICES, CLIENT_STATUS_CHOICES


class ClientForm(forms.Form):
    company_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter company name',
            'autocomplete': 'off',
        }),
        label='Company Name',
    )
    sector = forms.ChoiceField(
        choices=SECTOR_CHOICES,
        widget=forms.Select(attrs={'class': 'form-input'}),
        label='Sector',
    )
    client_status = forms.ChoiceField(
        choices=CLIENT_STATUS_CHOICES,
        initial='current',
        widget=forms.Select(attrs={'class': 'form-input'}),
        label='Client Status',
    )

    def __init__(self, *args, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance = instance
        if instance and not args:
            self.fields['company_name'].initial = instance.name
            self.fields['sector'].initial = instance.sector
            self.fields['client_status'].initial = instance.client_status

    def clean_company_name(self):
        name = self.cleaned_data['company_name'].strip()
        qs = Client.objects.filter(name=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError(
                f'A client named "{name}" already exists.'
            )
        return name


class ContactForm(forms.Form):
    contact_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter contact name',
        }),
        label='Contact Name',
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter email address',
        }),
        label='Email',
    )
    phone = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Enter phone number',
        }),
        label='Phone',
    )

    def __init__(self, *args, client=None, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = client
        self.instance = instance
        if instance and not args:
            self.fields['contact_name'].initial = instance.name
            self.fields['email'].initial = instance.email
            self.fields['phone'].initial = instance.phone

    def clean_contact_name(self):
        name = self.cleaned_data['contact_name'].strip()
        if self.client:
            qs = Contact.objects.filter(client=self.client, name=name)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f'A contact named "{name}" already exists for this client.'
                )
        return name
