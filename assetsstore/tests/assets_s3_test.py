from unittest import TestCase
from assetsstore.assets import FileAssets
import glob
import os
import logging


class AsssetsS3Test(TestCase):

    def setUp(self):
        self.maxDiff = None
        logging.basicConfig(level=logging.INFO)

    def test_upload_and_download_from_s3(self):
        # get set store
        os.environ["ASSET_STORE"]="S3Files"

        os.environ["AWS_ACCESS_KEY_ID"]=""
        os.environ["AWS_SECRET_ACCESS_KEY"]=""
        os.environ["S3_BUCKET_NAME"]=""
        os.environ["S3_REGION_NAME"]=""

        s3_handler = FileAssets.get_asset()
        os.environ["LOCAL_STORE"] = "fixtures/"
        self.assertEqual("Uploaded", s3_handler.put_file("test.txt"))

        os.environ["LOCAL_STORE"] = "results/"
        self.assertEqual("Downloaded", s3_handler.get_file("test.txt"))

        # get again to check if it exists
        self.assertEqual("Exists", s3_handler.get_file("test.txt"))

        self.assertEqual("Deleted", s3_handler.del_file("test.txt"))

    def tearDown(self):
        for file in glob.glob('results/*'):
            if '.gitkeep' not in file:
                os.remove(file)
