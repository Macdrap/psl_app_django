from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


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
