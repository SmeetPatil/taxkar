from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from .models import TaxCalculation, GSTCalculation, ForexRate, TaxCalculationHistory, GSTCalculationHistory, \
    ForexConversionHistory
from decimal import Decimal
import json
from datetime import datetime, timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login
from twilio.rest import Client
from .models import PhoneVerification
from django.conf import settings


def home(request):
    return render(request, 'home.html')


# Remove @login_required decorator from calculate_tax function
def calculate_tax(request):
    """Calculate income tax based on user input"""
    context = {}
    
    if request.method == 'POST':
        gross_income = Decimal(request.POST.get('gross_income', 0))
        regime = request.POST.get('regime', 'NEW')
        deductions = {
            '80c': Decimal(request.POST.get('80c', 0)),
            'hra': Decimal(request.POST.get('hra', 0)),
            'medical': Decimal(request.POST.get('medical', 0))
        }

        # Calculate tax with detailed breakdown
        tax_details = calculate_income_tax(gross_income, deductions, regime)
        
        if request.POST.get('save') and request.user.is_authenticated:
            # Convert Decimal objects to strings for JSON serialization
            serializable_deductions = {
                key: str(value) for key, value in deductions.items()
            }
            
            # Save to regular calculation
            TaxCalculation.objects.create(
                user=request.user,
                gross_income=gross_income,
                deductions=serializable_deductions,
                tax_regime=regime,
                calculated_tax=tax_details['tax'],
                financial_year=f"{datetime.now().year}-{str(datetime.now().year + 1)[2:]}"
            )
            
            # Save to history with detailed breakdown
            TaxCalculationHistory.objects.create(
                user=request.user,
                income=gross_income,
                regime=regime,
                tax_amount=tax_details['tax'],
                details={
                    'deductions': serializable_deductions,
                    'tax_slabs': tax_details['tax_slabs'],
                    'surcharge': str(tax_details['surcharge']),
                    'surcharge_rate': tax_details['surcharge_rate'],
                    'cess': str(tax_details['cess']),
                    'financial_year': f"{datetime.now().year}-{str(datetime.now().year + 1)[2:]}"
                }
            )

        # Pass all tax calculation details to template
        context = {
            'tax': tax_details['tax'],
            'tax_slabs': tax_details['tax_slabs'],
            'surcharge': tax_details['surcharge'],
            'surcharge_rate': tax_details['surcharge_rate'],
            'cess': tax_details['cess'],
            'deductions': deductions,
            'gross_income': gross_income,
            'regime': regime,
            'total_deductions': sum(deductions.values()) if regime == 'OLD' else Decimal('0')
        }
        return render(request, 'tax/result.html', context)

    return render(request, 'tax/calculator.html')

