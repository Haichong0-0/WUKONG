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
    path('close_ticket/<uuid:ticket_id>/', views.close_ticket, name='close_ticket'),
    path('tickets/table/', views.TicketsTableView.as_view(), name='tickets_table'),
    path("ticket/<uuid:pk>/return/", views.return_ticket, name="return_ticket"),
    path("ticket/<uuid:pk>/supplement/", views.supplement_ticket, name="supplement_ticket"),
    path('ticket/<uuid:ticket_id>/redirect', views.redirect_ticket_page, name='redirect_ticket_page'),
    path('ticket/<uuid:ticket_id>/assign/', views.redirect_ticket, name='redirect_ticket'),
    path('ticket/<uuid:ticket_id>/respond_page/', views.respond_ticket_page, name='respond_ticket_page'),
    path('ticket/<uuid:ticket_id>/respond/', views.respond_ticket, name='respond_ticket'),
    path('ticket/<uuid:ticket_id>/detail/', views.ticket_detail, name='ticket_detail'),
    
]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)