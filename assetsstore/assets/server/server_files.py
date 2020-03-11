from assetsstore.assets import FileAssets
from shutil import copyfile
from pathlib import Path
import logging
import paramiko
import os

logger = logging.getLogger(__name__)


class ServerFiles(FileAssets):

    def __init__(self):
        self.server = os.getenv("ASSET_SERVER")
        self.username = os.getenv("ASSET_ACCESS_KEY")
        self.password = os.getenv("ASSET_SECRET_ACCESS_KEY")
        self.location = os.getenv("ASSET_LOCATION", "")
        self.server_url = os.getenv("ASSET_PUBLIC_URL", "")
        self.ssh = paramiko.SSHClient()
        self.ssh.load_host_keys(os.path.expanduser(os.path.join("~", ".ssh", "known_hosts")))
        self.ssh.connect(self.server, username=self.username, password=self.password)
        super().__init__()

    def get_access(self, filename, seconds):
        return "{}{}".format(self.server_url, filename)

    def get_size(self, folder):
        size = 0
        return size

    def listdir_r(self, sftp, remotedir):
        file_list = []
        for entry in sftp.listdir_attr(remotedir):
            remotepath = remotedir + "/" + entry.filename
            mode = entry.st_mode
            if S_ISDIR(mode):
                file_list.extend(listdir_r(sftp, remotepath))
            elif S_ISREG(mode):
                file_list.append(remotepath)
        return file_list

    def get_folder(self, path):
        try:
            sftp = self.ssh.open_sftp()
            for r_file in self.listdir_r(sftp, path):
                folder_path = pathlib.Path("/".join(local_filename.split("/")[:-1]))
                folder_path.mkdir(parents=True, exist_ok=True)
                self.get_file(r_file)

            sftp.close()
        except Exception as e:
            logger.exception("Failed to read remote folder. Exception {}".format(str(e)))
        return 'Downloaded'
    def get_file(self, filename):

        asset_filename = os.path.realpath("{}{}".format(self.location, filename))
        local_filename = os.path.realpath("{}{}".format(self.local_store, filename))
        try:
            local_file = Path(local_filename)
            if not local_file.is_file():
                sftp = self.ssh.open_sftp()
                sftp.get(asset_filename, local_filename)
                sftp.close()
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
            local_file = Path(local_filename)
            if local_file.is_file():
                sftp = self.ssh.open_sftp()
                sftp.put(local_filename, asset_filename)
                sftp.close()
            else:
                logger.info("Local file does not exist {}".format(local_filename))
                return "Failed"
        except Exception as e:
            logger.exception("Download file from local store failed with error: {}".format(str(e)))
            return "Failed"
        return "Uploaded"

    def del_file(self, filename):
        asset_filename = os.path.realpath("{}{}".format(self.location, filename))
        if os.path.exists(asset_filename):
            try:
                sftp = self.ssh.open_sftp()
                sftp.remove(asset_filename)
                sftp.close()
                return "Removed"
            except Exception as e:
                logger.exception("Delete file from local store failed with error: {}".format(str(e)))
    
    def __del__(self):
        if self.ssh:
            self.ssh.close()