# Remove @login_required decorator from calculate_gst function
def calculate_gst(request):
    """Calculate GST based on user input"""
    context = {}
    
    if request.method == 'POST':
        try:
            # Get and validate base_amount
            base_amount = request.POST.get('base_amount', '0')
            if not base_amount or not base_amount.replace('.', '').isdigit():
                base_amount = '0'
            base_amount = Decimal(base_amount)

            # Get category and commodity
            category = request.POST.get('category', '')
            commodity = request.POST.get('commodity', '')
            
            # Get GST rate from category
            category_rate_map = {
                'essential': 0,
                'food_5': 5, 'household_5': 5, 'auto_5': 5, 'clothing_5': 5,
                'food_12': 12, 'household_12': 12, 'auto_12': 12, 'electronics_12': 12, 'jewelry_12': 12,
                'food_18': 18, 'household_18': 18, 'auto_18': 18, 'electronics_18': 18,
                'food_28': 28, 'household_28': 28, 'auto_28': 28, 'electronics_28': 28,
                'jewelry_3': 3
            }
            
            gst_rate = Decimal(str(category_rate_map.get(category, 0)))
            transaction_type = request.POST.get('transaction_type', 'INTRA')

            # Calculate GST based on transaction type
            if transaction_type == 'INTRA':
                # For intra-state, split into CGST and SGST
                single_gst = (base_amount * (gst_rate / 2)) / 100
                calculated_gst = single_gst * 2  # Total GST (CGST + SGST)
            else:
                # For inter-state, calculate IGST
                calculated_gst = (base_amount * gst_rate) / 100

            total_amount = base_amount + calculated_gst

            if request.POST.get('save') and request.user.is_authenticated:
                # Save to regular calculation
                GSTCalculation.objects.create(
                    user=request.user,
                    base_amount=base_amount,
                    gst_rate=gst_rate,
                    transaction_type=transaction_type,
                    calculated_gst=calculated_gst
                )
                
                # Save to history
                GSTCalculationHistory.objects.create(
                    user=request.user,
                    amount=base_amount,
                    gst_rate=gst_rate,
                    gst_amount=calculated_gst,
                    total_amount=total_amount
                )
                
                return redirect('history_dashboard')

            # Get category display name
            category_display = category.replace('_', ' ').title() if category else ''
            if '_' in category_display:
                category_display = ' '.join(category_display.split()[:-1])  # Remove the rate number

            return render(request, 'gst/result.html', {
                'gst': calculated_gst / 2 if transaction_type == 'INTRA' else calculated_gst,  # For display purposes
                'total': total_amount,
                'base_amount': base_amount,
                'gst_rate': gst_rate / 2 if transaction_type == 'INTRA' else gst_rate,  # For display purposes
                'transaction_type': transaction_type,
                'category': category_display,
                'commodity': commodity
            })

        except (ValueError, InvalidOperation) as e:
            # Handle invalid input gracefully
            return render(request, 'gst/calculator.html', {
                'error': 'Please enter valid numbers for amount and GST rate.'
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
    # Calculate taxable income
    taxable_income = gross_income
    if regime == 'OLD':
        # Apply deductions for old regime
        total_deductions = sum(deductions.values())
        taxable_income = max(0, gross_income - total_deductions)
    
    # Initialize tax calculation variables
    tax = Decimal('0')
    tax_slabs = []
    
    if regime == 'NEW':
        # New Tax Regime Slabs FY 2023-24
        remaining = taxable_income
        tax = Decimal('0')

        # Define all slabs
        slabs = [
            (Decimal('300000'), '₹0 - ₹3,00,000', Decimal('0')),
            (Decimal('300000'), '₹3,00,001 - ₹6,00,000', Decimal('0.05')),
            (Decimal('300000'), '₹6,00,001 - ₹9,00,000', Decimal('0.10')),
            (Decimal('300000'), '₹9,00,001 - ₹12,00,000', Decimal('0.15')),
            (Decimal('300000'), '₹12,00,001 - ₹15,00,000', Decimal('0.20')),
            (None, 'Above ₹15,00,000', Decimal('0.30'))
        ]

        # Find the starting slab based on income
        cumulative_amount = Decimal('0')
        for i, (amount, _, _) in enumerate(slabs[:-1]):
            if cumulative_amount + amount >= taxable_income:
                break
            cumulative_amount += amount

        # Calculate tax only for applicable slabs
        for amount, label, rate in slabs:
            if remaining <= 0:
                break
                
            if amount is None:  # Final slab
                if remaining > 0:
                    slab_tax = remaining * rate
                    tax += slab_tax
                    if rate > 0:  # Only show slabs with actual tax
                        tax_slabs.append({'range': f'{label} @ {int(rate * 100)}%', 'tax': str(slab_tax)})
                break
            
            slab_amount = min(remaining, amount)
            if slab_amount > 0:
                slab_tax = slab_amount * rate
                tax += slab_tax
                if rate > 0:  # Only show slabs with actual tax
                    tax_slabs.append({'range': f'{label} @ {int(rate * 100)}%', 'tax': str(slab_tax)})
                remaining -= slab_amount
    
    else:  # Old Tax Regime
        remaining = taxable_income
        tax = Decimal('0')

        # Define all slabs
        slabs = [
            (Decimal('250000'), '₹0 - ₹2,50,000', Decimal('0')),
            (Decimal('250000'), '₹2,50,001 - ₹5,00,000', Decimal('0.05')),
            (Decimal('250000'), '₹5,00,001 - ₹7,50,000', Decimal('0.20')),
            (Decimal('250000'), '₹7,50,001 - ₹10,00,000', Decimal('0.20')),
            (Decimal('250000'), '₹10,00,001 - ₹12,50,000', Decimal('0.30')),
            (None, 'Above ₹12,50,000', Decimal('0.30'))
        ]

        # Find the starting slab based on income
        cumulative_amount = Decimal('0')
        for i, (amount, _, _) in enumerate(slabs[:-1]):
            if cumulative_amount + amount >= taxable_income:
                break
            cumulative_amount += amount

        # Calculate tax only for applicable slabs
        for amount, label, rate in slabs:
            if remaining <= 0:
                break
                
            if amount is None:  # Final slab
                if remaining > 0:
                    slab_tax = remaining * rate
                    tax += slab_tax
                    if rate > 0:  # Only show slabs with actual tax
                        tax_slabs.append({'range': f'{label} @ {int(rate * 100)}%', 'tax': str(slab_tax)})
                break
            
            slab_amount = min(remaining, amount)
            if slab_amount > 0:
                slab_tax = slab_amount * rate
                tax += slab_tax
                if rate > 0:  # Only show slabs with actual tax
                    tax_slabs.append({'range': f'{label} @ {int(rate * 100)}%', 'tax': str(slab_tax)})
                remaining -= slab_amount
    
    # Calculate surcharge for high income
    surcharge = Decimal('0')
    surcharge_rate = 0
    if taxable_income > 5000000 and taxable_income <= 10000000:
        surcharge_rate = 10
        surcharge = tax * Decimal('0.10')
    elif taxable_income > 10000000 and taxable_income <= 20000000:
        surcharge_rate = 15
        surcharge = tax * Decimal('0.15')
    elif taxable_income > 20000000 and taxable_income <= 50000000:
        surcharge_rate = 25
        surcharge = tax * Decimal('0.25')
    elif taxable_income > 50000000:
        surcharge_rate = 37
        surcharge = tax * Decimal('0.37')
    
    # Calculate health and education cess
    cess = (tax + surcharge) * Decimal('0.04')
    
    # Total tax payable
    total_tax = tax + surcharge + cess
    
    return {
        'tax': total_tax,
        'tax_slabs': tax_slabs,
        'surcharge': surcharge,
        'surcharge_rate': surcharge_rate,
        'cess': cess
    }


@login_required
def history_view(request):
    tax_calculations = TaxCalculation.objects.filter(user=request.user).order_by('-calculation_date')
    gst_calculations = GSTCalculation.objects.filter(user=request.user).order_by('-calculation_date')

    return render(request, 'history/history.html', {
        'tax_calculations': tax_calculations,
        'gst_calculations': gst_calculations
    })


@login_required
def history_dashboard(request):
    tax_history = TaxCalculationHistory.objects.filter(user=request.user)[:10]
    gst_history = GSTCalculationHistory.objects.filter(user=request.user)[:10]
    forex_history = ForexConversionHistory.objects.filter(user=request.user)[:10]

    context = {
        'tax_history': tax_history,
        'gst_history': gst_history,
        'forex_history': forex_history,
    }

    return render(request, 'history/history.html', context)

#Forex Views and Models

#NEW
# views.py

import requests
from datetime import datetime, timedelta, time
import json
from django.shortcuts import render
from .models import ExchangeRate, HistoricalRate
import pandas as pd
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder


class ForexConverter:
    FRANKFURTER_BASE_URL = "https://api.frankfurter.app"

    @staticmethod
    def get_exchange_rate(from_currency, to_currency):
        """Get current exchange rate"""
        try:
            url = f"{ForexConverter.FRANKFURTER_BASE_URL}/latest"
            print(f"Fetching current rate from: {url}")  # Debug log

            response = requests.get(
                url,
                params={
                    'from': from_currency,
                    'to': to_currency
                }
            )

            print(f"Response status: {response.status_code}")  # Debug log
            print(f"Response content: {response.text}")  # Debug log

            if response.status_code == 200:
                data = response.json()
                return data['rates'][to_currency]
            return None
        except Exception as e:
            print(f"Error fetching current rate: {e}")
            return None

    @staticmethod
    def get_historical_data(from_currency, to_currency):
        """Get only last month of data"""
        try:
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)

            url = f"{ForexConverter.FRANKFURTER_BASE_URL}/{start_date.strftime('%Y-%m-%d')}..{end_date.strftime('%Y-%m-%d')}"
            print(f"Fetching historical data from: {url}")  # Debug log

            response = requests.get(
                url,
                params={
                    'from': from_currency,
                    'to': to_currency
                }
            )

            print(f"Historical data response status: {response.status_code}")  # Debug log
            print(f"Historical data response content: {response.text}")  # Debug log

            if response.status_code == 200:
                data = response.json()
                # Make sure the data structure is correct
                if 'rates' in data:
                    historical_data = [
                        {'date': date, 'rate': rates[to_currency]}
                        for date, rates in data['rates'].items()
                    ]
                    print(f"Processed historical data: {historical_data[:5]}")  # Debug log first 5 entries
                    return sorted(historical_data, key=lambda x: x['date'])
            return []

        except Exception as e:
            print(f"Error in get_historical_data: {e}")
            return []

    @staticmethod
    def get_available_currencies():
        """Get list of available currencies"""
        try:
            response = requests.get(f"{ForexConverter.FRANKFURTER_BASE_URL}/currencies")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error fetching currencies: {e}")
            return None

def converter(request, converted_amount=None):
    context = {}
    current_date = datetime.now().strftime("%H:%M:%S, %A, %d-%m-%Y")
    context['current_date'] = current_date
    # Get available currencies
    currencies = ForexConverter.get_available_currencies()
    if currencies:
        context['currencies'] = currencies

    if request.method == 'POST':
        try:
            from_currency = request.POST.get('from_currency', 'USD')
            to_currency = request.POST.get('to_currency', 'EUR')
            amount = float(request.POST.get('amount', 1))

            print(f"Converting from {from_currency} to {to_currency}")  # Debug log

            # Get current rate
            rate = ForexConverter.get_exchange_rate(from_currency, to_currency)
            print(f"Current rate: {rate}")  # Debug log

            if rate is not None:
                # Get historical data (last month only)
                historical_data = ForexConverter.get_historical_data(from_currency, to_currency)
                print(f"Historical data: {historical_data}")  # Debug log

                if request.POST.get('save') and request.user.is_authenticated:
                    ForexConversionHistory.objects.create(
                        user=request.user,
                        from_currency=from_currency,
                        to_currency=to_currency,
                        amount=amount,
                        converted_amount=converted_amount,
                        exchange_rate=rate
                    )
                    
                if historical_data:
                    # Create plot
                    df = pd.DataFrame(historical_data)
                    print(f"DataFrame head: {df.head()}")  # Debug log
                    print(f"DataFrame columns: {df.columns}")  # Debug log

                    # Create figure
                    fig = go.Figure()

                    # Add exchange rate line
                    fig.add_trace(go.Scatter(
                        x=df['date'],
                        y=df['rate'],
                        mode='lines',
                        name=f'1 {from_currency} = {to_currency}',
                        line=dict(color='#FF4E16', width=2),  # Default to accent color
                        hovertemplate='Date: %{x}<br>1 ' + from_currency + ' = %{y:.2f} ' + to_currency + '<extra></extra>'
                    ))

                    # Calculate appropriate y-axis range
                    y_min = df['rate'].min() * 0.900
                    y_max = df['rate'].max() * 1.205
                    print(f"Y-axis range: {y_min} to {y_max}")  # Debug log

                    # Update layout
                    fig.update_layout(
                        title=dict(
                            text=f'{from_currency}/{to_currency} Exchange Rate - Last 30 Days',
                            x=0.5,
                            xanchor='center'
                        ),
                        xaxis=dict(
                            title='Date',
                            gridcolor='rgba(255, 255, 255, 0.1)',
                            showgrid=True
                        ),
                        yaxis=dict(
                            title=f'{to_currency}',
                            gridcolor='rgba(255, 255, 255, 0.1)',
                            showgrid=True,
                            tickformat='.2f',
                            range=[y_min, y_max]
                        ),
                        template='plotly_dark',  # Use dark template as base
                        hovermode='x unified',
                        showlegend=True,
                        plot_bgcolor='#0F0904',  # Match primary color
                        paper_bgcolor='#0F0904'  # Match primary color
                    )

                    # Simpler range selector with custom styling
                    fig.update_xaxes(
                        rangeslider_visible=True,
                        rangeselector=dict(
                            buttons=list([
                                dict(count=7, label="1w", step="day", stepmode="backward"),
                                dict(count=14, label="2w", step="day", stepmode="backward"),
                                dict(step="all", label="1m")
                            ]),
                            bgcolor='rgba(255, 139, 61, 0.1)',  # Match your theme
                            activecolor='rgba(255, 78, 22, 0.5)',  # Accent color when active
                            x=0.05,  # Position from left
                            y=1.1,   # Position from bottom
                            font=dict(
                                color='#ffffff',  # White text
                                size=12,
                            ),
                            bordercolor='rgba(255, 139, 61, 0.2)',  # Border color
                            borderwidth=1,
                        ),
                        rangeslider=dict(
                            bgcolor='rgba(255, 255, 255, 0.05)',
                            bordercolor='rgba(255, 139, 61, 0.2)',
                        )
                    )

                    plot_data = json.dumps(fig.to_dict(), cls=PlotlyJSONEncoder)
                    context['plot_data'] = plot_data
                    print("Plot data created successfully")  # Debug log
                else:
                    print("No historical data received")  # Debug log

                context.update({
                    'rate': rate * amount,
                    'from_currency': from_currency,
                    'to_currency': to_currency,
                    'amount': amount,
                    'error': None
                })
            else:
                context['error'] = "Unable to fetch exchange rate. Please try again."
                print("Failed to get current rate")  # Debug log
        except Exception as e:
            context['error'] = f"An error occurred: {str(e)}"
            print(f"Exception occurred: {e}")  # Debug log

    return render(request, 'forex/converter.html', context)