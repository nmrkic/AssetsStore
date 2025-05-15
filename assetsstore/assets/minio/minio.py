from datetime import timedelta
from assetsstore.assets import FileAssets
import os
import logging
from pathlib import Path
from minio import Minio
from urllib.parse import urlunsplit
from .progress import Progress

logger = logging.getLogger(__name__)


class MinioFiles(FileAssets):
    """
    A class for interacting with Minio file storage.

    This class provides methods for managing files and folders in a Minio bucket.

    Attributes:
        access_key (str): The access key for the Minio server.
        secret_key (str): The secret access key for the Minio server.
        bucket_name (str): The name of the bucket in the Minio server.
        host (str): The host URL of the Minio server.
        tls_enabled (bool): Whether TLS encryption is enabled for the Minio server.
        client (Minio): The Minio client object for interacting with the server.

    """

    def __init__(
        self,
        access_key=os.getenv("ASSET_ACCESS_KEY"),
        secret_key=os.getenv("ASSET_SECRET_ACCESS_KEY"),
        bucket_name=os.getenv("ASSET_LOCATION"),
        bucket_region=os.getenv("ASSET_REGION"),
        host=os.getenv("ASSET_PUBLIC_URL", "localhost:9000"),
        tls_enabled=os.getenv("ASSET_TLS_ENABLED", False),
        local_store=os.getenv("LOCAL_STORE"),
    ):
        self.access_key = access_key
        self.secret_key = secret_key
        self.bucket_name = bucket_name
        self.host = host
        self.tls_enabled = tls_enabled
        self.client = Minio(
            self.host,
            self.access_key,
            self.secret_key,
            secure=self.tls_enabled,
            region=bucket_region,
        )
        self.local_store = local_store

    def check_if_exists(self, path: str):
        """
        Checks if desired object exists.
        Args:
            path (str): The path in the Minio bucket.

        Returns:
            bool: True if file exists, False otherwise.
        """
        response = None
        try:
            response = self.client.get_object(self.bucket_name, path)
            success = True
        except Exception as e:
            success = False
            logger.warning("Cannot access bucket object. Exception {}".format(str(e)))
        if response:
            response.close()
            response.release_conn()
        return success

    def get_size(self, folder: str):
        """
        Get the total size of a folder in the Minio bucket.

        Args:
            folder (str): The folder path in the Minio bucket.

        Returns:
            int: The total size of the folder in bytes.

        """
        size = 0
        try:
            for obj in self.client.list_objects(
                self.bucket_name, prefix=folder, recursive=True
            ):
                size += obj.size
        except Exception as e:
            logger.exception(
                "Cannot get size of the S3 bucket folder. Exception: {}".format(str(e))
            )
        return size

    def get_access(
        self,
        filename: str,
        seconds: int = 0,
        short=False,
        download_filename: str = "",
    ):
        """
        Get the access URL for a file in the Minio bucket.

        Args:
            filename (str): The name of the file in the Minio bucket.
            seconds (int, optional): The number of seconds the access URL should be valid for. Defaults to 0.
            short (bool, optional): Whether to generate a short URL using a URL shortening service. Defaults to False.

        Returns:
            str: The access URL for the file.

        """
        response = None
        try:
            if not download_filename:
                download_filename = filename
            if short:
                base_url = self.client._base_url._url
                base_url = urlunsplit(base_url)
                response = f"{base_url}/{self.bucket_name}/{filename}"
                short_url = self.shorten_url(response)
                if short_url:
                    response = short_url
            else:
                response = self.client.presigned_get_object(
                    self.bucket_name,
                    filename,
                    response_headers={
                        "response-content-disposition": f"attachment;filename={download_filename}"
                    },
                    expires=timedelta(seconds=seconds if seconds else 604800),
                )
        except Exception as e:
            logger.exception(
                "Not able to give access to {} for {} seconds. Exception {}".format(
                    filename, seconds, str(e)
                )
            )
        return response

    def get_upload_access(self, filename: str, seconds: int = 0):
        """
        Get the access URL for uploading a file to the Minio bucket.

        Args:
            filename (str): The name of the file to be uploaded.
            seconds (int, optional): The number of seconds the access URL should be valid for. Defaults to 0.

        Returns:
            str: The access URL for uploading the file.

        """
        response = None
        try:
            response = self.client.presigned_put_object(
                self.bucket_name,
                filename,
                expires=timedelta(seconds=seconds if seconds else 604800),
            )
        except Exception as e:
            logger.exception(
                "Not able to give access to {} for {} seconds. Exception {}".format(
                    filename, seconds, str(e)
                )
            )
            return False
        return response

    def get_folder(self, path: str):
        """
        Download a folder from the Minio bucket.

        Args:
            path (str): The folder path in the Minio bucket.

        Returns:
            bool: True if the folder is downloaded successfully, False otherwise.

        """
        try:
            local_folder = os.path.realpath("{}{}".format(self.local_store, path))
            logger.info(
                "Getting folder from minio s3 {}, into local folder {}".format(
                    path, local_folder
                )
            )
            for obj in self.client.list_objects(
                self.bucket_name, prefix=path, recursive=True
            ):
                try:
                    logger.info("Downloading file {}".format(obj._object_name))
                    full_filename = os.path.realpath(
                        "{}{}".format(self.local_store, obj._object_name)
                    )
                    if not os.path.exists(os.path.dirname(full_filename)):
                        os.makedirs(os.path.dirname(full_filename))
                    self.get_file(obj)
                except Exception as e:
                    logger.warning(
                        "Error occured downloading file {}, with error: {}".format(
                            str(e), obj._object_name
                        )
                    )
        except Exception as e:
            logger.warning(
                "Error occured while downloading folder from s3 minio {}".format(str(e))
            )
            return False
        return True

    def del_folder(self, path: str):
        """
        Delete a folder from the Minio bucket.

        Args:
            path (str): The folder path in the Minio bucket.

        Returns:
            bool: True if the folder is deleted successfully, False otherwise.

        """
        objects = self.client.list_objects(
            self.bucket_name, prefix=path, recursive=True
        )
        try:
            objects = [x._object_name for x in objects]
            for obj in objects:
                self.del_file(obj)
        except Exception as e:
            logger.exception("Delete file from s3 failed with error: {}".format(str(e)))
            return False
        return True

    def get_file(self, filename: str):
        """
        Download a file from the Minio bucket.

        Args:
            filename (str): The name of the file in the Minio bucket.

        Returns:
            bool: True if the file is downloaded successfully, False otherwise.
        """
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            my_file = Path(full_filename)
            if not my_file.is_file():
                folder_path = Path("/".join(full_filename.split("/")[:-1]))
                folder_path.mkdir(parents=True, exist_ok=True)
                self.client.fget_object(
                    self.bucket_name, filename, full_filename, progress=Progress()
                )
            else:
                logger.info("file already exists at path {}".format(full_filename))
        except Exception as e:
            logger.exception(
                "Error occurred while downloading file {}. Exception: {}".format(
                    filename, str(e)
                )
            )
            return False
        return True

    def put_file(self, filename: str):
        """
        Upload a file to the Minio bucket.

        Args:
            filename (str): The name of the file in the Minio bucket.

        Returns:
            bool: True if the file is uploaded successfully, False otherwise.
        """
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            self.client.fput_object(
                self.bucket_name, filename, full_filename, progress=Progress()
            )
            return True
        except Exception as e:
            logger.exception(
                "Upload file to minio s3 failed with error: {}".format(str(e))
            )
            return False

    def del_file(self, filename: str):
        """
        Delete a file from the Minio bucket.

        Args:
            filename (str): The name of the file in the Minio bucket.

        Returns:
            bool: True if the file is deleted successfully, False otherwise.
        """
        try:
            self.client.remove_object(self.bucket_name, filename)
        except Exception as e:
            logger.exception("Delete file from s3 failed with error: {}".format(str(e)))
            return False
        return True
