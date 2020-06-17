from assetsstore.assets import FileAssets
from shutil import copyfile
import pathlib
import logging
import os

logger = logging.getLogger(__name__)


class LocalFiles(FileAssets):

    def __init__(self):
        self.location = os.getenv("ASSET_LOCATION", "")
        self.server_url = os.getenv("ASSET_PUBLIC_URL", "error")
        super().__init__()

    def get_access(self, filename, seconds):
        return "{}{}".format(self.server_url, filename)

    def get_folder(self, path):
        for root, dirs, files in os.walk("{}{}".format(self.location, path)):
            for f in files:
                self.get_file("{}/{}".format(root.replace(self.location, ""), f))
        return "Donwloaded"

    def get_size(self, folder):
        size = 0
        return size

    def get_file(self, filename):
        asset_filename = os.path.realpath("{}{}".format(self.location, filename))
        local_filename = os.path.realpath("{}{}".format(self.local_store, filename))
        try:
            local_file = pathlib.Path(local_filename)
            if not local_file.is_file():
                folder_path = pathlib.Path("/".join(local_filename.split("/")[:-1]))
                folder_path.mkdir(parents=True, exist_ok=True)
                copyfile(asset_filename, local_filename)
            else:
                logger.info("File already downloaded {}".format(local_filename))
                return "Exists"
        except Exception as e:
            logger.exception("Download file from local store failed with error: {}".format(str(e)))
            return "Failed"
        return "Downloaded"

    def put_file(self, filename):
        asset_filename = os.path.realpath("{}{}".format(self.location, filename))
        local_filename = os.path.realpath("{}{}".format(self.local_store, filename))
        try:
            folder_path = pathlib.Path("/".join(asset_filename.split("/")[:-1]))
            folder_path.mkdir(parents=True, exist_ok=True)
            copyfile(local_filename, asset_filename)
        except Exception as e:
            logger.exception("Upload file to store failed with error: {}".format(str(e)))
            return "Failed"
        return "Uploaded"

    def del_file(self, filename, archive=False):
        asset_filename = os.path.realpath("{}{}".format(self.location, filename))
        if os.path.exists(asset_filename):
            try:
                os.remove(asset_filename)
                return "Deleted"
            except Exception as e:
                logger.exception("Delete file from local store failed with error: {}".format(str(e)))