from django import forms
from .models import InvoicedJob
from monthly_awards.models import MonthlyAward


class InvoicedJobForm(forms.ModelForm):
    """Form for creating/editing invoiced jobs with better award selection"""

    # Add a search field for award selection
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
        fields = ['award', 'description', 'date', 'utility_value',
                  'cad_value', 'topo_value', 'contractor_value', 'status']
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
            'utility_value': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter utility value',
                'step': '0.01',
                'min': '0'
            }),
            'cad_value': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter CAD value',
                'step': '0.01',
                'min': '0'
            }),
            'topo_value': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter Topo value',
                'step': '0.01',
                'min': '0'
            }),
            'contractor_value': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': 'Enter contractor value',
                'step': '0.01',
                'min': '0'
            }),
            'status': forms.Select(attrs={
                'class': 'form-input'
            }),
        }
        labels = {
            'award': 'Monthly Award',
            'description': 'Description',
            'date': 'Projected Invoice Date',
            'utility_value': 'Utility Value (£)',
            'cad_value': 'CAD Value (£)',
            'topo_value': 'Topo Value (£)',
            'contractor_value': 'Contractor Value (£)',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show awards with better formatting
        awards = MonthlyAward.objects.all().order_by('-date')

        # Create choice list with formatted options
        choices = [('', '-- Select a monthly award --')]
        for award in awards:
            label = f"#{award.job_number} - {award.client} | £{award.value:,.2f} | {award.date.strftime('%d/%m/%Y')}"
            choices.append((award.id, label))

        self.fields['award'].choices = choices


class QuickInvoiceForm(forms.ModelForm):
    """Simplified form for quickly adding invoice data to an award"""

    class Meta:
        model = InvoicedJob
        fields = ['description', 'date', 'utility_value', 'cad_value',
                  'topo_value', 'contractor_value', 'status']
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
            'utility_value': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'cad_value': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'topo_value': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'contractor_value': forms.NumberInput(attrs={
                'class': 'form-input',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'status': forms.Select(attrs={
                'class': 'form-input'
            }),
        }
        labels = {
            'description': 'Description',
            'date': 'Projected Invoice Date',
            'utility_value': 'Utility Value (£)',
            'cad_value': 'CAD Value (£)',
            'topo_value': 'Topo Value (£)',
            'contractor_value': 'Contractor Value (£)',
        }