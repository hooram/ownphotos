from django.core.management.base import BaseCommand
from django.utils import timezone

from django.core.management import call_command
import time
import os

class Command(BaseCommand):
    help = 'Job scheduler for photo scanning'

    def handle(self, *args, **kwargs):
        while True:
            ts = timezone.now().strftime('%X')
            self.stdout.write("%s Scheduling photo scan" % (ts))
            call_command('scan_photos')
            time.sleep(int(os.environ.get('SCHEDULER_INTERVAL', 300)))



