from django.db import models


class Contact(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Contact'
        verbose_name_plural = 'Contacts'


class Client(models.Model):
    name = models.CharField(max_length=255, unique=True)
    contact = models.ForeignKey(
        Contact,
        on_delete=models.PROTECT,
        related_name='clients'
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
