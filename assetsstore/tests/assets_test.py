from unittest import TestCase
from assetsstore.assets import FileAssets
import glob
import os
import logging


class AsssetsLocalTest(TestCase):
    def setUp(self):
        self.maxDiff = None
        logging.basicConfig(level=logging.INFO)

    def test_no_asset_store_set(self):
        os.environ["ASSET_STORE"] = ""
        with self.assertRaises(Exception) as context:
            FileAssets.get_asset()
        print(context.exception)
        self.assertTrue("Invalid ASSET_STORE value" in str(context.exception))

    def test_upload_and_download_from_local(self):
        # get set store
        os.environ["ASSET_STORE"] = "LocalFiles"

        os.environ["ASSET_ACCESS_KEY_ID"] = ""
        os.environ["ASSET_SECRET_ACCESS_KEY"] = ""
        os.environ["ASSET_LOCATION"] = "assetsstore/tests/results/remote/"
        os.environ["ASSET_REGION"] = ""

        os.environ["LOCAL_STORE"] = "assetsstore/tests/fixtures/"
        handler = FileAssets.get_asset()
        self.assertEqual(True, handler.put_file("test.txt"))

        os.environ["LOCAL_STORE"] = "assetsstore/tests/results/"
        handler = FileAssets.get_asset()
        self.assertEqual(True, handler.get_file("test.txt"))

        # get again to check if it exists
        self.assertEqual(True, handler.get_file("test.txt"))

        # delete remote file
        self.assertEqual(True, handler.del_file("test.txt"))

        # delete local copy
        self.assertEqual(True, handler.del_local_file("test.txt"))

    def tearDown(self):
        for file in glob.glob("results/*"):
            if ".gitkeep" not in file:
                os.remove(file)
        for file in glob.glob("results/remote/*"):
            if ".gitkeep" not in file:
                os.remove(file)
