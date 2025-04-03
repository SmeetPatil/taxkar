from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from huggingface_hub import InferenceClient
from django.conf import settings
from django.urls import reverse
import json
import re

# Initialize HuggingFace client
client = InferenceClient(token=settings.HUGGINGFACE_API_KEY)

SYSTEM_PROMPT = """You are TaxKar's AI Financial Assistant. When users ask about:

1. Stock prices or market data:
   - First provide a brief, factual answer about the topic
   - Then direct them to TaxKar's Stock Tracker at /stock_tracker/
   - Say "For real-time data and detailed analysis, you can use our Stock Tracker tool"

2. Currency exchange rates:
   - First provide a brief, factual answer about the topic
   - Then direct them to TaxKar's Forex Converter at /converter/
   - Say "For current exchange rates and conversion, you can use our Forex Converter tool"

3. Tax calculations:
   - First provide a brief, factual answer about the topic
   - Then direct them to TaxKar's Tax Calculator at /tax_calculator/
   - Say "For precise calculations based on your specific situation, you can use our Tax Calculator tool"

4. GST related queries:
   - First provide a brief, factual answer about the topic
   - Then direct them to TaxKar's GST Calculator at /gst_calculator/
   - Say "For accurate GST calculations with the latest rates, you can use our GST Calculator tool"

Never recommend external websites. Always direct users to TaxKar's tools and features after providing helpful information."""

# List of finance-related keywords to check if a query is finance-related
FINANCE_KEYWORDS = [
    'tax', 'taxes', 'taxation', 'income tax', 'gst', 'goods and services tax',
    'stock', 'stocks', 'share', 'shares', 'market', 'investment', 'invest',
    'mutual fund', 'equity', 'bond', 'bonds', 'dividend', 'forex', 'currency',
    'exchange rate', 'dollar', 'rupee', 'euro', 'yen', 'pound', 'finance',
    'financial', 'money', 'banking', 'bank', 'loan', 'interest', 'credit',
    'debit', 'saving', 'savings', 'budget', 'budgeting', 'expense', 'expenses',
    'income', 'salary', 'pension', 'retirement', 'insurance', 'trading', 'trader',
    'portfolio', 'asset', 'liability', 'debt', 'profit', 'loss', 'revenue',
    'capital gain', 'dividend', 'yield', 'return', 'roi', 'ipo', 'inflation',
    'deflation', 'recession', 'bull market', 'bear market', 'crypto', 'cryptocurrency',
    'bitcoin', 'ethereum', 'nifty', 'sensex', 'bse', 'nse', 'nasdaq', 'dow jones',
    's&p', 'standard & poor', 'balance sheet', 'p&l', 'profit and loss', 'accounting',
    'audit', 'auditing', 'wealth', 'net worth', 'asset allocation', 'diversification',
    'sip', 'systematic investment plan', 'ppf', 'provident fund', 'nps', 'pension scheme',
    'deduction', 'exemption', 'section 80c', 'tds', 'tax deducted at source', 'itr',
    'income tax return', 'capital', 'liquidity', 'solvency', 'leverage', 'mortgage',
    'emi', 'equated monthly installment', 'fd', 'fixed deposit', 'rd', 'recurring deposit'
]

def is_finance_related(query):
    """Check if the query is related to finance based on keywords"""
    query = query.lower()
    return any(keyword in query for keyword in FINANCE_KEYWORDS)

def chatbot_view(request):
    """
    Render the chatbot interface
    """
    return render(request, 'chat/chatbot.html')

@csrf_exempt
def chat_message(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()

            if not user_message:
                return JsonResponse({'response': 'Please enter a message.'})
            
            # Check if the query is finance-related
            if not is_finance_related(user_message):
                return JsonResponse({
                    'response': "I'm specialized in financial topics like taxes, investments, stock markets, and financial planning. For non-financial questions, I recommend using a general search engine or consulting a relevant expert. How can I assist you with your financial queries today?"
                })

            # Add website context to the prompt
            context_prompt = f"""User Question: {user_message}

Remember:
- First provide a helpful, factual answer to the user's question
- Then, if appropriate, direct users to TaxKar's tools:
  - Stock prices → /stock_tracker/
  - Exchange rates → /converter/
  - Tax calculations → /tax_calculator/
  - GST queries → /gst_calculator/
- Never suggest external websites
- Always provide value before redirecting

Your response:"""

            # Get response from HuggingFace
            response = client.text_generation(
                prompt=context_prompt,
                model="mistralai/Mistral-7B-Instruct-v0.2",
                max_new_tokens=500,
                temperature=0.7,
                repetition_penalty=1.2
            )
            
            print(f"Original response: {response}")  # Debug log
            
            # Fix escaped backslashes in the response
            processed_response = response.replace('/stock\\_tracker/', '/stock_tracker/')
            
            # Define replacements as a dictionary for cleaner code
            replacements = {
                '/stock_tracker/': f'<a href="{reverse("stock_tracker")}">Stock Tracker</a>',
                '/converter/': f'<a href="{reverse("converter")}">Forex Converter</a>',
                '/tax_calculator/': f'<a href="{reverse("calculate_tax")}">Tax Calculator</a>',
                '/gst_calculator/': f'<a href="{reverse("calculate_gst")}">GST Calculator</a>'
            }
            
            # Apply URL replacements
            for pattern, replacement in replacements.items():
                processed_response = processed_response.replace(pattern, replacement)
            
            print(f"Processed response: {processed_response}")  # Debug log

            return JsonResponse({'response': processed_response})

        except Exception as e:
            print(f"Error in chat_message: {str(e)}")
            return JsonResponse({
                'response': 'I apologize, but I encountered an error. Please try again.'
            })

    return JsonResponse({'response': 'Invalid request method'}, status=405)