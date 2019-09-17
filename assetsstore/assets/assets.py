import abc
import os
import uuid
import zipfile


class FileAssets(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        pass

    @abc.abstractmethod
    def get_file(self, filename):
        raise "Not implemented abstract method"

    @abc.abstractmethod
    def put_file(self, filename):
        raise "Not implemented abstract method"

    def save_and_push(self, file, filename):
        match_path, ext = os.path.splitext(filename)
        randomise_name = '{}-{}{}'.format(match_path, uuid.uuid4().hex, ext)
        saved_filename = '{}'.format(randomise_name)
        full_filename = os.path.realpath("{}{}".format(os.getenv("LOCAL_STORE", ""), saved_filename))
        with open(full_filename, 'wb') as model_file:
            model_file.write(file.read())

        self.put_file(saved_filename)

        return saved_filename

    @abc.abstractmethod
    def del_file(self, filename):
        raise "Not implemented abstract method"

    @classmethod
    def get_asset(cls):
        for sub_cls in cls.__subclasses__():
            if os.getenv("ASSET_STORE", "ServerFiles").lower() == sub_cls.__name__.lower():
                return sub_cls()

    def compress(self, file):
        with zipfile.ZipFile(file.replace('.csv', '.zip'), 'w', zipfile.ZIP_DEFLATED) as zipped:
            zipped.write(file, file.split('/')[-1])
        return file.replace('.csv', '.zip')
