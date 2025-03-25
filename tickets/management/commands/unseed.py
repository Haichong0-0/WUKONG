from django.core.management.base import BaseCommand, CommandError
from tickets.models import *

class Command(BaseCommand):
    """Build automation command to unseed the database."""
    
    help = "Removes all non-staff users and related ticket data from the database."

    def handle(self, *args, **options):
        """Unseed the database."""

        TicketAttachment.objects.all().delete()
        TicketActivity.objects.all().delete()
        Response.objects.all().delete()
        AITicketProcessing.objects.all().delete()
        MergedTicket.objects.all().delete()
        DailyTicketClosureReport.objects.all().delete()
        Ticket.objects.all().delete()
        User.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Successfully unseeded the database."))