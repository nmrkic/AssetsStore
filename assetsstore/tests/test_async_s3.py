from pathlib import Path

import aioboto3
import pytest

from assetsstore.assets.s3.async_s3_files import S3Files


MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "minio"
MINIO_SECRET_KEY = "minio123"
TEST_BUCKET = "test-bucket"
AWS_REGION = "us-east-1"


@pytest.fixture(scope="session", autouse=True)
async def ensure_minio_bucket():
    """Create *TEST_BUCKET* in the MinIO server if it is missing."""

    session = aioboto3.Session(
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name=AWS_REGION,
    )
    async with session.client("s3", endpoint_url=MINIO_ENDPOINT) as client:
        buckets = await client.list_buckets()
        if not any(b["Name"] == TEST_BUCKET for b in buckets.get("Buckets", [])):
            await client.create_bucket(Bucket=TEST_BUCKET)
    # tests run after bucket exists
    yield


@pytest.fixture()
async def s3files(tmp_path: Path):
    """Return S3Files instance configured for MinIO."""
    fs = S3Files(
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        bucket_name=TEST_BUCKET,
        bucket_region=AWS_REGION,
        local_store=str(tmp_path) + "/",
    )
    # Point helper to MinIO instead of AWS
    fs._endpoint_url = MINIO_ENDPOINT  # pylint: disable=protected-access
    return fs


async def test_put_get_del_file(s3files: S3Files, tmp_path: Path):
    """End-to-end upload, download and delete cycle against MinIO."""

    filename = "hello.txt"
    local_path = tmp_path / filename
    content = b"hello world"
    local_path.write_bytes(content)

    # Upload
    assert await s3files.put_file(filename) is True

    # Existence check (remote)
    assert await s3files.check_if_exists(filename) is True

    # Remove local copy then download again
    local_path.unlink()
    assert not local_path.exists()
    assert await s3files.get_file(filename) is True
    assert local_path.read_bytes() == content

    # Delete and ensure gone
    assert await s3files.del_file(filename) is True
    assert await s3files.check_if_exists(filename) is False


async def test_presigned_url(s3files: S3Files):
    """Generate a presigned GET URL – should come back as an HTTP URL string."""

    url = await s3files.get_access("does_not_exist.txt", seconds=60, short=False)
    assert isinstance(url, str) and url.startswith("http")


async def test_check_if_exists_missing(s3files: S3Files):
    """Test existence check for non-existent file."""
    assert await s3files.check_if_exists("does_not_exist.txt") is False


async def test_get_size_empty_folder(s3files: S3Files):
    """Test get_size on empty folder."""
    size = await s3files.get_size("empty_folder/")
    assert size == 0
