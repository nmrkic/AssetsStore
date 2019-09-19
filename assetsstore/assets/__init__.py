from .assets import FileAssets
from .s3 import S3Files
from .server import ServerFiles
from .local import LocalFiles

__version__ = "0.0.1"

__all__ = [
    "FileAssets",
    "S3Files",
    "ServerFiles",
    "LocalFiles"
]
