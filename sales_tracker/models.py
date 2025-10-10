from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class SalesEnquiry(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Rejected', 'Rejected'),
        ('Awarded', 'Awarded'),
    ]

    job_number = models.CharField(max_length=20)
    date = models.DateField(default=timezone.now)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    location = models.TextField()
    client = models.CharField(max_length=255)
    client_contact = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=100, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='sales_enquiries')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-created_at']
        verbose_name = 'Sales Enquiry'
        verbose_name_plural = 'Sales Enquiries'

    def __str__(self):
        return f"Job #{self.job_number} - {self.client}"