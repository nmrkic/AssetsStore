from assetsstore.assets import FileAssets
import os
import sys
import boto3
import logging
from pathlib import Path
import threading
from botocore.client import Config

logger = logging.getLogger(__name__)


class ProgressPercentage(object):
    def __init__(self, filename, client=None, bucket=None):
        self._filename = filename
        if client:
            self._size = float(
                client.head_object(Bucket=bucket, Key=filename)
                .get("ResponseMetadata", {})
                .get("HTTPHeaders", {})
                .get("content-length", 1)
            )
        else:
            self._size = float(os.path.getsize(filename))

        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        # To simplify we'll assume this is hooked up
        # to a single filename.
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = round((self._seen_so_far / self._size) * 100, 2)
            logger.info(
                "{} is the file name. {} out of {} done. The percentage completed is {} %".format(
                    str(self._filename),
                    str(self._seen_so_far),
                    str(self._size),
                    str(percentage),
                )
            )
            sys.stdout.flush()


class S3Files(FileAssets):
    """
    A class for interacting with files stored in an S3 bucket.

    Attributes:
        aws_access_key_id (str): The AWS access key ID.
        aws_secret_access_key (str): The AWS secret access key.
        s3_bucket_name (str): The name of the S3 bucket.
        region_name (str): The AWS region name.
        connection (boto3.client): The S3 client connection.
        resource (boto3.resource): The S3 resource connection.
    """

    def __init__(
        self,
        access_key=os.getenv("ASSET_ACCESS_KEY"),
        secret_key=os.getenv("ASSET_SECRET_ACCESS_KEY"),
        bucket_name=os.getenv("ASSET_LOCATION"),
        bucket_region=os.getenv("ASSET_REGION"),
        local_store=os.getenv("LOCAL_STORE"),
        profile_name=os.getenv("AWS_PROFILE", "default"),
    ):
        self.aws_access_key_id = access_key
        self.aws_secret_access_key = secret_key
        self.s3_bucket_name = bucket_name
        self.region_name = bucket_region
        self.local_store = local_store
        self.profile_name = profile_name
        session = None
        if self.aws_access_key_id:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )
        else:
            session = boto3.Session(profile_name=self.profile_name)
        self.connection = session.client(
            "s3",
            config=Config(region_name=self.region_name, signature_version="s3v4"),
            endpoint_url=f"https://s3.{self.region_name}.amazonaws.com",
        )
        self.resource = session.resource(
            "s3", endpoint_url=f"https://s3.{self.region_name}.amazonaws.com"
        )

    def check_if_exists(self, path: str):
        """
        Checks if desired object exists.
        Args:
            path (str): The path in the S3 bucket.

        Returns:
            bool: True if file exists, False otherwise.
        """
        try:
            self.connection.head_object(Bucket=self.s3_bucket_name, Key=path)
            return True
        except Exception as e:
            logger.warning("Cannot access bucket object. Exception {}".format(str(e)))
        return False

    def get_size(self, folder: str):
        """
        Get the total size of files in a folder in the S3 bucket.

        Args:
            folder (str): The folder path in the S3 bucket.

        Returns:
            int: The total size of files in the folder.

        """
        size = 0
        try:
            bucket = self.resource.Bucket(self.s3_bucket_name)
            for key in bucket.objects.filter(Prefix=folder):
                if key.meta.data.get("StorageClass", "") == "STANDARD":
                    size += key.size
        except Exception as e:
            logger.exception(
                "Cannot get size of the S3 bucket folder. Exception: {}".format(str(e))
            )
            return False
        return size

    def get_access(
        self,
        filename: str,
        seconds: int = 0,
        short: bool = False,
        download_filename: str = "",
    ):
        """
        Get temporary access to download a file from the S3 bucket.

        Args:
            filename (str): The name of the file in the S3 bucket.
            seconds (int): The duration of access in seconds (default: 0).
            short (bool): Whether to generate a short URL (default: False).
            download_filename (str): The name of the file to be downloaded (default: "").

        Returns:
            str: The URL for accessing the file.

        """
        response = None
        try:
            if not download_filename:
                download_filename = filename

            if short:
                response = "https://{}.s3.amazonaws.com/{}".format(
                    self.s3_bucket_name, filename
                )
                short_url = self.shorten_url(response)
                if short_url:
                    response = short_url
            else:
                response = self.connection.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={
                        "Bucket": self.s3_bucket_name,
                        "Key": filename,
                        "ResponseContentDisposition": f"attachment;filename={download_filename}",
                    },
                    ExpiresIn=seconds,
                )

        except Exception as e:
            logger.exception(
                "Not able to give access to {} for {} seconds. Exception {}".format(
                    filename, seconds, str(e)
                )
            )
            return False
        return response

    def get_upload_access(self, filename: str, seconds: int = 0):
        """
        Get temporary access to upload a file to the S3 bucket.

        Args:
            filename (str): The name of the file in the S3 bucket.
            seconds (int): The duration of access in seconds (default: 0).

        Returns:
            str: The URL for uploading the file.

        """
        response = None

        # Set the desired multipart threshold value (5GB)
        try:
            response = self.connection.generate_presigned_url(
                ClientMethod="put_object",
                Params={
                    "Bucket": self.s3_bucket_name,
                    "Key": filename,
                },
                ExpiresIn=seconds,
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
        Download a folder from the S3 bucket to the local file system.

        Args:
            path (str): The folder path in the S3 bucket.

        Returns:
            bool: True if the folder is downloaded successfully, False otherwise.

        """
        try:
            local_folder = os.path.realpath("{}{}".format(self.local_store, path))
            logger.info(
                "Getting folder from s3 {}, into local folder {}".format(
                    path, local_folder
                )
            )
            bucket = self.resource.Bucket(self.s3_bucket_name)
            for obj in bucket.objects.filter(Prefix=path):
                try:
                    logger.info("Downloading file {}".format(obj.key))
                    full_filename = os.path.realpath(
                        "{}{}".format(self.local_store, obj.key)
                    )
                    if not os.path.exists(os.path.dirname(full_filename)):
                        os.makedirs(os.path.dirname(full_filename))
                    self.get_file(obj.key)
                except Exception as e:
                    logger.warning(
                        "Error occurred downloading file {}, with error: {}".format(
                            str(e), obj.key
                        )
                    )
        except Exception as e:
            logger.warning(
                "Error occurred while downloading folder from s3 {}".format(str(e))
            )
            return False
        return True

    def del_folder(self, path: str):
        """
        Delete a folder and its contents from the S3 bucket.

        Args:
            path (str): The folder path in the S3 bucket.

        Returns:
            bool: True if the folder is deleted successfully, False otherwise.

        """
        bucket = self.resource.Bucket(self.s3_bucket_name)
        for obj in bucket.objects.filter(Prefix=path):
            try:
                self.del_file(obj.key)
            except Exception as e:
                logger.exception(
                    "Delete file from s3 failed with error: {}".format(str(e))
                )
                return False
        return True

    def get_file(self, filename: str):
        """
        Download a file from the S3 bucket to the local file system.

        Args:
            filename (str): The name of the file in the S3 bucket.

        Returns:
            bool: True if the file is downloaded successfully, False otherwise.

        """
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            my_file = Path(full_filename)
            if not my_file.is_file():
                folder_path = Path("/".join(full_filename.split("/")[:-1]))
                folder_path.mkdir(parents=True, exist_ok=True)
                progress = ProgressPercentage(
                    filename, self.connection, self.s3_bucket_name
                )
                self.connection.download_file(
                    self.s3_bucket_name, filename, full_filename, Callback=progress
                )
            else:
                logger.info("file already exists at path {}".format(full_filename))
                return True

        except Exception as e:
            logger.exception(
                "Download file from s3 failed with error: {}".format(str(e))
            )
            return False
        return True

    def put_file(self, filename: str):
        """
        Upload a file from the local file system to the S3 bucket.

        Args:
            filename (str): The name of the file in the S3 bucket.

        Returns:
            bool: True if the file is uploaded successfully, False otherwise.

        """
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            progress = ProgressPercentage(full_filename)
            self.connection.upload_file(
                full_filename, self.s3_bucket_name, filename, Callback=progress
            )
        except Exception as e:
            logger.exception("Upload file to s3 failed with error: {}".format(str(e)))
            return False
        return True

    def del_file(self, filename: str, archive: bool = False):
        """
        Delete a file from the S3 bucket.

        Args:
            filename (str): The name of the file in the S3 bucket.
            archive (bool): Whether to archive the file before deleting (default: False).

        Returns:
            bool: True if the file is deleted successfully, False otherwise.

        """
        try:
            if archive:
                self.connection.copy(
                    {"Bucket": self.s3_bucket_name, "Key": filename},
                    self.s3_bucket_name,
                    filename,
                    ExtraArgs={"StorageClass": "GLACIER", "MetadataDirective": "COPY"},
                )
            else:
                self.connection.delete_object(Bucket=self.s3_bucket_name, Key=filename)

        except Exception as e:
            logger.exception("Delete file from s3 failed with error: {}".format(str(e)))
            return False
        return True
