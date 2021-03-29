from assetsstore.assets import FileAssets
import os
# import sys
import logging
from pathlib import Path
from azure.storage.blob import BlockBlobService, BlobPermissions
import datetime as dt

logger = logging.getLogger(__name__)


class AzureFiles(FileAssets):

    def __init__(self):
        self.azure_storage_name = os.getenv("ASSET_ACCESS_KEY", None)
        self.azure_storage_key = os.getenv("ASSET_SECRET_ACCESS_KEY", None)
        self.azure_storage_container = os.getenv("ASSET_LOCATION")
        self.azure_storage_url = os.getenv("ASSET_PUBLIC_URL")

        self.connection = BlockBlobService(
            account_name=self.azure_storage_name,
            account_key=self.azure_storage_key,
        )
        super().__init__()

    def get_size(self, folder):
        size = 0
        # TODO add azure functionality to get size of folder
        return size

    def get_access(self, filename, seconds=0, short=True):
        if not seconds:
            seconds = 60 * 60 * 12  # 12 hours
        sas_url = self.connection.generate_blob_shared_access_signature(
            self.azure_storage_container,
            filename,
            BlobPermissions.READ,
            dt.datetime.utcnow() + dt.timedelta(seconds=seconds)
        )
        response = "{}/{}/{}/{}".format(
            self.azure_storage_url,
            self.azure_storage_container,
            filename,
            sas_url
        )

        return response

    def get_upload_access(self, filename, seconds=0):
        response = None
        # TODO Add get upload access for front end apps to be able to upload images to azure
        return response

    def get_folder(self, path):
        try:
            local_folder = os.path.realpath("{}{}".format(self.local_store, path))
            logger.info("Getting folder from azure {}, into local folder {}".format(path, local_folder))
            blob_list = self.connection.list_blobs(self.azure_storage_container)

            for obj in blob_list:
                try:
                    logger.info("Downloading file {}".format(obj))
                    full_filename = os.path.realpath("{}{}".format(self.local_store, obj))
                    if not os.path.exists(os.path.dirname(full_filename)):
                        os.makedirs(os.path.dirname(full_filename))
                    self.get_file(obj)
                except Exception as e:
                    logger.warn("Error occured downloading file {}, with error: {}".format(str(e), obj))
        except Exception as e:
            logger.warn("Error occured while downloading folder from azure {}".format(str(e)))
            return "Failed"
        return "Downloaded"

    def get_file(self, filename):
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            my_file = Path(full_filename)
            if not my_file.is_file():
                folder_path = Path("/".join(full_filename.split("/")[:-1]))
                folder_path.mkdir(parents=True, exist_ok=True)
                self.connection.get_blob_to_path(self.azure_storage_container, filename, full_filename)
            else:
                logger.info("file already exists at path {}".format(full_filename))
                return "Exists"

        except Exception as e:
            logger.exception("Download file from azure failed with error: {}".format(str(e)))
            return "Failed"
        return "Downloaded"

    def put_file(self, filename):
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            self.connection.create_blob_from_path(self.azure_storage_container, filename, full_filename)
            return "Uploaded"
        except Exception as e:
            logger.exception("Upload file to azure failed with error: {}".format(str(e)))
            return "Failed"

    def del_file(self, filename, archive=False):
        try:
            self.connection.delete_blob(self.azure_storage_container, filename, snapshot=None)
        except Exception as e:
            logger.exception("Delete file from azure failed with error: {}".format(str(e)))
            return "Not Deleted"
        return "Deleted"
