from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from monthly_awards.models import MonthlyAward
from sales_tracker.survey_types import SURVEY_TYPES, DEPARTMENT_VALUE_FIELDS


class InvoicedJob(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Invoiced', 'Invoiced'),
    ]
    FOLLOW_STATUS = [
        ("n_a", "N/A"),
        ("to_follow", "To Follow"),
        ("followed_up", "Followed Up"),
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

    # Value breakdown - one field per survey type (sales_tracker/survey_types.py).
    # mbs_value was called cad_value before migration 0010 (CAD renamed to MBS).
    utility_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mbs_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    topo_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    contractor_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    watercourse_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cctv_drainage_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    modelling_3d_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    drone_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    engineering_value = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # PSL value (automatically calculated)
    psl_value = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False)

    # Status
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')

    # Follow up
    follow_up_status = models.CharField(max_length=20, choices=FOLLOW_STATUS, default="n_a")
    followed_up_date = models.DateField(null=True, blank=True)

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
        PSL value = every department except Contractor (total - contractor).
        A department given a value here becomes one of the job's survey types.
        """
        self.psl_value = self.get_total_invoice_value() - (self.contractor_value or 0)
        super().save(*args, **kwargs)
        if self.award_id:
            self.award.add_survey_types(self.departments_with_value())

    def get_total_invoice_value(self):
        """Get total value of this invoice's components (all departments)"""
        return sum((getattr(self, f) or 0 for f in DEPARTMENT_VALUE_FIELDS), 0)

    def departments_with_value(self):
        """Survey type codes this invoice puts a non-zero value against."""
        return [code for code, _, field, _ in SURVEY_TYPES if getattr(self, field)]

    def department_breakdown(self):
        """'Utility £100.00, MBS £50.00' - for tooltips."""
        return ', '.join(f'{label} £{getattr(self, field):,.2f}'
                         for _, label, field, _ in SURVEY_TYPES if getattr(self, field))

    @staticmethod
    def get_award_invoice_total(award):
        """Get sum of all invoice component values for an award"""
        invoices = InvoicedJob.objects.filter(award=award)
        return sum((inv.get_total_invoice_value() for inv in invoices), 0)

    @staticmethod
    def award_has_value_mismatch(award):
        """Check if sum of all invoices doesn't match award value"""
        total_invoiced = InvoicedJob.get_award_invoice_total(award)
        return round(total_invoiced, 2) != round(award.value or 0, 2)