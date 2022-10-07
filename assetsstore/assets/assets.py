import abc
import os
import uuid
import zipfile
import logging
import requests
import json

logger = logging.getLogger(__name__)


class FileAssets(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.local_store = os.getenv("LOCAL_STORE", "")

    @abc.abstractmethod
    def get_folder(self, path):
        raise "Not implemented abstract method"

    @abc.abstractmethod
    def get_size(self, folder):
        raise "Not implemented abstract method"

    @abc.abstractmethod
    def get_file(self, filename):
        raise "Not implemented abstract method"

    def get_access(self, filename, seconds):
        raise "Not implemented abstract method"

    def put_folder(self, path):
        # local_folder = "{}{}".format(self.local_store, path)
        self._put_folder(path)

    def _put_folder(self, path):
        for root, dirs, files in os.walk(path):
            for f in files:
                self.put_file("{}/{}".format(root.replace(self.local_store, ""), f))
            for d in dirs:
                self._put_folder("{}/{}".format(path, d).replace("//", "/"))

    @abc.abstractmethod
    def put_file(self, filename):
        raise "Not implemented abstract method"

    def save_and_push(self, file, filename, randomise=True):
        match_path, ext = os.path.splitext(filename)
        saved_filename = filename
        if randomise:
            randomise_name = '{}-{}{}'.format(match_path, uuid.uuid4().hex, ext)
            saved_filename = '{}'.format(randomise_name)
        full_filename = os.path.realpath("{}{}".format(self.local_store, saved_filename))
        with open(full_filename, 'wb') as model_file:
            model_file.write(file.read())

        self.put_file(saved_filename)

        return saved_filename

    @abc.abstractmethod
    def del_file(self, filename, archive=False):
        raise "Not implemented abstract method"

    @classmethod
    def get_asset(cls):
        asset = None
        selected = os.getenv("ASSET_STORE", "")
        for sub_cls in cls.__subclasses__():
            if selected.lower() == sub_cls.__name__.lower():
                asset = sub_cls
        if not asset:
            raise Exception("""There is no asset by name '{}' please set environment variable ASSET_STORE to one of the following:
                LocalFiles, ServerFiles, S3Files, AzureFiles""".format(selected))
        return asset()

    def compress(self, file):
        with zipfile.ZipFile(file.replace('.csv', '.zip'), 'w', zipfile.ZIP_DEFLATED) as zipped:
            zipped.write(file, file.split('/')[-1])
        return file.replace('.csv', '.zip')

    def del_local_file(self, filename):
        local_filename = os.path.realpath("{}{}".format(self.local_store, filename))
        if os.path.exists(local_filename):
            try:
                os.remove(local_filename)
                return "Deleted"
            except Exception as e:
                logger.exception("Delete local file failed with error: {}".format(str(e)))
        else:
            logger.info("Local file does not exist {}".format(local_filename))
        return "Not Deleted"

    def shorten_url(self, url):
        try:
            linkRequest = {
                "destination": url,
                "domain": {"fullName": os.getenv("REBRAND_DOMAIN", "rebrand.ly")}
                # , "slashtag": "A_NEW_SLASHTAG"
                # , "title": "Rebrandly YouTube channel"
            }

            requestHeaders = {
                "Content-type": "application/json",
                "apikey": os.getenv("REBRAND_KEY"),
                # "workspace": "YOUR_WORKSPACE_ID"
            }

            r = requests.post(
                "https://api.rebrandly.com/v1/links",
                data=json.dumps(linkRequest),
                headers=requestHeaders
            )

            if (r.status_code == requests.codes.ok):
                link = r.json()
                logger.info(link)
                print("Long URL was %s, short URL is %s" % (link["destination"], link["shortUrl"]))
                return "https://{}".format(link['shortUrl'])
            else:
                logger.warn("Failed getting url, code {}. Response {}".format(r.status_code, r.content))
            return None
        except Exception as e:
            logger.warn("Issue getting shorter url. Error {}".format(str(e)))
        return None
