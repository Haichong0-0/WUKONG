from django.core.management.base import BaseCommand
from django.utils import timezone
from tickets.models import Ticket
from datetime import timedelta

class Command(BaseCommand):
    help = 'Close tickets that have not been updated in the last 7 days'

    def handle(self, *args, **kwargs):
        now = timezone.now()
        stale_tickets = Ticket.objects.filter(
            status__in=['open', 'in_progress', 'resolved'],
            updated_at__lt=now - timedelta(days=7)
        )
        count = stale_tickets.update(status='closed')
        self.stdout.write(self.style.SUCCESS(f'Successfully closed {count} stale tickets'))

        urgent_tickets = Ticket.objects.filter(
            status__in=['open', 'in_progress', 'resolved'],
            updated_at__lt=now - timedelta(days=6)
        )
        ucount = urgent_tickets.update(priority='urgent')
        self.stdout.write(self.style.SUCCESS(f'Successfully closed {ucount} stale tickets'))
