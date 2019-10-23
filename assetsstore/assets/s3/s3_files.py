from assetsstore.assets import FileAssets
import os
import sys
import boto3
import logging
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class ProgressPercentage(object):
    def __init__(self, filename, client=None, bucket=None):
        self._filename = filename
        if client:
            self._size = float(
                client.head_object(
                    Bucket=bucket,
                    Key=filename
                ).get(
                    'ResponseMetadata',
                    {}
                ).get(
                    'HTTPHeaders',
                    {}
                ).get(
                    'content-length',
                    1
                )
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
                '{} is the file name. {} out of {} done. The percentage completed is {} %'.format(
                    str(self._filename),
                    str(self._seen_so_far),
                    str(self._size),
                    str(percentage)
                )
            )
            sys.stdout.flush()


class S3Files(FileAssets):

    def __init__(self):
        self.aws_access_key_id = os.getenv("ASSET_ACCESS_KEY", None)
        self.aws_secret_access_key = os.getenv("ASSET_SECRET_ACCESS_KEY", None)
        self.s3_bucket_name = os.getenv("ASSET_LOCATION")
        self.region_name = os.getenv("ASSET_REGION")
        session = None
        if self.aws_access_key_id:
            session = boto3.Session(
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key,
            )
        else:
            session = boto3.Session()
        self.connection = session.client('s3')
        super().__init__()

    def get_folder(self, path):
        # def downloadDirectoryFroms3(bucketName,remoteDirectoryName):
        # s3_resource = boto3.resource('s3')
        # bucket = s3_resource.Bucket(bucketName) 
        # for object in bucket.objects.filter(Prefix = remoteDirectoryName):
        #     if not os.path.exists(os.path.dirname(object.key)):
        #         os.makedirs(os.path.dirname(object.key))
        #     bucket.download_file(object.key,object.key)
        pass

    def get_file(self, filename):
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            my_file = Path(full_filename)
            if not my_file.is_file():
                progress = ProgressPercentage(filename, self.connection, self.s3_bucket_name)
                self.connection.download_file(self.s3_bucket_name, filename, full_filename, Callback=progress)
            else:
                logger.info("file already exists at path {}".format(full_filename))
                return "Exists"

        except Exception as e:
            logger.exception("Download file from s3 failed with error: {}".format(str(e)))
            return "Failed"
        return "Downloaded"

    def put_file(self, filename):
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            progress = ProgressPercentage(full_filename)
            self.connection.upload_file(full_filename, self.s3_bucket_name, filename, Callback=progress)
            return "Uploaded"
        except Exception as e:
            logger.exception("Upload file to s3 failed with error: {}".format(str(e)))
            return "Failed"

    def del_file(self, filename):
        try:
            self.connection.delete_object(Bucket=self.s3_bucket_name, Key=filename)

        except Exception as e:
            logger.exception("Delete file from s3 failed with error: {}".format(str(e)))
            return "Not Deleted"
        return "Deleted"
