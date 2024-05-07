from unittest import TestCase
from assetsstore.assets import FileAssets
import glob
import os
import logging
import json
import requests


class AsssetsLocalTest(TestCase):
    def setUp(self):
        os.environ["ASSET_STORE"] = "MinioFiles"
        os.environ["LOCAL_STORE"] = "assetsstore/tests/fixtures/"
        self.maxDiff = None
        handler = FileAssets.get_asset(
            access_key="minio", secret_key="minio123", bucket_name="test"
        )
        handler.client.make_bucket("test")
        logging.basicConfig(level=logging.INFO)

    def test_upload_and_download_from_minio(self):
        handler = FileAssets.get_asset(
            access_key="minio", secret_key="minio123", bucket_name="test"
        )
        self.assertEqual(True, handler.put_file("test.txt"))

        # change path to avoid exists on 1. step
        os.environ["LOCAL_STORE"] = "assetsstore/tests/results/"

        # download file
        handler = FileAssets.get_asset(
            access_key="minio", secret_key="minio123", bucket_name="test"
        )
        self.assertEqual(True, handler.get_file("test.txt"))

        # get again to check if it exists
        self.assertEqual(True, handler.get_file("test.txt"))

        # delete remote file
        self.assertEqual(True, handler.del_file("test.txt"))

        # delete local copy
        self.assertEqual(True, handler.del_local_file("test.txt"))

    def test_get_folder_from_minio(self):
        handler = FileAssets.get_asset(
            access_key="minio", secret_key="minio123", bucket_name="test"
        )
        self.assertEqual(True, handler.put_file("test_folder/test2.txt"))
        self.assertEqual(True, handler.get_folder("test_folder"))
        self.assertEqual(True, handler.del_file("test_folder/test2.txt"))

    def test_get_upload_access(self):
        handler = FileAssets.get_asset(
            access_key="minio", secret_key="minio123", bucket_name="test"
        )
        self.assertIsNotNone(handler.get_upload_access("test.txt"))

    def test_get_download_access_private_object(self):
        handler = FileAssets.get_asset(
            access_key="minio", secret_key="minio123", bucket_name="test"
        )
        self.assertEqual(True, handler.put_file("test.txt"))
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Deny",
                    "Principal": {"AWS": "*"},
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::test/test.txt",
                },
                {
                    "Effect": "Deny",
                    "Principal": {"AWS": "*"},
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::test/test3.txt",
                },
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": "*"},
                    "Action": "s3:GetObject",
                    "Resource": "arn:aws:s3:::test/test2.txt",
                },
            ],
        }
        self.assertEqual(
            403, requests.get(f"http://{handler.host}/test/test.txt").status_code
        )
        handler.client.set_bucket_policy("test", json.dumps(policy))
        url = handler.get_access("test.txt", short=False)
        self.assertEqual(200, requests.get(url).status_code)
        self.assertEqual(True, handler.del_file("test.txt"))

    def test_get_access_for_public(self):
        handler = FileAssets.get_asset(
            access_key="minio", secret_key="minio123", bucket_name="test"
        )
        self.assertEqual(True, handler.put_file("test_folder/test2.txt"))
        test = handler.get_access("test_folder", short=True)
        self.assertEqual(True, handler.del_file("test_folder/test2.txt"))
        self.assertEqual(test, "http://localhost:9000/test/test_folder")

    def test_get_folder_size(self):
        handler = FileAssets.get_asset(
            access_key="minio", secret_key="minio123", bucket_name="test"
        )
        self.assertEqual(True, handler.put_file("test_folder/test2.txt"))
        self.assertEqual(19, handler.get_size("test_folder"))
        self.assertEqual(True, handler.del_file("test_folder/test2.txt"))

    def test_check_if_file_exists(self):
        handler = FileAssets.get_asset(
            access_key="minio", secret_key="minio123", bucket_name="test"
        )
        self.assertEqual(True, handler.put_file("test_folder/test2.txt"))
        self.assertTrue(handler.check_if_exists("test_folder/test2.txt"))
        self.assertFalse(handler.check_if_exists("test_folder/test33.txt"))
        self.assertEqual(True, handler.del_file("test_folder/test2.txt"))

    def tearDown(self):
        handler = FileAssets.get_asset(
            access_key="minio", secret_key="minio123", bucket_name="test"
        )
        handler.client.remove_bucket("test")
        for file in glob.glob("results/*"):
            if ".gitkeep" not in file:
                os.remove(file)
        for file in glob.glob("results/remote/*"):
            if ".gitkeep" not in file:
                os.remove(file)
