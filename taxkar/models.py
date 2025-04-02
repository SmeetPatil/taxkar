from datetime import datetime
from django.contrib.auth.models import User
from django.db import models
from django.conf import settings  # Add this import


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


from django.db import models
from django.contrib.auth.models import User
import random


class PhoneVerification(models.Model):
    phone_number = models.CharField(max_length=15)
    verification_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def generate_code(cls):
        return str(random.randint(100000, 999999))


# taxkar/models.py
# Add these models to your existing models.py

class TaxCalculationHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    calculation_date = models.DateTimeField(auto_now_add=True)
    income = models.DecimalField(max_digits=12, decimal_places=2)
    regime = models.CharField(max_length=10)  # 'old' or 'new'
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2)
    details = models.JSONField(null=True, blank=True)  # Store additional calculation details

    class Meta:
        ordering = ['-calculation_date']


class GSTCalculationHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    calculation_date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    gst_rate = models.DecimalField(max_digits=5, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=12, decimal_places=2)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['-calculation_date']


class ForexConversionHistory(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    conversion_date = models.DateTimeField(auto_now_add=True)
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    converted_amount = models.DecimalField(max_digits=12, decimal_places=2)
    exchange_rate = models.DecimalField(max_digits=15, decimal_places=6)

    class Meta:
        ordering = ['-conversion_date']

# models.py

from django.db import models
from datetime import datetime

class ExchangeRate(models.Model):
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=20, decimal_places=10)
    timestamp = models.DateTimeField(default=datetime.now)

    class Meta:
        indexes = [
            models.Index(fields=['from_currency', 'to_currency']),
            models.Index(fields=['timestamp']),
        ]

class HistoricalRate(models.Model):
    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(max_digits=20, decimal_places=10)
    date = models.DateField()

    class Meta:
        indexes = [
            models.Index(fields=['from_currency', 'to_currency', 'date']),
        ]


class StockData(models.Model):
    symbol = models.CharField(max_length=10)
    date = models.DateField()
    open_price = models.DecimalField(max_digits=20, decimal_places=2)
    high_price = models.DecimalField(max_digits=20, decimal_places=2)
    low_price = models.DecimalField(max_digits=20, decimal_places=2)
    close_price = models.DecimalField(max_digits=20, decimal_places=2)
    volume = models.BigIntegerField()
    
    class Meta:
        indexes = [
            models.Index(fields=['symbol', 'date']),
        ]
        unique_together = ('symbol', 'date')
        ordering = ['-date']

class StockPrediction(models.Model):
    symbol = models.CharField(max_length=10)
    prediction_date = models.DateTimeField(auto_now_add=True)
    target_date = models.DateField()
    predicted_price = models.DecimalField(max_digits=20, decimal_places=2)
    confidence_interval_lower = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    confidence_interval_upper = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    model_parameters = models.JSONField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['symbol', 'target_date']),
            models.Index(fields=['user', 'prediction_date']),
        ]
        ordering = ['-prediction_date']

class StockSearchHistory(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    symbol = models.CharField(max_length=10)
    search_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'search_date']),
        ]
        ordering = ['-search_date']