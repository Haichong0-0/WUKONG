"""
URL configuration for query_hub project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path
from tickets import views
from tickets.views import role_based_login_view




urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('log_in/', views.LogInView.as_view(), name='log_in'),
    path('log_out/', views.log_out, name='log_out'),
    path('password/', views.PasswordView.as_view(), name='password'),
    path('profile/', views.ProfileUpdateView.as_view(), name='profile'),
    path('sign_up/', views.SignUpView.as_view(), name='sign_up'),
    path('tickets/', views.TicketListView.as_view(), name='ticket_list'),
    path('tickets/create/', views.CreateTicketView.as_view(), name='create_ticket'),
    path('tickets/<uuid:pk>/', views.TicketDetailView.as_view(), name='ticket_detail'),
    path('login_students/', role_based_login_view, {'role': 'students'}, name='student_login'),
    path('login_program_officers/', role_based_login_view, {'role': 'program_officers'}, name='program_officer_login'),
    path('login_specialists/', role_based_login_view, {'role': 'specialists'}, name='specialist_login'),

]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)