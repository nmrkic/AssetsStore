from datetime import timedelta
from assetsstore.assets import FileAssets
import os
import logging
import json
from pathlib import Path
from minio import Minio
from .progress import Progress

logger = logging.getLogger(__name__)


class MinioFiles(FileAssets):

    def __init__(self):
        self.access_key = os.getenv("ASSET_ACCESS_KEY", None)
        self.secret_key = os.getenv("ASSET_SECRET_ACCESS_KEY", None)
        self.bucket_name = os.getenv("ASSET_LOCATION")
        self.host = os.getenv("ASSET_PUBLIC_URL", "localhost:9000")
        self.tls_enabled = os.getenv("ASSET_TLS_ENABLED", False)
        self.client = Minio(
            self.host,
            self.access_key,
            self.secret_key,
            secure=self.tls_enabled
        )
        super().__init__()

    def _check_public(self, filename):
        response = None
        try:
            response = self.client.get_object(self.bucket_name, filename)
            success = True
        except Exception as e:
            success = False
            logger.warn("Cannot access bucket object. Exception {}".format(str(e)))
        if response:
            response.close()
            response.release_conn()
        return success

    def _set_public(self, filename):
        try:
            policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"AWS": "*"},
                        "Action": "s3:GetObject",
                        "Resource": f"arn:aws:s3:::{self.bucket_name}/{filename}",
                    },
                ],
            }
            try:
                existing_policy = json.loads(self.client.get_bucket_policy(self.bucket_name))
                for pol in existing_policy["Statement"]:
                    # Do not allow 2 same effects on policies
                    if not pol["Resource"][0] == policy["Statement"][0]["Resource"]:
                        policy["Statement"].append(pol)
            except Exception as e:
                logger.info(f"No policy detected.. {str(e)}")
            self.client.set_bucket_policy(self.bucket_name, json.dumps(policy))
            return True
        except Exception as e:
            logger.exception("Cannot change object permissions {}".format(str(e)))
        return False

    def get_size(self, folder):
        size = 0
        try:
            for obj in self.client.list_objects(self.bucket_name, prefix=folder, recursive=True):
                size += obj.size
        except Exception as e:
            logger.exception("Cannot get size of the S3 bucket folder. Exception: {}".format(str(e)))
        return size

    def get_access(self, filename, seconds: int = 0, short=True):
        response = None
        try:
            public = self._check_public(filename)

            if (not seconds or seconds == 0) and not public:
                public = self._set_public(filename)

            if public and short:
                response = f"{self.host}/{filename}"
                short_url = self.shorten_url(response)
                if short_url:
                    response = short_url
            else:
                response = self.client.presigned_get_object(
                    self.bucket_name,
                    filename,
                    expires=timedelta(seconds=seconds if seconds else 604800)
                )
        except Exception as e:
            logger.exception("Not able to give access to {} for {} seconds. Exception {}".format(filename, seconds, str(e)))
        return response

    def get_upload_access(self, filename, seconds: int = 0):
        response = None
        try:
            response = self.client.presigned_put_object(
                self.bucket_name,
                filename,
                expires=timedelta(seconds=seconds if seconds else 604800)
            )
        except Exception as e:
            logger.exception("Not able to give access to {} for {} seconds. Exception {}".format(filename, seconds, str(e)))
        return response

    def get_folder(self, path):
        try:
            local_folder = os.path.realpath("{}{}".format(self.local_store, path))
            logger.info("Getting folder from minio s3 {}, into local folder {}".format(path, local_folder))
            for obj in self.client.list_objects(self.bucket_name, prefix=path, recursive=True):
                try:
                    logger.info("Downloading file {}".format(obj._object_name))
                    full_filename = os.path.realpath("{}{}".format(self.local_store, obj._object_name))
                    if not os.path.exists(os.path.dirname(full_filename)):
                        os.makedirs(os.path.dirname(full_filename))
                    self.get_file(obj)
                except Exception as e:
                    logger.warn("Error occured downloading file {}, with error: {}".format(str(e), obj._object_name))
        except Exception as e:
            logger.warn("Error occured while downloading folder from s3 minio {}".format(str(e)))
            return "Failed"
        return "Downloaded"

    def del_folder(self, path):
        objects = self.client.list_objects(self.bucket_name, prefix=path, recursive=True)
        try:
            objects = [x._object_name for x in objects]
            for obj in objects:
                self.del_file(obj)
        except Exception as e:
            logger.exception("Delete file from s3 failed with error: {}".format(str(e)))
            return "Not Deleted"
        return "Deleted"

    def get_file(self, filename):
        try:
            full_filename = os.path.realpath("{}{}".format(self.local_store, filename))
            my_file = Path(full_filename)
            if not my_file.is_file():
                folder_path = Path("/".join(full_filename.split("/")[:-1]))
                folder_path.mkdir(parents=True, exist_ok=True)
                self.client.fget_object(self.bucket_name, filename, full_filename, progress=Progress())
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
            self.client.fput_object(self.bucket_name, filename, full_filename, progress=Progress())
            return "Uploaded"
        except Exception as e:
            logger.exception("Upload file to minio s3 failed with error: {}".format(str(e)))
            return "Failed"

    def del_file(self, filename):
        try:
            self.client.remove_object(self.bucket_name, filename)
        except Exception as e:
            logger.exception("Delete file from s3 failed with error: {}".format(str(e)))
            return "Not Deleted"
        return "Deleted"
