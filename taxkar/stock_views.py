import json
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from statsmodels.tsa.arima.model import ARIMA
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from plotly.utils import PlotlyJSONEncoder
import plotly.graph_objects as go
from .models import StockData, StockPrediction, StockSearchHistory
import os
import time

# Read Alpha Vantage API key from file
try:
    with open(os.path.join(os.path.dirname(__file__), 'alpha_vantage_api_key.txt'), 'r') as file:
        ALPHA_VANTAGE_API_KEY = file.read().strip()
except FileNotFoundError:
    ALPHA_VANTAGE_API_KEY = '4RV4AL39F2VA8GYL'  # Using your existing API key as fallback

def get_stock_data(symbol, period='1y'):
    """Fetch stock data from Alpha Vantage API"""
    try:
        # Check if we have recent data in the database
        latest_data = StockData.objects.filter(symbol=symbol).order_by('-date').first()
        today = datetime.now().date()
        
        # If we have recent data (within last 24 hours) and not requesting full history, return from DB
        if latest_data and (today - latest_data.date).days < 1 and period != '2y':
            # Get data from database
            stock_data = StockData.objects.filter(symbol=symbol).order_by('date')
            
            # Check if we have enough data
            if stock_data.count() < 5:
                # Not enough data, fetch from API
                print(f"Not enough data for {symbol} in database, fetching from API")
            else:
                # Convert to DataFrame
                data = {
                    'date': [item.date for item in stock_data],
                    'open_price': [float(item.open_price) for item in stock_data],
                    'high_price': [float(item.high_price) for item in stock_data],
                    'low_price': [float(item.low_price) for item in stock_data],
                    'close_price': [float(item.close_price) for item in stock_data],
                    'volume': [item.volume for item in stock_data]
                }
                df = pd.DataFrame(data)
                
                # Check if DataFrame is valid
                if not df.empty and len(df) > 5:
                    print(f"Using cached data for {symbol} from database")
                    return df
        
        # Try different API endpoints to get the data
        # First try: Standard Alpha Vantage endpoint
        url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&outputsize=compact&apikey={ALPHA_VANTAGE_API_KEY}'
        print(f"Fetching data for {symbol} from Alpha Vantage")
        response = requests.get(url)
        data = response.json()
        
        # Check if we got valid data
        if 'Time Series (Daily)' not in data:
            # Check if we hit API limit
            if 'Note' in data and 'API call frequency' in data['Note']:
                print(f"API limit reached: {data['Note']}")
                # Wait and try again with a different API key or endpoint
                time.sleep(1)
                
                # Try with a different API endpoint (Alpha Vantage Global Quote)
                url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}'
                response = requests.get(url)
                quote_data = response.json()
                
                if 'Global Quote' in quote_data and quote_data['Global Quote']:
                    # We got at least current quote data
                    print(f"Got quote data for {symbol}")
                    
                    # Create a minimal dataset with just today's data
                    today = datetime.now().date()
                    quote = quote_data['Global Quote']
                    
                    # Create a single-row DataFrame
                    df = pd.DataFrame({
                        'date': [today],
                        'open_price': [float(quote.get('02. open', 0))],
                        'high_price': [float(quote.get('03. high', 0))],
                        'low_price': [float(quote.get('04. low', 0))],
                        'close_price': [float(quote.get('05. price', 0))],
                        'volume': [int(quote.get('06. volume', 0))]
                    })
                    
                    # Store in database
                    StockData.objects.update_or_create(
                        symbol=symbol,
                        date=today,
                        defaults={
                            'open_price': float(quote.get('02. open', 0)),
                            'high_price': float(quote.get('03. high', 0)),
                            'low_price': float(quote.get('04. low', 0)),
                            'close_price': float(quote.get('05. price', 0)),
                            'volume': int(quote.get('06. volume', 0))
                        }
                    )
                    
                    return df
            
            # Try with different region/exchange
            print(f"No data found for {symbol}, trying with BSE suffix")
            url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}.BSE&outputsize=compact&apikey={ALPHA_VANTAGE_API_KEY}'
            response = requests.get(url)
            data = response.json()
            
            if 'Time Series (Daily)' not in data:
                # Try with NSE (for Indian stocks)
                print(f"No data found for {symbol}.BSE, trying with NSE suffix")
                url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}.NSE&outputsize=compact&apikey={ALPHA_VANTAGE_API_KEY}'
                response = requests.get(url)
                data = response.json()
                
                if 'Time Series (Daily)' not in data:
                    print(f"No data found for {symbol} with any exchange")
                    return None
        
        # Extract time series data
        time_series = data['Time Series (Daily)']
        
        # Convert to DataFrame
        df = pd.DataFrame.from_dict(time_series, orient='index')
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        
        # Rename columns
        df = df.rename(columns={
            '1. open': 'open_price',
            '2. high': 'high_price',
            '3. low': 'low_price',
            '4. close': 'close_price',
            '5. volume': 'volume'
        })
        
        # Convert types
        df['open_price'] = df['open_price'].astype(float)
        df['high_price'] = df['high_price'].astype(float)
        df['low_price'] = df['low_price'].astype(float)
        df['close_price'] = df['close_price'].astype(float)
        df['volume'] = df['volume'].astype(int)
        
        # Add date column
        df['date'] = df.index
        
        # Store in database for caching
        for index, row in df.iterrows():
            StockData.objects.update_or_create(
                symbol=symbol,
                date=index.date(),
                defaults={
                    'open_price': row['open_price'],
                    'high_price': row['high_price'],
                    'low_price': row['low_price'],
                    'close_price': row['close_price'],
                    'volume': row['volume']
                }
            )
        
        print(f"Successfully fetched and stored data for {symbol}")
        # Convert string values to float in the DataFrame
        for col in ['open_price', 'high_price', 'low_price', 'close_price']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
        # Scale adjustment - check if prices are too low compared to current market price
        # This is a workaround for the API sometimes returning adjusted prices
        if 'close_price' in df.columns and not df.empty:
            # Get the latest price from a different endpoint for verification
            verify_url = f'https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_API_KEY}'
            verify_response = requests.get(verify_url)
            verify_data = verify_response.json()
            
            if 'Global Quote' in verify_data and '05. price' in verify_data['Global Quote']:
                current_market_price = float(verify_data['Global Quote']['05. price'])
                latest_df_price = float(df['close_price'].iloc[-1])
                
                # If there's a significant discrepancy (more than 50%), adjust the prices
                if latest_df_price > 0 and current_market_price / latest_df_price > 2:
                    scale_factor = current_market_price / latest_df_price
                    print(f"Adjusting prices for {symbol} with scale factor {scale_factor}")
                    df['open_price'] = df['open_price'] * scale_factor
                    df['high_price'] = df['high_price'] * scale_factor
                    df['low_price'] = df['low_price'] * scale_factor
                    df['close_price'] = df['close_price'] * scale_factor
        
        return df
    except Exception as e:
        print(f"Error fetching stock data: {e}")
        return None

