from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import TaxCalculation, GSTCalculation, ForexRate
from decimal import Decimal
import json
from datetime import datetime, timedelta


def home(request):
    return render(request, 'home.html')


@login_required
def calculate_tax(request):
    if request.method == 'POST':
        gross_income = Decimal(request.POST.get('gross_income', 0))
        regime = request.POST.get('regime', 'NEW')
        deductions = {
            '80c': Decimal(request.POST.get('80c', 0)),
            'hra': Decimal(request.POST.get('hra', 0)),
            'medical': Decimal(request.POST.get('medical', 0))
        }

        # Basic tax calculation logic (to be expanded)
        tax = calculate_income_tax(gross_income, deductions, regime)

        if request.POST.get('save', False):
            TaxCalculation.objects.create(
                user=request.user,
                gross_income=gross_income,
                deductions=deductions,
                tax_regime=regime,
                calculated_tax=tax,
                financial_year=f"{datetime.now().year}-{str(datetime.now().year + 1)[2:]}"
            )

        return render(request, 'tax/result.html', {'tax': tax, 'deductions': deductions})

    return render(request, 'tax/calculator.html')


@login_required
def calculate_gst(request):
    if request.method == 'POST':
        base_amount = Decimal(request.POST.get('base_amount', 0))
        gst_rate = Decimal(request.POST.get('gst_rate', 0))
        transaction_type = request.POST.get('transaction_type', 'INTRA')

        calculated_gst = (base_amount * gst_rate) / 100

        if request.POST.get('save', False):
            GSTCalculation.objects.create(
                user=request.user,
                base_amount=base_amount,
                gst_rate=gst_rate,
                transaction_type=transaction_type,
                calculated_gst=calculated_gst
            )

        return render(request, 'gst/result.html', {
            'gst': calculated_gst,
            'total': base_amount + calculated_gst
        })

    return render(request, 'gst/calculator.html')


@login_required
def forex_converter(request):
    currencies = ['USD', 'EUR', 'INR']
    rates = ForexRate.objects.filter(
        date=datetime.now().date(),
        from_currency__in=currencies,
        to_currency__in=currencies
    )

    return render(request, 'forex/converter.html', {'rates': rates})


def calculate_income_tax(gross_income, deductions, regime):
    # Placeholder for tax calculation logic
    # This should be expanded based on current tax rules
    taxable_income = gross_income - sum(deductions.values())
    # Basic calculation (to be enhanced)
    return max(0, (taxable_income * Decimal('0.2')))


@login_required
def history_view(request):
    tax_calculations = TaxCalculation.objects.filter(user=request.user).order_by('-calculation_date')
    gst_calculations = GSTCalculation.objects.filter(user=request.user).order_by('-calculation_date')

    return render(request, 'history.html', {
        'tax_calculations': tax_calculations,
        'gst_calculations': gst_calculations
    })