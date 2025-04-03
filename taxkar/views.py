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
        
        if request.POST.get('save') and request.user.is_authenticated:
            # Convert Decimal objects to strings for JSON serialization
            serializable_deductions = {
                key: str(value) for key, value in deductions.items()
            }
            
            # Save to regular calculation
            TaxCalculation.objects.create(
                user=request.user,
                gross_income=gross_income,
                deductions=serializable_deductions,  # Use the serializable version
                tax_regime=regime,
                calculated_tax=tax,
                financial_year=f"{datetime.now().year}-{str(datetime.now().year + 1)[2:]}"
            )
            
            # Save to history
            TaxCalculationHistory.objects.create(
                user=request.user,
                income=gross_income,
                regime=regime,
                tax_amount=tax,
                details={
                    'deductions': serializable_deductions,  # Use the serializable version
                    'financial_year': f"{datetime.now().year}-{str(datetime.now().year + 1)[2:]}"
                }
            )

        return render(request, 'tax/result.html', {'tax': tax, 'deductions': deductions})

    return render(request, 'tax/calculator.html')

@login_required
def calculate_gst(request):
    if request.method == 'POST':
        try:
            # Get and validate base_amount
            base_amount = request.POST.get('base_amount', '0')
            if not base_amount or not base_amount.replace('.', '').isdigit():
                base_amount = '0'
            base_amount = Decimal(base_amount)

            # Get and validate gst_rate
            gst_rate = request.POST.get('gst_rate', '0')
            if not gst_rate or not gst_rate.replace('.', '').isdigit():
                gst_rate = '0'
            gst_rate = Decimal(gst_rate)

            transaction_type = request.POST.get('transaction_type', 'INTRA')

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

            return render(request, 'gst/result.html', {
                'gst': calculated_gst,
                'total': total_amount,
                'base_amount': base_amount,
                'gst_rate': gst_rate,
                'transaction_type': transaction_type
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
    # Placeholder for tax calculation logic
    # This should be expanded based on current tax rules
    taxable_income = gross_income - sum(deductions.values())
    # Basic calculation (to be enhanced)
    return max(0, (taxable_income * Decimal('0.2')))


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