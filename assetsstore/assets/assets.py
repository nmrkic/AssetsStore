import abc
import os
import uuid
import zipfile
import logging
import requests
import json

logger = logging.getLogger(__name__)


class FileAssets(metaclass=abc.ABCMeta):

    def __init__(self):
        self.local_store = os.getenv("LOCAL_STORE")

    @abc.abstractmethod
    def get_folder(self, path):
        raise NotImplementedError

    @abc.abstractmethod
    def get_file(self, filename):
        raise NotImplementedError

    @abc.abstractmethod
    def get_access(self, filename, seconds):
        raise NotImplementedError

    def put_folder(self, path):
        local_folder = "{}{}".format(self.local_store, path)
        self._put_folder(local_folder)

    def _put_folder(self, path):
        for root, dirs, files in os.walk(path):
            for f in files:
                self.put_file("{}/{}".format(root.replace(self.local_store, ""), f))
            for d in dirs:
                self._put_folder("{}/{}".format(path, d).replace("//", "/"))

    @abc.abstractmethod
    def put_file(self, filename):
        raise NotImplementedError

    def save_and_push(self, file, filename, randomise=True):
        match_path, ext = os.path.splitext(filename)
        saved_filename = filename
        if randomise:
            randomise_name = "{}-{}{}".format(match_path, uuid.uuid4().hex, ext)
            saved_filename = "{}".format(randomise_name)
        full_filename = os.path.realpath(
            "{}{}".format(self.local_store, saved_filename)
        )
        with open(full_filename, "wb") as model_file:
            model_file.write(file.read())

        self.put_file(saved_filename)

        return saved_filename

    @abc.abstractmethod
    def del_file(self, filename, archive=False):
        raise NotImplementedError

    @classmethod
    def get_asset(cls):
        asset = None
        selected = os.getenv("ASSET_STORE")
        for sub_cls in cls.__subclasses__():
            if selected.lower() == sub_cls.__name__.lower():
                asset = sub_cls
        if not asset:
            raise Exception(
                """There is no asset by name '{}' please set environment variable ASSET_STORE to one of the following:
                LocalFiles, ServerFiles, S3Files, AzureFiles, MinioFiles""".format(
                    selected
                )
            )
        return asset()

    def compress(self, file):
        with zipfile.ZipFile(
            file.replace(".csv", ".zip"), "w", zipfile.ZIP_DEFLATED
        ) as zipped:
            zipped.write(file, file.split("/")[-1])
        return file.replace(".csv", ".zip")

    def del_local_file(self, filename):
        local_filename = os.path.realpath("{}{}".format(self.local_store, filename))
        if os.path.exists(local_filename):
            try:
                os.remove(local_filename)
                return True
            except Exception as e:
                logger.exception(
                    "Delete local file failed with error: {}".format(str(e))
                )
        else:
            logger.info("Local file does not exist {}".format(local_filename))
        return False

    def shorten_url(self, url):
        try:
            linkRequest = {
                "destination": url,
                "domain": {"fullName": os.getenv("REBRAND_DOMAIN", "rebrand.ly")},
            }

            requestHeaders = {
                "Content-type": "application/json",
                "apikey": os.getenv("REBRAND_KEY"),
            }

            r = requests.post(
                "https://api.rebrandly.com/v1/links",
                data=json.dumps(linkRequest),
                headers=requestHeaders,
            )

            if r.status_code == requests.codes.ok:
                link = r.json()
                logger.info(link)
                return "https://{}".format(link["shortUrl"])
            else:
                logger.warning(
                    "Failed getting url, code {}. Response {}".format(
                        r.status_code, r.content
                    )
                )
            return False
        except Exception as e:
            logger.warning("Issue getting shorter url. Error {}".format(str(e)))
        return False
