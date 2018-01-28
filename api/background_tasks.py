from api.models import Photo, Person, Face
from config import image_dirs, NEXTCLOUD_USER, NEXTCLOUD_PWD, NEXTCLOUD_CONTACT_ENDPOINT
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
    if fetch_external_people:
        nextcloud_contact_fetching()


def get_all_vcard_links(url , auth):
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

def nextcloud_contact_fetching():
    auth = HTTPBasicAuth(NEXTCLOUD_USER, NEXTCLOUD_PWD)
    url = NEXTCLOUD_CONTACT_ENDPOINT
    contacts_urls = get_all_vcard_links(url, auth)
    for vurl in contacts_urls:
        # Download each vcard
        result = requests.request("GET", vurl, auth=auth, verify=False)
        raw_data = result.content.decode("utf-8")

        # Parse vcard
        vcard = vobject.readOne(raw_data)

        # Retrieve name, uid & photo from vcard
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
                    raise e
                    print("Failed to process photo")

            qs_person = Person.objects.filter(external_id=person_ext_id)
            person = None
            if qs_person.count() == 0:
                person = Person(name=person_name, external_id=person_ext_id)
                person.save()
            else:
                person = qs_person[0]

            if photo_path:
                is_added, is_already_stored, photo = process_photo(photo_path)
                if photo and is_added and not is_already_stored:
                    assume_face_is_person = True # TODO add "assume face from contact pic is contact"
                    if assume_face_is_person:
                        for face in Face.objects.filter(photo=photo):
                            face.person = person
                            face.person_label_is_inferred = False
                            face.save()


# Add external ID to people
# If ext ID not in DB
#       Create people
#       if has picture:
#           add faces
# If in DB
#       Update name TODO
#       if picture
#           remove old face if existing
#           has new faces
# If changes:
# Train model
