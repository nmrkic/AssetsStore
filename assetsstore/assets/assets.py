import abc
import os
import uuid
import zipfile
import logging

logger = logging.getLogger(__name__)

class FileAssets(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self.local_store = os.getenv("LOCAL_STORE", "")

    @abc.abstractmethod
    def get_folder(self, path):
        raise "Not implemented abstract method"
    @abc.abstractmethod
    def get_file(self, filename):
        raise "Not implemented abstract method"

    def put_folder(self, path):
        for root, dirs, files in os.walk(path):
            for f in files:
            logger.info("files {}, {}, {}".format(root, dirs, f))
            self.put_file("{}/{}".format(path, f))

    @abc.abstractmethod
    def put_file(self, filename):
        raise "Not implemented abstract method"

    def save_and_push(self, file, filename):
        match_path, ext = os.path.splitext(filename)
        randomise_name = '{}-{}{}'.format(match_path, uuid.uuid4().hex, ext)
        saved_filename = '{}'.format(randomise_name)
        full_filename = os.path.realpath("{}{}".format(self.local_store, saved_filename))
        with open(full_filename, 'wb') as model_file:
            model_file.write(file.read())

        self.put_file(saved_filename)

        return saved_filename

    @abc.abstractmethod
    def del_file(self, filename):
        raise "Not implemented abstract method"

    @classmethod
    def get_asset(cls):
        asset = None
        selected = os.getenv("ASSET_STORE", "")
        for sub_cls in cls.__subclasses__():
            if selected.lower() == sub_cls.__name__.lower():
                asset = sub_cls
        if not asset:
            raise Exception("""There is no asset by name '{}' please set environment variable ASSET_STORE to one of the following:
                LocalFiles, ServerFiles, S3Files""".format(selected))
        return asset()
    def compress(self, file):
        with zipfile.ZipFile(file.replace('.csv', '.zip'), 'w', zipfile.ZIP_DEFLATED) as zipped:
            zipped.write(file, file.split('/')[-1])
        return file.replace('.csv', '.zip')

    def del_local_file(self, filename):
        local_filename = os.path.realpath("{}{}".format(self.local_store, filename))
        if os.path.exists(local_filename):
            try:
                os.remove(local_filename)
                return "Deleted"
            except Exception as e:
                logger.exception("Delete local file failed with error: {}".format(str(e)))
        else:
            logger.info("Local file does not exist {}".format(local_filename))
        return "Not Deleted"
 