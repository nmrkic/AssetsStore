import pytest
from assetsstore.assets import FileAssets
import os
import json
import requests


MINIO_ACCESS_KEY = "minio"
MINIO_SECRET_KEY = "minio123"
TEST_BUCKET = "test-bucket-pytest"


@pytest.fixture(scope="session", autouse=True)
def ensure_minio_bucket():
    """Create test bucket in MinIO if it doesn't exist."""
    os.environ["ASSET_STORE"] = "MinioFiles"

    try:
        handler = FileAssets.get_asset(
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            bucket_name=TEST_BUCKET,
        )
        handler.client.make_bucket(TEST_BUCKET)
    except Exception:
        # Bucket might already exist
        pass

    yield

    # Cleanup bucket after all tests
    handler = FileAssets.get_asset(
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        bucket_name=TEST_BUCKET,
    )
    # Remove all objects
    try:
        objects = handler.client.list_objects(TEST_BUCKET, recursive=True)
        for obj in objects:
            handler.client.remove_object(TEST_BUCKET, obj.object_name)
    except Exception:
        pass

    # Remove bucket
    try:
        handler.client.remove_bucket(TEST_BUCKET)
    except Exception:
        pass


@pytest.fixture
def minio_handler(tmp_path):
    """Return MinIO handler with temporary local store."""
    # Create test files first
    (tmp_path / "test.txt").write_text("This is a test file for unit tests.")
    test_folder = tmp_path / "test_folder"
    test_folder.mkdir()
    (test_folder / "test2.txt").write_text("This is test2 file.")

    # Set LOCAL_STORE environment variable
    os.environ["LOCAL_STORE"] = str(tmp_path) + "/"

    # Create handler with explicit local_store parameter
    return FileAssets.get_asset(
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        bucket_name=TEST_BUCKET,
        local_store=str(tmp_path) + "/",
    )


def test_upload_and_download_from_minio(minio_handler, tmp_path):
    """Test file upload and download cycle."""
    # Upload file
    assert minio_handler.put_file("test.txt") is True

    # Change local store to download to different location
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    os.environ["LOCAL_STORE"] = str(results_dir) + "/"

    # Create new handler with updated local store
    download_handler = FileAssets.get_asset(
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        bucket_name=TEST_BUCKET,
        local_store=str(results_dir) + "/",
    )

    # Download file
    assert download_handler.get_file("test.txt") is True

    # Download again to check if it exists
    assert download_handler.get_file("test.txt") is True

    # Delete remote file
    assert download_handler.del_file("test.txt") is True

    # Delete local copy
    assert download_handler.del_local_file("test.txt") is True


def test_get_folder_from_minio(minio_handler):
    """Test folder upload and download."""
    # Upload folder
    assert minio_handler.put_file("test_folder/test2.txt") is True

    # Download folder
    assert minio_handler.get_folder("test_folder") is True

    # Cleanup
    assert minio_handler.del_file("test_folder/test2.txt") is True


def test_get_upload_access(minio_handler):
    """Test presigned upload URL generation."""
    url = minio_handler.get_upload_access("test.txt")
    assert url is not None
    assert isinstance(url, str)
    assert url.startswith("http")


def test_get_download_access_private_object(minio_handler):
    """Test presigned download URL with bucket policy."""
    # Upload test file
    assert minio_handler.put_file("test.txt") is True

    # Set bucket policy to deny direct access
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Deny",
                "Principal": {"AWS": "*"},
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{TEST_BUCKET}/test.txt",
            },
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{TEST_BUCKET}/test2.txt",
            },
        ],
    }

    # Verify direct access is denied
    assert (
        requests.get(f"http://{minio_handler.host}/{TEST_BUCKET}/test.txt").status_code
        == 403
    )

    # Set bucket policy
    minio_handler.client.set_bucket_policy(TEST_BUCKET, json.dumps(policy))

    # Generate presigned URL with custom filename
    url = minio_handler.get_access(
        "test.txt", short=False, download_filename="novi.txt"
    )
    assert "novi.txt" in url

    # Presigned URL should work even with deny policy
    assert requests.get(url).status_code == 200

    # Cleanup
    assert minio_handler.del_file("test.txt") is True


def test_get_access_for_public(minio_handler):
    """Test public URL generation."""
    # Upload test file
    assert minio_handler.put_file("test_folder/test2.txt") is True

    # Get public URL
    url = minio_handler.get_access("test_folder", short=True)
    expected = f"http://localhost:9000/{TEST_BUCKET}/test_folder"
    assert url == expected

    # Cleanup
    assert minio_handler.del_file("test_folder/test2.txt") is True


def test_get_folder_size(minio_handler):
    """Test folder size calculation."""
    # Upload test file
    assert minio_handler.put_file("test_folder/test2.txt") is True

    # Check folder size
    size = minio_handler.get_size("test_folder")
    assert size == 19  # Size of "This is test2 file."

    # Cleanup
    assert minio_handler.del_file("test_folder/test2.txt") is True


def test_check_if_file_exists(minio_handler):
    """Test file existence checking."""
    # Upload test file
    assert minio_handler.put_file("test_folder/test2.txt") is True

    # Check existing file
    assert minio_handler.check_if_exists("test_folder/test2.txt") is True

    # Check non-existing file
    assert minio_handler.check_if_exists("test_folder/nonexistent.txt") is False

    # Cleanup
    assert minio_handler.del_file("test_folder/test2.txt") is True
