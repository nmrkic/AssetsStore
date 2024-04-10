from assetsstore.assets import FileAssets
import pathlib
import logging
import paramiko
import os
import stat


logger = logging.getLogger(__name__)


class ServerFiles(FileAssets):

    def __init__(self):
        self.server = os.getenv("ASSET_SERVER")
        self.username = os.getenv("ASSET_ACCESS_KEY")
        self.location = os.getenv("ASSET_LOCATION")
        self.server_url = os.getenv("ASSET_PUBLIC_URL")
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
        super().__init__()

    def get_access(self, filename, *args, **kwargs):
        return "{}{}".format(self.server_url, filename)

    def get_upload_access(self, filename, *args, **kwargs):
        return "{}{}".format(self.server_url, filename)

    def get_size(self, folder):
        size = 0
        asset_folder = "{}{}".format(self.location, folder)
        sftp = self.ssh.open_sftp()
        for i in sftp.listdir_attr(asset_folder):
            size = i.st_size
        return size

    def listdir_r(self, sftp, remotedir):
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

    def del_file(self, filename, archive=False):
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
