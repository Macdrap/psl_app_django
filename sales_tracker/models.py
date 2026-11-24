from django.db import models
from django.contrib.auth.models import User
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone

from .survey_types import SURVEY_TYPE_CHOICES, badges, split_breakdown, split_values


class SalesEnquiry(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Rejected', 'Rejected'),
        ('Awarded', 'Awarded'),
        ('Not_Quoted', 'Not Quoted')
    ]

    FEEDBACK_CHOICES = [
        ('Price', 'Price'),
        ('Timeframe', 'Timeframe'),
        ('Capability', 'Capability'),
        ('Other', 'Other')
    ]

    # Statuses that count as a quote in client quote figures (Statistic Explorer
    # Client Analysis, Clients page). Enquiries at £0 are excluded as well.
    QUOTED_STATUSES = ('Pending', 'Awarded', 'Rejected')

    REFERRAL_CHOICES = [
        ('google', 'Google'),
        ('recommendation', 'Recommendation'),
        ('website_form', 'Website Contact Form'),
        ('other', 'Other'),
    ]

    job_number = models.CharField(max_length=20)
    date = models.DateField(default=timezone.now)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    note = models.TextField(blank=True, null=True)
    feedback = models.CharField(blank=True, null=True, choices=FEEDBACK_CHOICES, default='')
    other_feedback = models.TextField(blank=True, null=True)
    location = models.TextField()
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales_enquiries'
    )
    contact = models.ForeignKey(
        'clients.Contact',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales_enquiries'
    )
    referral = models.CharField(max_length=20, choices=REFERRAL_CHOICES, blank=True, null=True)
    # One or more survey types (departments), codes from sales_tracker/survey_types.py
    survey_types = ArrayField(
        models.CharField(max_length=20, choices=SURVEY_TYPE_CHOICES),
        default=list, blank=True,
    )
    # Value per survey type, {code: "123.45"}. When survey types are ticked,
    # `value` is the sum of these (set by SalesEnquiryEditForm). Empty for
    # enquiries whose value was never split (no survey type, or legacy data).
    survey_type_values = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales_enquiries')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Sales Enquiry'
        verbose_name_plural = 'Sales Enquiries'

    def __str__(self):
        client_name = self.client.name if self.client else 'N/A'
        return f"Job #{self.job_number} - {client_name}"

    def survey_type_badges(self):
        return badges(self.survey_types)

    def get_survey_type_values(self):
        """{code: Decimal} for each of the enquiry's survey types, or {} if the
        value was never split between them."""
        return split_values(self.survey_types, self.survey_type_values)

    def survey_type_value_breakdown(self):
        """'MBS £600.00, Topo £400.00' - for tooltips; '' when not split."""
        return split_breakdown(self.get_survey_type_values())
