# Generated by Django 5.1.6 on 2025-03-11 16:48
<<<<<<< HEAD

=======
>>>>>>> f546b48ce5036e8d7a60d12d0314cdb4832e5fcb
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tickets', '0014_alter_ticketattachment_file'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ticket',
            name='status',
            field=models.CharField(choices=[('open', 'Open'), ('in_progress', 'In Progress'), ('resolved', 'Resolved'), ('closed', 'Closed'), ('returned', 'Returned'), ('returned_student', 'Returned To Student'), ('returned_officer', 'Returned To Officer')], default='open', max_length=20),
        ),
    ]
