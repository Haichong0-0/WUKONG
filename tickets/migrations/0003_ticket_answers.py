# Generated by Django 5.1.5 on 2025-02-04 15:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0002_department_user_role_user_department_ticket_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='ticket',
            name='answers',
            field=models.TextField(blank=True, help_text='All responses to the ticket.', null=True),
        ),
    ]
