from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=15, null=True, blank=True)
    google_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user.username

class TaxCalculation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    financial_year = models.CharField(max_length=9)  # Format: 2024-25
    gross_income = models.DecimalField(max_digits=12, decimal_places=2)
    deductions = models.JSONField()
    tax_regime = models.CharField(max_length=10, choices=[('OLD', 'Old'), ('NEW', 'New')])
    calculated_tax = models.DecimalField(max_digits=12, decimal_places=2)
    calculation_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-calculation_date']

class GSTCalculation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=[('INTRA', 'Intra State'), ('INTER', 'Inter State')])
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=4, decimal_places=2)
    calculated_gst = models.DecimalField(max_digits=12, decimal_places=2)
    calculation_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-calculation_date']

class ForexRate(models.Model):
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=10, decimal_places=4)
    date = models.DateField()

    class Meta:
        unique_together = ('from_currency', 'to_currency', 'date')