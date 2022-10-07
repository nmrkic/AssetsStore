# Assets Store
### [**Github**](https://github.com/nmrkic/AssetsStore)

This library was created to simplify upload/download of files from/to S3, Azure Storage, or your desired server. 

## Setup instructions

The project is using python 3.10 but should support newer versions, it relies on boto3 lib for S3, azure-storage-blob for AzureStorage, and paramiko for server connections.


- [Python 3.10](python.org/downloads/)
- [boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [azure-storage-blob](https://pypi.org/project/azure-storage-blob/)
- [paramiko](https://www.paramiko.org/)


## How to use

Install with pip:

``` pip install AssetsStore ```

Set environment variables dependent on what upload you are using:

- AzureStorage

```
ASSET_STORE=AzureFiles
ASSET_ACCESS_KEY="put_access_key"
ASSET_SECRET_ACCESS_KEY="put_access_key_secret"
ASSET_LOCATION="name_of_the_blob"
ASSET_PUBLIC_URL="blob_public_url"
LOCAL_STORE=path_to_download_folder
```

- S3

```
ASSET_STORE=S3Files
ASSET_ACCESS_KEY="put_access_key"
ASSET_SECRET_ACCESS_KEY="put_access_key_secret"
ASSET_LOCATION="name_of_the_bucket"
ASSET_PUBLIC_URL="blob_public_url"
ASSET_REGION="s3_region"
LOCAL_STORE=path_to_download_folder
```

- for local development

```
ASSET_STORE=LocalFiles
ASSET_LOCATION="path_to_folder"
ASSET_PUBLIC_URL="local_url_if_folder_hosted"
LOCAL_STORE=path_to_download_folder
```

The library has abbility to use Rebrand and to use it add these envs:

```
REBRAND_KEY="rebrand_key"
REBRAND_DOMAIN='rebrand_domain'
```

## Usage example

```python

from assetsstore.assets import FileAssets

assets = FileAssets.get_asset()  # setup asset store
assets.put_file("some_file.txt")  # Upload file from local download folder
assets.get_file("some_file.txt")  # Download file to local download folder
assets.del_local_file("some_file.txt")  # Delete file from local download folder
assets.del_file("some_file.txt")  # Deletes file from serve
```


## Authors

  

- [@nmrkic](https://github.com/nmrkic)

  
  

## Contributing

  

Contributions are always welcome! :)

