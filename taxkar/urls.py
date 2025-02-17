from django.urls import path
from . import views, auth_views, invoice_views

urlpatterns = [
    path('', views.home, name='home'),

    # Authentication URLs
    path('auth/login/', auth_views.login_view, name='login'),
    path('auth/register/', auth_views.register_view, name='register'),
    path('auth/phone-login/', auth_views.phone_login_view, name='phone_login'),
    path('auth/google-login/', auth_views.google_login_view, name='google_login'),
    path('auth/logout/', auth_views.logout_view, name='logout'),

    # Calculator URLs
    path('tax/calculate/', views.calculate_tax, name='calculate_tax'),
    path('gst/calculate/', views.calculate_gst, name='calculate_gst'),
    path('forex/', views.forex_converter, name='forex_converter'),
    path('history/', views.history_view, name='history'),

    # Invoice URLs
    path('invoices/', invoice_views.invoice_list, name='invoice_list'),
    path('invoices/<int:id>/', invoice_views.invoice_detail, name='invoice_detail'),
    path('invoices/<int:id>/download/', invoice_views.download_invoice, name='download_invoice'),
]

