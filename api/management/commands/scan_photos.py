from django.core.management.base import BaseCommand
from django.utils import timezone

from api.models import User
from api.directory_watcher import scan_photos
from rest_framework.response import Response

class Command(BaseCommand):
    help = 'Scans directories of all users who have auto_scan enabled'

    def handle(self, *args, **kwargs):
        ts = timezone.now().strftime('%X')
        users = User.objects.filter(auto_scan=True)
        for user in users:
            self.stdout.write("%s Starting photo scan for user %s" % (ts, user))
            res = scan_photos.delay(user)
            print("Job status: %s" % Response({'status': True, 'job_id': res.id}))



