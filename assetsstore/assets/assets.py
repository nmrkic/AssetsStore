import abc
import os
import uuid
import zipfile
import logging
import requests
import json
from pydoc import locate

logger = logging.getLogger(__name__)


class FileAssets(metaclass=abc.ABCMeta):
    """
    The `FileAssets` class is an abstract base class that provides
    a common interface for working with different types of file assets.
    It defines abstract methods that need to be implemented by its subclasses.
    The class also provides some common functionality for working with files,
    such as uploading, downloading, and deleting files.
    """

    ASSETS_MAP = {
        "AsyncS3Files": "assetsstore.assets.s3.async_s3_files.AsyncS3Files",
        "S3Files": "assetsstore.assets.s3.s3_files.S3Files",
        "AzureFiles": "assetsstore.assets.azr.azure_files.AzureFiles",
        "LocalFiles": "assetsstore.assets.local.local_files.LocalFiles",
        "ServerFiles": "assetsstore.assets.server.server_files.ServerFiles",
        "MinioFiles": "assetsstore.assets.minio.minio.MinioFiles",
    }

    @abc.abstractmethod
    def get_folder(self, path: str):
        """
        Abstract method that needs to be implemented by subclasses.
        Retrieves a folder from the asset store.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_file(self, filename: str):
        """
        Abstract method that needs to be implemented by subclasses.
        Retrieves a file from the asset store.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_access(self, filename: str, seconds: int):
        """
        Abstract method that needs to be implemented by subclasses.
        Retrieves access to a file for a specified duration.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def check_if_exists(self, path: str):
        """
        Abstract method that needs to be implemented by subclasses.
        Checks if desired object exists.
        """
        raise NotImplementedError

    def put_folder(self, path: str):
        """
        Uploads a folder to the asset store by
        recursively uploading all files and subfolders.
        """
        local_folder = os.path.join(self.local_store, path)
        self._put_folder(local_folder)

    def _put_folder(self, path: str):
        """
        Helper method for uploading a folder and its contents.
        """
        for root, dirs, files in os.walk(path):
            for f in files:
                self.put_file(os.path.join(root.replace(self.local_store, ""), f))
            for d in dirs:
                self._put_folder(os.path.join(path, d).replace("//", "/"))

    @abc.abstractmethod
    def put_file(self, filename: str):
        """
        Abstract method that needs to be implemented by subclasses.
        Uploads a file to the asset store.
        """
        raise NotImplementedError

    def save_and_push(self, file: str, filename: str, randomise: bool = True):
        """
        Saves a file locally and then uploads it to the asset store.
        """
        match_path, ext = os.path.splitext(filename)
        saved_filename = filename
        if randomise:
            randomise_name = "{}-{}{}".format(match_path, uuid.uuid4().hex, ext)
            saved_filename = "{}".format(randomise_name)
        full_filename = os.path.realpath(os.path.join(self.local_store, saved_filename))
        with open(full_filename, "wb") as model_file:
            model_file.write(file.read())

        self.put_file(saved_filename)

        return saved_filename

    @abc.abstractmethod
    def del_file(self, filename: str, archive: bool = False):
        """
        Abstract method that needs to be implemented by subclasses.
        Deletes a file from the asset store.
        """
        raise NotImplementedError

    @classmethod
    def get_asset(cls, **kwargs):
        """
        Class method that returns an instance of the appropriate
        subclass based on the value of the ASSET_STORE environment variable.
        Use **kwargs to override environment variables related to the selected asset
        eg. secret_key=my_key
        """
        selected = os.getenv("ASSET_STORE")
        if selected is None:
            raise Exception("Environment variable ASSET_STORE is not set.")
        if selected not in cls.ASSETS_MAP.keys():
            raise Exception(
                """Invalid ASSET_STORE value '{}'.
                Please set it to one of the following: {}""".format(
                    selected, ", ".join(cls.ASSETS_MAP.keys())
                )
            )
        return locate(cls.ASSETS_MAP[selected])(**kwargs)

    def compress(self, file: str):
        """
        Compresses a file into a ZIP archive.
        """
        with zipfile.ZipFile(
            file.replace(".csv", ".zip"), "w", zipfile.ZIP_DEFLATED
        ) as zipped:
            zipped.write(file, file.split("/")[-1])
        return file.replace(".csv", ".zip")

    def del_local_file(self, filename: str):
        """
        Deletes a file from the local store.
        """
        local_filename = os.path.realpath(os.path.join(self.local_store, filename))
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

    def shorten_url(self, url: str):
        """
        Shortens a URL using the Rebrandly API.
        """
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
