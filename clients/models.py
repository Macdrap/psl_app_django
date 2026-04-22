from django.db import models


SECTOR_CHOICES = [
    ('architects', 'Architects'),
    ('local_authority', 'Local Authority'),
    ('consulting_engineer', 'Consulting Engineer'),
    ('construction', 'Construction'),
    ('government_agency', 'Government Agency'),
    ('retail', 'Retail'),
    ('other', 'Other'),
]

CLIENT_STATUS_CHOICES = [
    ('current', 'Current'),
    ('new', 'New'),
    ('dormant', 'Dormant'),
]


class Client(models.Model):
    name = models.CharField(max_length=255, unique=True)
    sector = models.CharField(
        max_length=50,
        choices=SECTOR_CHOICES,
        default='other',
    )
    client_status = models.CharField(
        max_length=20,
        choices=CLIENT_STATUS_CHOICES,
        default='current',
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'


class Contact(models.Model):
    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='contacts'
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.client.name})"

    class Meta:
        verbose_name = 'Contact'
        verbose_name_plural = 'Contacts'
        unique_together = [('client', 'name')]
