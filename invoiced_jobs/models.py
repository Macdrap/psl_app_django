from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from monthly_awards.models import MonthlyAward


class InvoicedJob(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Invoiced', 'Invoiced'),
    ]

    # Foreign key to MonthlyAward - REQUIRED (always linked)
    # Changed to allow MULTIPLE invoices per award
    award = models.ForeignKey(
        MonthlyAward,
        on_delete=models.CASCADE,
        related_name='invoiced_jobs'
    )

    # NEW: Description field for manual invoices
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description for this invoice"
    )

    # Date invoiced
    date = models.DateField(default=timezone.now, help_text="Date the job was invoiced")

    # Value breakdown
    utility_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cad_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    topo_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    contractor_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # PSL value (automatically calculated)
    psl_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)

    # Status
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='invoiced_jobs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Invoiced Job'
        verbose_name_plural = 'Invoiced Jobs'

    def __str__(self):
        desc = f" - {self.description[:30]}" if self.description else ""
        return f"Invoice: Job #{self.award.job_number}{desc}"

    def save(self, *args, **kwargs):
        """
        Override save to automatically calculate PSL value
        PSL Value = Award Total Value - Contractor Value

        Also auto-update date for old pending invoices
        """
        if self.award:
            self.psl_value = self.utility_value + self.cad_value + self.topo_value

        # Auto-move old pending invoices to current month
        if self.status == 'Pending':
            current_date = timezone.now().date()
            if self.date < current_date.replace(day=1):  # If before current month
                self.date = current_date

        super().save(*args, **kwargs)

    def get_total_invoice_value(self):
        """Get total value of this invoice's components"""
        return (
                self.utility_value +
                self.cad_value +
                self.topo_value +
                self.contractor_value
        )

    @staticmethod
    def get_award_invoice_total(award):
        """Get sum of all invoice component values for an award"""
        invoices = InvoicedJob.objects.filter(award=award)
        total = sum(
            inv.utility_value + inv.cad_value +
            inv.topo_value + inv.contractor_value
            for inv in invoices
        )
        return total

    @staticmethod
    def award_has_value_mismatch(award):
        """Check if sum of all invoices doesn't match award value"""
        total_invoiced = InvoicedJob.get_award_invoice_total(award)
        return round(total_invoiced, 2) != round(award.value or 0, 2)