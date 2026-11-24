from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone
from sales_tracker.models import SalesEnquiry
from sales_tracker.survey_types import (
    SURVEY_TYPE_CHOICES, badges, invoice_fields_from_split, ordered, split_breakdown, split_values,
)


class MonthlyAward(models.Model):
    # Foreign key to SalesEnquiry - optional (can be null)
    sale = models.ForeignKey(
        SalesEnquiry,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='monthly_awards'
    )

    # Fields that can be inherited from SalesEnquiry OR entered manually
    job_number = models.CharField(max_length=20)
    location = models.TextField()
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='monthly_awards'
    )
    contact = models.ForeignKey(
        'clients.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='monthly_awards'
    )
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # Survey types (departments) - copied from / to the linked sale
    survey_types = ArrayField(
        models.CharField(max_length=20, choices=SURVEY_TYPE_CHOICES),
        default=list, blank=True,
    )
    # Value per survey type {code: "600.00"}; `value` is their sum when any
    # survey type is ticked. Same as the linked sale's (kept in sync both ways).
    survey_type_values = models.JSONField(default=dict, blank=True)

    # Date awarded
    date = models.DateField(default=timezone.now, help_text="Date the job was awarded")

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='monthly_awards')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Monthly Award'
        verbose_name_plural = 'Monthly Awards'

    def __str__(self):
        client_name = self.client.name if self.client else 'N/A'
        return f"Award: Job #{self.job_number} - {client_name}"

    def survey_type_badges(self):
        return badges(self.survey_types)

    def get_survey_type_values(self):
        """{code: Decimal} value per survey type, or {} if never split."""
        return split_values(self.survey_types, self.survey_type_values)

    def survey_type_value_breakdown(self):
        return split_breakdown(self.get_survey_type_values())

    def apply_split_to_invoice(self):
        """Copy the award's value-by-survey-type onto its invoice.

        Only when the award has exactly ONE invoice: once a job is invoiced in
        stages, each invoice's department values are managed on Invoiced Jobs.
        Returns True if an invoice was updated.
        """
        split = self.get_survey_type_values()
        invoices = list(self.invoiced_jobs.all()[:2])
        if not split or len(invoices) != 1:
            return False
        invoice = invoices[0]
        for field, value in invoice_fields_from_split(split).items():
            setattr(invoice, field, value)
        invoice.save()
        return True

    def add_survey_types(self, codes):
        """Add survey types this award doesn't have yet.

        Used when an invoice puts value against a department: a department with
        invoiced value is always one of the award's survey types. The linked
        sale is left alone - it holds the quote, which can differ.
        """
        missing = [c for c in ordered(codes) if c not in self.survey_types]
        if not missing:
            return
        self.survey_types = ordered(self.survey_types + missing)
        MonthlyAward.objects.filter(pk=self.pk).update(survey_types=self.survey_types)

    def get_invoice_count(self):
        """Get count of invoices linked to this award"""
        return self.invoiced_jobs.count()

    def has_no_invoices(self):
        """Check if award has no invoices - returns True if flagged"""
        return self.get_invoice_count() == 0

    def has_value_mismatch(self):
        """Check if sum of invoice values doesn't match award value"""
        from invoiced_jobs.models import InvoicedJob
        return InvoicedJob.award_has_value_mismatch(self)

    def get_total_invoiced(self):
        """Get sum of all invoice component values"""
        from invoiced_jobs.models import InvoicedJob
        return InvoicedJob.get_award_invoice_total(self)
