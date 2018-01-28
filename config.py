# add paths of the directories where your photos live.
# it will not look for photos recursively, so you might want to add subdirectories as well.
import os

image_dirs = [
	'/data',
]

mapzen_api_key = os.environ['MAPZEN_API_KEY']

# Person fetching option
fetch_external_person = os.environ['FETCH_PERSONS'] == "1"
assume_face_is_person = os.environ['FACE_IS_PERSON'] == "1"

NEXTCLOUD_USER = os.environ['NEXTCLOUD_USER']
NEXTCLOUD_PWD = os.environ['NEXTCLOUD_PWD']
NEXTCLOUD_CONTACT_ENDPOINT = os.environ['NEXTCLOUD_CONTACT_ENDPOINT']
