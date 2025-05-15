from assetsstore.assets import FileAssets
import pathlib
import logging
import paramiko
import os
import stat


logger = logging.getLogger(__name__)


class ServerFiles(FileAssets):
    """
    Represents a class for managing server files.

    This class provides methods for accessing, uploading, downloading,
    and deleting files on a remote server.

    Attributes:
        server (str): The server address.
        username (str): The username for authentication.
        location (str): The location of the asset files on the server.
        server_url (str): The public URL of the asset server.
        ssh (paramiko.SSHClient): The SSH client for connecting to the server.
        pkey (paramiko.Ed25519Key): The private key for authentication (optional).
        password (str): The password for authentication (optional).
    """

    def __init__(
        self,
        server=os.getenv("ASSET_SERVER"),
        username=os.getenv("ASSET_ACCESS_KEY"),
        location=os.getenv("ASSET_LOCATION"),
        server_url=os.getenv("ASSET_PUBLIC_URL"),
        local_store=os.getenv("LOCAL_STORE"),
    ):
        self.server = server
        self.username = username
        self.location = location
        self.server_url = server_url
        self.local_store = local_store
        self.ssh = paramiko.SSHClient()
        self.ssh.load_host_keys(
            os.path.expanduser(os.path.join("~", ".ssh", "known_hosts"))
        )
        pkey_path = os.getenv("ASSET_PRIVATE_KEY")
        if pkey_path:
            self.pkey = paramiko.Ed25519Key.from_private_key_file(pkey_path)
            self.ssh.connect(
                self.server, username=self.username, pkey=self.pkey, banner_timeout=200
            )
        else:
            self.password = os.getenv("ASSET_SECRET_ACCESS_KEY")
            self.ssh.connect(
                self.server, username=self.username, password=self.password
            )

    def check_if_exists(self, path: str):
        pass

    def get_access(self, filename, *args, **kwargs):
        """
        Get the access URL for a file.

        Args:
            filename (str): The name of the file.

        Returns:
            str: The access URL for the file.
        """
        return "{}{}".format(self.server_url, filename)

    def get_upload_access(self, filename, *args, **kwargs):
        """
        Get the upload access URL for a file.

        Args:
            filename (str): The name of the file.

        Returns:
            str: The upload access URL for the file.
        """
        return "{}{}".format(self.server_url, filename)

    def get_size(self, folder):
        """
        Get the size of a folder on the server.

        Args:
            folder (str): The path to the folder.

        Returns:
            int: The size of the folder in bytes.
        """
        size = 0
        asset_folder = "{}{}".format(self.location, folder)
        sftp = self.ssh.open_sftp()
        for i in sftp.listdir_attr(asset_folder):
            size = i.st_size
        return size

    def listdir_r(self, sftp, remotedir):
        """
        Recursively list all files in a directory on the server.

        Args:
            sftp (paramiko.SFTPClient): The SFTP client.
            remotedir (str): The path to the directory.

        Returns:
            list: A list of file paths.
        """
        file_list = []
        for entry in sftp.listdir_attr(remotedir):
            remotepath = remotedir + "/" + entry.filename
            mode = entry.st_mode
            if stat.S_ISDIR(mode):
                file_list.extend(self.listdir_r(sftp, remotepath))
            elif stat.S_ISREG(mode):
                file_list.append(remotepath)
        return file_list

    def get_folder(self, path):
        """
        Download a folder from the server.

        Args:
            path (str): The path to the folder on the server.

        Returns:
            bool: True if the folder was downloaded successfully, False otherwise.
        """
        try:
            sftp = self.ssh.open_sftp()
            asset_folder = "{}{}".format(self.location, path)
            for r_file in self.listdir_r(sftp, asset_folder):
                folder_path = pathlib.Path("/".join(r_file.split("/")[:-1]))
                folder_path.mkdir(parents=True, exist_ok=True)
                self.get_file(r_file.replace(self.location, ""))
            sftp.close()
        except Exception as e:
            logger.exception(
                "Failed to read remote folder. Exception {}".format(str(e))
            )
            return False
        return True

    def get_file(self, filename):
        """
        Download a file from the server.

        Args:
            filename (str): The name of the file on the server.

        Returns:
            bool: True if the file was downloaded successfully, False otherwise.
        """
        asset_filename = "{}{}".format(self.location, filename)
        local_filename = os.path.realpath("{}{}".format(self.local_store, filename))
        try:
            local_file = pathlib.Path(local_filename)
            if not local_file.is_file():
                sftp = self.ssh.open_sftp()
                folder_path = pathlib.Path(
                    "{}{}".format(self.local_store, "/".join(filename.split("/")[:-1]))
                )
                folder_path.mkdir(parents=True, exist_ok=True)
                sftp.get(asset_filename, local_filename)
                sftp.close()
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
        Upload a file to the server.

        Args:
            filename (str): The name of the file to upload.

        Returns:
            bool: True if the file was uploaded successfully, False otherwise.
        """
        asset_filename = "{}{}".format(self.location, filename)
        local_filename = os.path.realpath("{}{}".format(self.local_store, filename))
        try:
            local_file = pathlib.Path(local_filename)
            if local_file.is_file():
                sftp = self.ssh.open_sftp()
                sftp.put(local_filename, asset_filename)
                sftp.close()
            else:
                logger.info("Local file does not exist {}".format(local_filename))
                return False
        except Exception as e:
            logger.exception(
                "Download file from local store failed with error: {}".format(str(e))
            )
            return False
        return True

    def del_file(self, filename, *args, **kwargs):
        """
        Delete a file from the server.

        Args:
            filename (str): The name of the file to delete.
            archive (bool): Whether to archive the file (default: False).

        Returns:
            bool: True if the file was deleted successfully, False otherwise.
        """
        asset_filename = "{}{}".format(self.location, filename)
        if os.path.exists(asset_filename):
            try:
                sftp = self.ssh.open_sftp()
                sftp.remove(asset_filename)
                sftp.close()
                return True
            except Exception as e:
                logger.exception(
                    "Delete file from local store failed with error: {}".format(str(e))
                )
        return False

    def __del__(self):
        if self.ssh:
            self.ssh.close()
