from assetsstore.assets import FileAssets
import os
import sys
import boto3
import logging
from pathlib import Path
import threading

from boto3.s3.transfer import TransferConfig

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
        self.upload_connection = session.client(
            's3',
            config=boto3.session.Config(
                s3={'addressing_style': 'path'},
                signature_version='s3v4'
            )
        )

        self.resource = session.resource('s3')
        super().__init__()

    def _check_public(self, filename):
        try:
            acl_object = self.resource.ObjectAcl(self.s3_bucket_name, filename)
            if [x for x in  acl_object.grants if x.get('Grantee',{}).get('URI', '') == 'http://acs.amazonaws.com/groups/global/AllUsers']:
                return True
        except Exception as e:
            logger.warn("Cannot access bucket object. Exception {}".format(str(e)))
        return False

    def _set_public(self, filename):
        try:
            acl_object = self.resource.ObjectAcl(self.s3_bucket_name, filename)
            resp = acl_object.put(ACL='public-read')
            logger.info("public read {}".format(resp))
            return True
        except Exception as e:
            logger.exception("Cannot change object permissions {}".format(str(e)))
        return False

    def get_size(self, folder):
        size = 0
        try:
            bucket = self.resource.Bucket(self.s3_bucket_name)
            for key in bucket.objects.filter(Prefix=folder):
                if key.meta.data.get('StorageClass', "") == "STANDARD":
                    size += key.size

        except Exception as e:
            logger.exception("Cannot get size of the S3 bucket folder. Exception: {}".format(str(e)))
        return size

    def get_access(self, filename, seconds=0, short=True):
        response = None
        try:
            public = self._check_public(filename)

            if (not seconds or seconds == 0) and not public:
                public = self._set_public(filename)

            if public and short:
                response = "https://{}.s3.amazonaws.com/{}".format(self.s3_bucket_name, filename)
                short_url = self.shorten_url(response)
                if short_url:
                    response = short_url
            else:
                response = self.connection.generate_presigned_url(
                    ClientMethod='get_object',
                    Params={
                        'Bucket': self.s3_bucket_name,
                        'Key': filename,
                    },
                    ExpiresIn=seconds
                )

        except Exception as e:
            logger.exception("Not able to give access to {} for {} seconds. Exception".format(filename, seconds, str(e)))
        return response

    def get_upload_access(self, filename, seconds=0):
        response = None

        # Set the desired multipart threshold value (5GB)
        try:
            response = self.upload_connection.generate_presigned_url(
                ClientMethod='put_object',
                Params={
                    'Bucket': self.s3_bucket_name,
                    'Key': filename,
                },
                ExpiresIn=seconds
            )

        except Exception as e:
            logger.exception("Not able to give access to {} for {} seconds. Exception".format(filename, seconds, str(e)))
        return response

    def get_folder(self, path):
        try:
            local_folder = os.path.realpath("{}{}".format(self.local_store, path))
            logger.info("Getting folder from s3 {}, into local folder {}".format(path, local_folder))
            bucket = self.resource.Bucket(self.s3_bucket_name)
            for obj in bucket.objects.filter(Prefix=path):
                try:
                    logger.info("Downloading file {}".format(obj.key))
                    full_filename = os.path.realpath("{}{}".format(self.local_store, obj.key))
                    if not os.path.exists(os.path.dirname(full_filename)):
                        os.makedirs(os.path.dirname(full_filename))
                    self.get_file(obj.key)
                except Exception as e:
                    logger.warn("Error occured downloading file {}, with error: {}".format(str(e), obj.key))
        except Exception as e:
            logger.warn("Error occured while downloading folder from s3 {}".format(str(e)))
            return "Failed"
        return "Downloaded"

    def get_file(self, filename):
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            my_file = Path(full_filename)
            if not my_file.is_file():
                folder_path = Path("/".join(full_filename.split("/")[:-1]))
                folder_path.mkdir(parents=True, exist_ok=True)
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

    def del_file(self, filename, archive=False):
        try:
            if archive:
                self.connection.copy(
                    {"Bucket": self.s3_bucket_name, "Key": filename},
                    self.s3_bucket_name,
                    filename,
                    ExtraArgs = {
                        "StorageClass": "GLACIER",
                        "MetadataDirective": "COPY"
                    }
                )
            else:
                self.connection.delete_object(Bucket=self.s3_bucket_name, Key=filename)

        except Exception as e:
            logger.exception("Delete file from s3 failed with error: {}".format(str(e)))
            return "Not Deleted"
        return "Deleted"