def predict_stock_price(symbol, days=30):
    """Predict stock prices using ARIMA model"""
    try:
        # Get historical data
        df = get_stock_data(symbol, period='2y')
        if df is None or len(df) < 60:  # Need sufficient data for prediction
            print(f"Not enough data for prediction: {symbol}")
            return None
            
        # Prepare data for ARIMA
        price_data = df['close_price'].values
        
        # Fit ARIMA model - using auto_arima would be better but simplified for now
        model = ARIMA(price_data, order=(5,1,0))
        model_fit = model.fit()
        
        # Make prediction
        forecast = model_fit.forecast(steps=days)
        
        # Get confidence intervals
        pred_conf = model_fit.get_forecast(steps=days).conf_int()
        
        # Fix: Check if pred_conf is a numpy array and handle accordingly
        if isinstance(pred_conf, np.ndarray):
            # If it's a numpy array, it likely has shape (days, 2)
            lower_conf = pred_conf[:, 0]  # First column is lower bound
            upper_conf = pred_conf[:, 1]  # Second column is upper bound
        else:
            # If it's a pandas DataFrame, use iloc
            lower_conf = pred_conf.iloc[:, 0]
            upper_conf = pred_conf.iloc[:, 1]
        
        # Create date range for prediction
        last_date = df['date'].iloc[-1] if isinstance(df['date'], pd.Series) else df['date'][-1]
        future_dates = [last_date + timedelta(days=i+1) for i in range(days)]
        
        # Create prediction results
        predictions = []
        for i, date in enumerate(future_dates):
            predictions.append({
                'date': date.strftime('%Y-%m-%d'),
                'predicted_price': forecast[i],
                'lower_bound': lower_conf[i],
                'upper_bound': upper_conf[i]
            })
            
        # Store prediction in database
        for pred in predictions:
            StockPrediction.objects.create(
                symbol=symbol,
                target_date=datetime.strptime(pred['date'], '%Y-%m-%d'),
                predicted_price=pred['predicted_price'],
                confidence_interval_lower=pred['lower_bound'],
                confidence_interval_upper=pred['upper_bound'],
                model_parameters=json.dumps({"order": (5,1,0)}),
                user=None  # Set to the current user if authenticated
            )
            
        return predictions
    except Exception as e:
        print(f"Error in prediction: {e}")
        # Add more detailed error information for debugging
        import traceback
        traceback.print_exc()
        return None

