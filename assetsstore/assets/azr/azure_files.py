from assetsstore.assets import FileAssets
import os

import logging
from pathlib import Path
from azure.storage.blob import BlockBlobService, BlobPermissions
import datetime as dt

logger = logging.getLogger(__name__)


class AzureFiles(FileAssets):
    """
    A class representing Azure Files in the Assets Store.
    """

    def __init__(
        self,
        access_key=os.getenv("ASSET_ACCESS_KEY"),
        secret_key=os.getenv("ASSET_SECRET_ACCESS_KEY"),
        bucket_name=os.getenv("ASSET_LOCATION"),
        host=os.getenv("ASSET_PUBLIC_URL"),
        local_store=os.getenv("LOCAL_STORE"),
    ):
        self.azure_storage_name = access_key
        self.azure_storage_key = secret_key
        self.azure_storage_container = bucket_name
        self.azure_storage_url = host
        self.local_store = local_store
        self.connection = BlockBlobService(
            account_name=self.azure_storage_name,
            account_key=self.azure_storage_key,
        )

    def check_if_exists(self, path: str):
        pass

    def get_access(self, filename: str, seconds: int = 0, *args, **kwargs):
        """
        Get the access URL for a file in Azure.

        Args:
            filename (str): The name of the file.
            seconds (int, optional): The number of seconds
                the access URL will be valid for.
                Defaults to 0, which means the URL will be valid for 12 hours.

        Returns:
            str: The access URL for the file.
        """
        if not seconds:
            seconds = 60 * 60 * 12  # 12 hours
        sas_url = self.connection.generate_blob_shared_access_signature(
            container_name=self.azure_storage_container,
            blob_name=filename,
            permission=BlobPermissions.READ,
            expiry=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=seconds),
        )
        response = "{}/{}/{}?{}".format(
            self.azure_storage_url, self.azure_storage_container, filename, sas_url
        )

        return response

    def get_folder(self, path: str):
        """
        Download a folder from Azure.

        Args:
            path (str): The path of the folder in Azure.

        Returns:
            bool: True if the folder was downloaded successfully, False otherwise.
        """
        try:
            local_folder = os.path.realpath("{}{}".format(self.local_store, path))
            logger.info(
                "Getting folder from azure {}, into local folder {}".format(
                    path, local_folder
                )
            )
            blob_list = self.connection.list_blobs(self.azure_storage_container)

            for obj in blob_list:
                try:
                    logger.info("Downloading file {}".format(obj))
                    full_filename = os.path.realpath(
                        "{}{}".format(self.local_store, obj)
                    )
                    if not os.path.exists(os.path.dirname(full_filename)):
                        os.makedirs(os.path.dirname(full_filename))
                    self.get_file(obj)
                except Exception as e:
                    logger.warning(
                        "Error occurred downloading file {}, with error: {}".format(
                            str(e), obj
                        )
                    )
        except Exception as e:
            logger.warning(
                "Error occurred while downloading folder from Azure {}".format(str(e))
            )
            return False
        return True

    def get_file(self, filename: str):
        """
        Download a file from Azure.

        Args:
            filename (str): The name of the file in Azure.

        Returns:
            bool: True if the file was downloaded successfully, False otherwise.
        """
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            my_file = Path(full_filename)
            if not my_file.is_file():
                folder_path = Path("/".join(full_filename.split("/")[:-1]))
                folder_path.mkdir(parents=True, exist_ok=True)
                self.connection.get_blob_to_path(
                    self.azure_storage_container, filename, full_filename
                )
            else:
                logger.info("file already exists at path {}".format(full_filename))
                return True

        except Exception as e:
            logger.exception(
                "Download file from Azure failed with error: {}".format(str(e))
            )
            return False
        return True

    def put_file(self, filename: str):
        """
        Upload a file to Azure.

        Args:
            filename (str): The name of the file to upload.

        Returns:
            bool: True if the file was uploaded successfully, False otherwise.
        """
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            self.connection.create_blob_from_path(
                self.azure_storage_container, filename, full_filename
            )
            return True
        except Exception as e:
            logger.exception(
                "Upload file to Azure failed with error: {}".format(str(e))
            )
            return False

    def del_file(self, filename: str, *args, **kwargs):
        """
        Delete a file from Azure.

        Args:
            filename (str): The name of the file to delete.

        Returns:
            bool: True if the file was deleted successfully, False otherwise.
        """
        try:
            self.connection.delete_blob(
                self.azure_storage_container, filename, snapshot=None
            )
        except Exception as e:
            logger.exception(
                "Delete file from Azure failed with error: {}".format(str(e))
            )
            return False
        return True
