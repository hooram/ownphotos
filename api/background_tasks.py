from api.models import Photo, Person, Face, get_unknown_person
from config import image_dirs, NEXTCLOUD_USER, NEXTCLOUD_PWD, NEXTCLOUD_CONTACT_ENDPOINT, assume_face_is_person, fetch_external_person
from requests.auth import HTTPBasicAuth
from lxml import etree
from urllib.parse import urlparse
import io
from PIL import Image
import requests
import vobject
import base64
from api.directory_watcher import process_photo
import tempfile

def generate_captions():
    photos = Photo.objects.filter(search_captions=None)
    print('%d photos to be processed for caption generation'%photos.count())
    for photo in photos:
        photo._generate_captions()
        photo.save()

def geolocate():
    photos = Photo.objects.filter(geolocation_json=None)
    print('%d photos to be geolocated'%photos.count())
    for photo in photos:
        photo._geolocate_mapzen()

def fetch_external_people():
    if fetch_external_person:
        # For now it only support one fetcher strategy
        # TODO allow implementation of others fetchers by providing a way
        # to choose between strategies
        NextcloudContactFetcher().fetch_persons()

class PersonFetcher(object):

    def fetch_persons(self):
        """
        Should be overriden by every fetching strategy
        """
        raise NotImplementError

    def handle_person(self, person_name, person_external_id, photo_path=None):
        # Retrieve of create person
        qs_person = Person.objects.filter(external_id=person_external_id)
        person = None
        if qs_person.count() == 0:
            person = Person(name=person_name, external_id=person_external_id)
            person.save()
        else:
            person = qs_person[0]
            if person.name != person_name:
                person.name = person_name
                person.save()

        # If a photo is provided process it
        if photo_path:
            is_added, is_already_stored, photo = process_photo(photo_path)
            # If it's a newly added photo then assign faces to the person
            # provided that the corresponding flag is activated
            if photo and is_added and not is_already_stored and assume_face_is_person:
                unknown_person = get_unknown_person()[0]
                for face in Face.objects.filter(photo=photo):
                    if face.person == unknown_person:
                        face.person = person
                        face.person_label_is_inferred = False
                        face.save()

class NextcloudContactFetcher(PersonFetcher):
    """
    PoC of a Carddav client for Nextcloud

    """
    USER = NEXTCLOUD_USER
    PASSWORD = NEXTCLOUD_PWD
    URL = NEXTCLOUD_CONTACT_ENDPOINT

    def fetch_persons(self):
        auth = HTTPBasicAuth(NEXTCLOUD_USER, NEXTCLOUD_PWD)
        url = NEXTCLOUD_CONTACT_ENDPOINT
        contacts_urls = self._get_all_vcard_links(url, auth)
        for vurl in contacts_urls:
            # Download each vcard
            result = requests.request("GET", vurl, auth=auth, verify=False)
            raw_data = result.content.decode("utf-8")
            # Parse vcard
            vcard = vobject.readOne(raw_data)
            # Retrieve name, nextcloud uid & photo from vcard
            if "uid" in vcard.contents and "fn" in vcard.contents:
                person_ext_id = vcard.uid.value
                person_name = vcard.fn.value.encode("utf-8")
                photo_path = None
                if "photo" in vcard.contents:
                    try:
                        tmp_dir = tempfile.gettempdir()
                        image_data = vcard.photo.value
                        image = Image.open(io.BytesIO(image_data))
                        tmp_pic = "{}/temp.jpg".format(tmp_dir)
                        image.save(tmp_pic)
                        photo_path = tmp_pic
                    except BaseException as e :
                        print("Failed to process photo", e.message)
                self.handle_person(person_name, person_ext_id, photo_path)

    def _get_all_vcard_links(self, url , auth):
        """
        Given an url & an auth token retrieve url linking towards all contacts
        """
        baseurl = urlparse(url).scheme + '://' +urlparse(url).netloc
        r = requests.request('PROPFIND', url, auth=auth, verify=False)
        root = etree.XML(r.content)
        vcardUrlList=[]
        for record in root.xpath(".//d:response", namespaces={"d" : "DAV:"}):
            vcard_links = record.xpath(".//d:href", namespaces={"d" : "DAV:"})
            for link in vcard_links:
                if ".vcf" in link.text:
                    vcardUrlList.append(baseurl + '/' + link.text)
        return vcardUrlList
