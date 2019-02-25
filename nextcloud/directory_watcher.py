from api.models import (Photo, Person, LongRunningJob)
from django_rq import job
import owncloud as nextcloud
import pathlib
import ipdb
import os
from ownphotos import settings
import os
import datetime
import hashlib
import pytz
import time

from tqdm import tqdm
from config import image_dirs

import api.util as util

import ipdb
from django_rq import job
import time
import numpy as np
import rq


def collect_photos(nc, path, photos):
    for x in nc.list(path):
        if x.path.lower().endswith('.jpg'):
            photos.append(x.path)
        elif x.is_dir():
            collect_photos(nc, x.path, photos)


@job
def scan_photos(user):
    lrj = LongRunningJob(
        started_by=user,
        job_id=rq.get_current_job().id,
        started_at=datetime.datetime.now(),
        job_type=LongRunningJob.JOB_SCAN_PHOTOS)
    lrj.save()

    nc = nextcloud.Client(user.nextcloud_server_address)
    nc.login(user.nextcloud_username, user.nextcloud_app_password)

    scan_directory = user.nextcloud_scan_directory
    photos = []

    image_paths = []

    collect_photos(nc, scan_directory, photos)

    for photo in tqdm(photos):
        local_dir = os.path.join(settings.BASE_DIR, 'nextcloud_media',
                                 user.username,
                                 os.path.dirname(photo)[1:])
        local_path = os.path.join(settings.BASE_DIR, 'nextcloud_media',
                                  user.username, photo[1:])
        image_paths.append(local_path)

        if not os.path.exists(local_dir):
            pathlib.Path(local_dir).mkdir(parents=True, exist_ok=True)

        if not os.path.exists(local_path):
            nc.get_file(photo, local_path)

    try:

        # for image_dir in image_dirs:
        #     image_paths.extend([
        #         os.path.join(dp, f) for dp, dn, fn in os.walk(image_dir)
        #         for f in fn
        #     ])

        image_paths.sort()

        existing_hashes = [p.image_hash for p in Photo.objects.all()]

        image_paths_to_add = []
        for image_path in tqdm(image_paths):
            # hash_md5 = hashlib.md5()
            # with open(image_path, "rb") as f:
            #     for chunk in iter(lambda: f.read(4096), b""):
            #         hash_md5.update(chunk)
            # image_hash = hash_md5.hexdigest()
            # if image_hash not in existing_hashes:
            #     image_paths_to_add.append(image_path)

            if not Photo.objects.filter(image_path=image_path).exists():
                # ipdb.set_trace()
                image_paths_to_add.append(image_path)

        added_photo_count = 0
        already_existing_photo = 0
        counter = 0
        for image_path in tqdm(image_paths_to_add):
            counter += 1
            if image_path.lower().endswith('.jpg'):
                try:
                    img_abs_path = image_path

                    start = datetime.datetime.now()
                    hash_md5 = hashlib.md5()
                    with open(img_abs_path, "rb") as f:
                        for chunk in iter(lambda: f.read(4096), b""):
                            hash_md5.update(chunk)
                    image_hash = hash_md5.hexdigest() + str(user.id)
                    elapsed = (datetime.datetime.now() - start).total_seconds()
                    util.logger.info('generating md5 took %.2f, image_hash: %s'
                                     % (elapsed, image_hash))

                    # qs = Photo.objects.filter(image_hash=image_hash)

                    photo_exists = Photo.objects.filter(
                        image_hash=image_hash).exists()

                    if not photo_exists:
                        photo = Photo(image_path=img_abs_path, owner=user)
                        photo.added_on = datetime.datetime.now().replace(
                            tzinfo=pytz.utc)
                        photo.geolocation_json = {}
                        photo._generate_md5()
                        photo.save()

                        start = datetime.datetime.now()
                        photo._generate_thumbnail()
                        elapsed = (
                            datetime.datetime.now() - start).total_seconds()
                        util.logger.info('thumbnail get took %.2f' % elapsed)

                        start = datetime.datetime.now()
                        photo._generate_captions()
                        elapsed = (
                            datetime.datetime.now() - start).total_seconds()
                        util.logger.info(
                            'caption generation took %.2f' % elapsed)

                        start = datetime.datetime.now()
                        photo._save_image_to_db()
                        elapsed = (
                            datetime.datetime.now() - start).total_seconds()
                        util.logger.info('image save took %.2f' % elapsed)

                        start = datetime.datetime.now()
                        photo._extract_exif()
                        photo.save()
                        elapsed = (
                            datetime.datetime.now() - start).total_seconds()
                        util.logger.info('exif extraction took %.2f' % elapsed)

                        start = datetime.datetime.now()
                        photo._geolocate_mapbox()
                        photo.save()
                        elapsed = (
                            datetime.datetime.now() - start).total_seconds()
                        util.logger.info('geolocation took %.2f' % elapsed)

                        start = datetime.datetime.now()
                        photo._add_to_album_place()
                        photo.save()
                        elapsed = (
                            datetime.datetime.now() - start).total_seconds()
                        util.logger.info(
                            'add to AlbumPlace took %.2f' % elapsed)

                        start = datetime.datetime.now()
                        photo._extract_faces()
                        elapsed = (
                            datetime.datetime.now() - start).total_seconds()
                        util.logger.info('face extraction took %.2f' % elapsed)

                        start = datetime.datetime.now()
                        photo._add_to_album_date()
                        elapsed = (
                            datetime.datetime.now() - start).total_seconds()
                        util.logger.info(
                            'adding to AlbumDate took %.2f' % elapsed)

                        start = datetime.datetime.now()
                        photo._add_to_album_thing()
                        elapsed = (
                            datetime.datetime.now() - start).total_seconds()
                        util.logger.info(
                            'adding to AlbumThing took %.2f' % elapsed)

                        added_photo_count += 1
                        util.logger.info(
                            "Image processed: {}".format(img_abs_path))
                    else:
                        already_existing_photo += 1
                        util.logger.info("photo already exists in db")
                        print("photo already exists in db %s" % img_abs_path)
                except Exception as e:
                    try:
                        util.logger.error(
                            "Could not load image {}. reason: {}".format(
                                image_path, e.__repr__()))
                    except:
                        util.logger.error(
                            "Could not load image {}".format(image_path))

        util.logger.info("Added {}/{} photos".format(
            added_photo_count,
            len(image_paths) - already_existing_photo))

        lrj = LongRunningJob.objects.get(job_id=rq.get_current_job().id)
        lrj.finished = True
        lrj.finished_at = datetime.datetime.now()
        lrj.result = {"new_photo_count": added_photo_count}
        lrj.save()
    except:
        lrj = LongRunningJob.objects.get(job_id=rq.get_current_job().id)
        lrj.finished = True
        lrj.failed = True
        lrj.finished_at = datetime.datetime.now()
        lrj.result = {"new_photo_count": 0}
        lrj.save()
    return {"new_photo_count": added_photo_count, "status": True}
