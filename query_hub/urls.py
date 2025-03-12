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
from django.shortcuts import render
from tickets.views import get_user_role, manage_tickets_for_program_officer

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('log_in/', views.LogInView.as_view(), name='log_in'),
    path('log_out/', views.log_out, name='log_out'),
    path('password/', views.PasswordView.as_view(), name='password'),
    path('profile/', views.ProfileUpdateView.as_view(), name='profile'),
    path('tickets/', views.TicketListView.as_view(), name='ticket_list'),
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
    path('ticket/<uuid:ticket_id>/return_page/', views.return_ticket_page, name='return_ticket_page'),
    path('ticket/<uuid:ticket_id>/return_ticket_specailist/', views.return_ticket_specailist, name='return_ticket_specailist'),

    path("ticket/submit/", views.submit_ticket, name="submit_ticket"),
    path('tickets/create/', views.CreateTicketView.as_view(), name='create_ticket'),
    path('dashboard_program_officer/', views.dashboard, name='dashboard_program_officer'),
    path('dashboard_student/', views.dashboard, name='dashboard_student'),
    path('dashboard_specialist/', views.dashboard, name='dashboard_specialist'),
    path('get_user_role/', get_user_role, name='get_user_role'),
    path('manage_tickets_for_program_officer/<uuid:ticket_id>/', views.manage_tickets_for_program_officer, name="manage_tickets_for_program_officer"),

    path('ticket/<uuid:ticket_id>/update_page/', views.update_ticket_page, name='update_ticket_page'),
    path('ticket/<uuid:ticket_id>/update_ticket/', views.update_ticket, name='update_ticket'),
    


]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT) #pragma: no cover