def stock_tracker(request):
    context = {}
    current_date = datetime.now().strftime("%H:%M:%S, %A, %d-%m-%Y")
    context['current_date'] = current_date
    
    if request.method == 'POST':
        symbol = request.POST.get('symbol', '').upper()
        if symbol:
            # Save search history if user is logged in
            if request.user.is_authenticated:
                StockSearchHistory.objects.create(
                    user=request.user,
                    symbol=symbol
                )
                
            # Get stock data
            stock_data = get_stock_data(symbol)
            
            if stock_data is not None and not stock_data.empty:
                # Skip creating the historical price graph
                # Instead, directly get prediction data which includes historical context
                
                # Add stock info to context
                context.update({
                    'symbol': symbol,
                    'current_price': stock_data['close_price'].iloc[-1],
                    'price_change': stock_data['close_price'].iloc[-1] - stock_data['close_price'].iloc[-2] if len(stock_data) > 1 else 0,
                    'price_change_percent': ((stock_data['close_price'].iloc[-1] - stock_data['close_price'].iloc[-2]) / stock_data['close_price'].iloc[-2] * 100) if len(stock_data) > 1 else 0,
                    'error': None
                })
                
                # Get prediction data if we have enough historical data
                if len(stock_data) >= 60:
                    prediction_data = predict_stock_price(symbol)
                    
                    if prediction_data:
                        # Create prediction plot
                        pred_fig = go.Figure()
                        
                        # Extract prediction data
                        pred_dates = [datetime.strptime(p['date'], '%Y-%m-%d') for p in prediction_data]
                        pred_prices = [p['predicted_price'] for p in prediction_data]
                        lower_bounds = [p['lower_bound'] for p in prediction_data]
                        upper_bounds = [p['upper_bound'] for p in prediction_data]
                        
                        # Get the last 30 days of historical data for context
                        historical_dates = stock_data['date'][-30:].tolist()
                        historical_prices = stock_data['close_price'][-30:].tolist()
                        
                        # Add historical data
                        pred_fig.add_trace(go.Scatter(
                            x=historical_dates,
                            y=historical_prices,
                            mode='lines',
                            name='Historical',
                            line=dict(color='#1f77b4', width=2)
                        ))
                        
                        # Add prediction line
                        pred_fig.add_trace(go.Scatter(
                            x=pred_dates,
                            y=pred_prices,
                            mode='lines',
                            name='Prediction',
                            line=dict(color='#FF4E16', width=2)
                        ))
                        
                        # Add confidence interval
                        pred_fig.add_trace(go.Scatter(
                            x=pred_dates + pred_dates[::-1],
                            y=upper_bounds + lower_bounds[::-1],
                            fill='toself',
                            fillcolor='rgba(255, 78, 22, 0.2)',
                            line=dict(color='rgba(255, 78, 22, 0)'),
                            name='95% Confidence Interval'
                        ))
                        
                        # Update layout
                        pred_fig.update_layout(
                            title=dict(
                                text=f'{symbol} Price History & Forecast',
                                x=0.5,
                                xanchor='center'
                            ),
                            xaxis=dict(
                                title='Date',
                                gridcolor='rgba(255, 255, 255, 0.1)',
                                showgrid=True,
                                rangeselector=dict(
                                    buttons=list([
                                        dict(count=7, label="1w", step="day", stepmode="backward"),
                                        dict(count=1, label="1m", step="month", stepmode="backward"),
                                        dict(count=3, label="3m", step="month", stepmode="backward"),
                                        dict(count=6, label="6m", step="month", stepmode="backward"),
                                        dict(step="all", label="All")
                                    ])
                                )
                            ),
                            yaxis=dict(
                                title='Price ($)',
                                gridcolor='rgba(255, 255, 255, 0.1)',
                                showgrid=True,
                                tickformat='.2f',
                                autorange=True  # Ensure proper scaling
                            ),
                            template='plotly_dark',
                            hovermode='x unified',
                            showlegend=True,
                            legend=dict(
                                orientation="h",
                                yanchor="bottom",
                                y=1.02,
                                xanchor="right",
                                x=1
                            ),
                            plot_bgcolor='#0F0904',
                            paper_bgcolor='#0F0904'
                        )
                        
                        # Convert to JSON for template
                        pred_plot_data = json.dumps(pred_fig.to_dict(), cls=PlotlyJSONEncoder)
                        context['pred_plot_data'] = pred_plot_data
                        
                        # Format dates for the prediction table
                        formatted_prediction_data = []
                        for pred in prediction_data:
                            # Convert date from YYYY-MM-DD to DD-MM-YYYY
                            date_obj = datetime.strptime(pred['date'], '%Y-%m-%d')
                            formatted_date = date_obj.strftime('%d-%m-%Y')
                            
                            formatted_prediction_data.append({
                                'date': formatted_date,
                                'predicted_price': pred['predicted_price'],
                                'lower_bound': pred['lower_bound'],
                                'upper_bound': pred['upper_bound']
                            })
                        
                        context['prediction_data'] = formatted_prediction_data
            else:
                context['error'] = f"Could not find data for symbol: {symbol}. Try adding exchange suffix like .BSE or .NSE for Indian stocks."
    
    # Get recent searches for logged-in users
    if request.user.is_authenticated:
        recent_searches = StockSearchHistory.objects.filter(user=request.user).values('symbol').distinct()[:5]
        context['recent_searches'] = recent_searches
    
    return render(request, 'stocks/tracker.html', context)

@login_required
def stock_history(request):
    """View for user's stock search history"""
    searches = StockSearchHistory.objects.filter(user=request.user).order_by('-search_date')
    predictions = StockPrediction.objects.filter(user=request.user).order_by('-prediction_date')
    
    context = {
        'searches': searches,
        'predictions': predictions
    }
    
    return render(request, 'stocks/history.html', context)