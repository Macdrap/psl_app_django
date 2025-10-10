from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from sales_tracker.models import SalesEnquiry


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
    client = models.CharField(max_length=255)
    client_contact = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=100, blank=True, null=True)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Date awarded
    date = models.DateField(default=timezone.now, help_text="Date the job was awarded")

    # Metadata
    created_by = models.ForeignKey(User,on_delete=models.SET_NULL, null=True, related_name='monthly_awards')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Monthly Award'
        verbose_name_plural = 'Monthly Awards'

    def __str__(self):
        return f"Award: Job #{self.job_number} - {self.client}"

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