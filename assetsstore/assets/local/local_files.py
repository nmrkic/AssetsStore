from assetsstore.assets import FileAssets
from shutil import copyfile
import pathlib
import logging
import os

logger = logging.getLogger(__name__)


class LocalFiles(FileAssets):
    """
    A class that represents local file assets.

    This class provides methods to interact with local files,
    including getting access to files,
    uploading files, downloading files, and deleting files.
    """

    def __init__(
        self,
        location=os.getenv("ASSET_LOCATION"),
        server_url=os.getenv("SERVER_URL"),
        local_store=os.getenv("LOCAL_STORE"),
    ):
        self.location = location
        self.server_url = server_url
        self.local_store = local_store

    def check_if_exists(self, path: str):
        pass

    def get_access(self, filename: str, *args, **kwargs):
        """
        Get the access URL for a file.

        Args:
            filename (str): The name of the file.

        Returns:
            str: The access URL for the file.

        """
        return "{}{}".format(self.server_url, filename)

    def get_upload_access(self, filename: str, *args, **kwargs):
        """
        Get the upload access URL for a file.

        Args:
            filename (str): The name of the file.

        Returns:
            str: The upload access URL for the file.

        """
        return "{}{}".format(self.server_url, filename)

    def get_folder(self, path: str):
        """
        Get the files in a folder.

        Args:
            path (str): The path of the folder.

        Returns:
            bool: True if the operation is successful, False otherwise.

        """
        for root, dirs, files in os.walk("{}{}".format(self.location, path)):
            for f in files:
                self.get_file("{}/{}".format(root.replace(self.location, ""), f))
        return True

    def get_file(self, filename):
        """
        Get a file from the asset store.

        Args:
            filename (str): The name of the file.

        Returns:
            bool: True if the file is successfully downloaded, False otherwise.

        """
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
                return True
        except Exception as e:
            logger.exception(
                "Download file from local store failed with error: {}".format(str(e))
            )
            return False
        return True

    def put_file(self, filename):
        """
        Put a file into the asset store.

        Args:
            filename (str): The name of the file.

        Returns:
            bool: True if the file is successfully uploaded, False otherwise.

        """
        asset_filename = os.path.realpath("{}{}".format(self.location, filename))
        local_filename = os.path.realpath("{}{}".format(self.local_store, filename))
        try:
            folder_path = pathlib.Path("/".join(asset_filename.split("/")[:-1]))
            folder_path.mkdir(parents=True, exist_ok=True)
            copyfile(local_filename, asset_filename)
        except Exception as e:
            logger.exception(
                "Upload file to store failed with error: {}".format(str(e))
            )
            return False
        return True

    def del_file(self, filename):
        """
        Delete a file from the asset store.

        Args:
            filename (str): The name of the file.

        Returns:
            bool: True if the file is successfully deleted, False otherwise.

        """
        asset_filename = os.path.realpath("{}{}".format(self.location, filename))
        if os.path.exists(asset_filename):
            try:
                os.remove(asset_filename)
                return True
            except Exception as e:
                logger.exception(
                    "Delete file from local store failed with error: {}".format(str(e))
                )
        return False
