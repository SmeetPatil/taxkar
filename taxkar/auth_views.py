from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.exceptions import ValidationError
from .models import UserProfile
from google.oauth2 import id_token
from google.auth.transport import requests
import random
from django.conf import settings
import jwt
from datetime import datetime, timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import login
from twilio.rest import Client
from .models import PhoneVerification
from django.conf import settings


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Invalid credentials')

    return render(request, 'auth/login.html')


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')

        if password1 != password2:
            messages.error(request, 'Passwords do not match')
            return render(request, 'auth/register.html')

        try:
            user = User.objects.create_user(username=username,
                                            email=email,
                                            password=password1)
            UserProfile.objects.create(user=user)
            login(request, user)
            return redirect('home')
        except ValidationError as e:
            messages.error(request, str(e))
        except:
            messages.error(request, 'Error creating account')

    return render(request, 'auth/register.html')


def phone_login_view(request):
    if request.method == 'POST':
        phone = request.POST.get('phone')
        if 'otp' in request.POST:
            # Verify OTP
            stored_otp = request.session.get('phone_otp')
            if stored_otp and stored_otp == request.POST.get('otp'):
                try:
                    profile = UserProfile.objects.get(phone_number=phone)
                    login(request, profile.user)
                    del request.session['phone_otp']
                    return redirect('home')
                except UserProfile.DoesNotExist:
                    # Create new user with phone
                    user = User.objects.create_user(
                        username=f"phone_user_{phone}",
                        password=str(random.randint(100000, 999999))
                    )
                    UserProfile.objects.create(
                        user=user,
                        phone_number=phone
                    )
                    login(request, user)
                    return redirect('home')
            else:
                messages.error(request, 'Invalid OTP')
        else:
            # Generate and send OTP
            otp = str(random.randint(100000, 999999))
            request.session['phone_otp'] = otp
            # In production, integrate with SMS service here
            messages.success(request, f'OTP sent! (Dev mode: {otp})')
            return render(request, 'auth/phone_verify.html', {'phone': phone})

    return render(request, 'auth/phone_login.html')


def google_login_view(request):
    if request.method == 'POST':
        token = request.POST.get('credential')
        try:
            idinfo = id_token.verify_oauth2_token(
                token, requests.Request(), settings.GOOGLE_CLIENT_ID)

            email = idinfo['email']
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                user = User.objects.create_user(
                    username=email.split('@')[0],
                    email=email,
                    password=str(random.randint(100000, 999999))
                )
                UserProfile.objects.create(
                    user=user,
                    google_id=idinfo['sub']
                )

            login(request, user)
            return redirect('home')
        except ValueError:
            messages.error(request, 'Invalid Google token')

    return render(request, 'auth/login.html')

'''
# Replace MessageBird with Vonage
try:
    import vonage
except ImportError:
    vonage = None

def phone_login(request):
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')

        # Generate verification code
        code = PhoneVerification.generate_code()
        verification = PhoneVerification.objects.create(
            phone_number=phone_number,
            verification_code=code
        )

        # For development, always show the code in the UI
        if settings.DEBUG:
            messages.info(request, f'Development mode: Your verification code is {code}')
            
        # Try to send SMS via Vonage if not in DEBUG mode
        if not settings.DEBUG and vonage:
            try:
                client = vonage.Client(key=settings.VONAGE_API_KEY, secret=settings.VONAGE_API_SECRET)
                sms = vonage.Sms(client)
                
                response = sms.send_message({
                    'from': 'TaxKar',
                    'to': phone_number,
                    'text': f'Your TaxKar verification code is {code}'
                })
                
                if response["messages"][0]["status"] == "0":
                    messages.success(request, 'Verification code sent successfully!')
                else:
                    messages.warning(request, f'Error sending SMS: {response["messages"][0]["error-text"]}')
                    
            except Exception as e:
                print(f"Vonage error: {e}")
                messages.warning(request, 'Could not send SMS. Using development mode instead.')

        # Store phone number in session for verification page
        request.session['phone_number'] = phone_number
        return redirect('verify_code')

    return render(request, 'auth/phone_login.html')


'''
def phone_login(request):
    if request.method == 'POST':
        phone_number = request.POST.get('phone_number')

        # Generate verification code
        code = PhoneVerification.generate_code()
        PhoneVerification.objects.create(
            phone_number=phone_number,
            verification_code=code
        )

        # Send SMS via Twilio
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f'Your verification code is {code}',
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )

        # Store phone number in session for verification page
        request.session['phone_number'] = phone_number
        return redirect('verify_code')

    return render(request, 'auth/phone_login.html')


def verify_code(request):
    if request.method == 'POST':
        phone_number = request.session.get('phone_number')
        code = request.POST.get('code')

        verification = PhoneVerification.objects.filter(
            phone_number=phone_number,
            verification_code=code
        ).first()

        if verification:
            # Check if user exists, otherwise create
            user, created = User.objects.get_or_create(username=phone_number)

            # Specify the authentication backend
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')

            # Store the phone number in session for display
            request.session['login_method'] = 'phone'
            request.session['phone_number_display'] = phone_number

            # Redirect to home
            return redirect('home')  # Assuming 'home' is your URL name

    return render(request, 'auth/verify_code.html')


def logout_view(request):
    logout(request)
    return redirect('home')