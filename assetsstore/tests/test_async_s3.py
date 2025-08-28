from pathlib import Path

import aioboto3
import pytest

from assetsstore.assets.s3 import AsyncS3Files


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
    fs = AsyncS3Files(
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        bucket_name=TEST_BUCKET,
        bucket_region=AWS_REGION,
        local_store=str(tmp_path) + "/",
        endpoint_url=MINIO_ENDPOINT,
    )
    return fs


async def test_put_get_del_file(s3files: AsyncS3Files, tmp_path: Path):
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


async def test_presigned_url(s3files: AsyncS3Files):
    """Generate a presigned GET URL – should come back as an HTTP URL string."""

    url = await s3files.get_access("does_not_exist.txt", seconds=60, short=False)
    assert isinstance(url, str) and url.startswith("http")


async def test_check_if_exists_missing(s3files: AsyncS3Files):
    """Test existence check for non-existent file."""
    assert await s3files.check_if_exists("does_not_exist.txt") is False


async def test_get_size_empty_folder(s3files: AsyncS3Files):
    """Test get_size on empty folder."""
    size = await s3files.get_size("empty_folder/")
    assert size == 0


def test_progress_percentage():
    """Test ProgressPercentage callback with threading safety."""
    from unittest.mock import patch
    from assetsstore.assets.s3.async_s3_files import ProgressPercentage

    # Capture logger output
    with patch("assetsstore.assets.s3.async_s3_files.logger") as mock_logger:
        progress = ProgressPercentage("test.txt", 100.0)

        # Test initial state
        assert progress._filename == "test.txt"
        assert progress._size == 100.0
        assert progress._seen_so_far == 0

        # Test progress updates
        progress(25)  # 25%
        progress(25)  # 50%
        progress(50)  # 100%

        # Check final state
        assert progress._seen_so_far == 100

        # Verify logging was called with progress info
        assert mock_logger.info.call_count == 3
        # Check that the last call contains 100%
        last_call_args = mock_logger.info.call_args_list[-1]
        assert "test.txt" in str(last_call_args)
        assert "100.0" in str(last_call_args)


def test_progress_percentage_zero_size():
    """Test ProgressPercentage with zero size (edge case)."""
    from assetsstore.assets.s3.async_s3_files import ProgressPercentage

    progress = ProgressPercentage("empty.txt", 0)
    assert progress._size == 1.0  # Should default to 1.0 to avoid division by zero

    # Should not crash
    progress(10)
    assert progress._seen_so_far == 10


async def test_s3files_init_variations():
    """Test S3Files initialization with different parameter combinations."""
    # Test with all None (should use environment variables)
    fs1 = AsyncS3Files(None, None, None, None, None)
    assert fs1.local_store == "./"

    # Test with custom local store
    fs2 = AsyncS3Files(local_store="/custom/path/")
    assert fs2.local_store == "/custom/path/"

    # Test with minimal credentials
    fs3 = AsyncS3Files("key", "secret", "bucket", "region")
    assert fs3.aws_access_key_id == "key"
    assert fs3.aws_secret_access_key == "secret"
    assert fs3.s3_bucket_name == "bucket"
    assert fs3.region_name == "region"


async def test_get_access_short_url(s3files: AsyncS3Files):
    """Test get_access with short=True returns public S3 URL."""
    url = await s3files.get_access("test.txt", short=True)
    expected = f"https://{TEST_BUCKET}.s3.amazonaws.com/test.txt"
    assert url == expected


async def test_get_access_with_download_filename(s3files: AsyncS3Files):
    """Test get_access with custom download filename."""
    url = await s3files.get_access(
        "test.txt", seconds=60, download_filename="custom.txt"
    )
    assert isinstance(url, str)
    assert url.startswith("http")
    # Should contain the custom filename in the response disposition
    assert "custom.txt" in url


async def test_get_upload_access(s3files: AsyncS3Files):
    """Test get_upload_access generates presigned PUT URL."""
    url = await s3files.get_upload_access("upload.txt", seconds=3600)
    assert isinstance(url, str)
    assert url.startswith("http")
    # MinIO URL should contain the endpoint
    assert "localhost:9000" in url


async def test_get_size_with_files(s3files: AsyncS3Files, tmp_path: Path):
    """Test get_size with actual files in folder."""
    # Create and upload test files
    file1 = tmp_path / "folder" / "file1.txt"
    file2 = tmp_path / "folder" / "file2.txt"
    file1.parent.mkdir()
    file1.write_text("content1")
    file2.write_text("content22")

    # Upload files
    await s3files.put_file("folder/file1.txt")
    await s3files.put_file("folder/file2.txt")

    # Test folder size
    size = await s3files.get_size("folder/")
    assert size > 0  # Should have some size

    # Cleanup
    await s3files.del_file("folder/file1.txt")
    await s3files.del_file("folder/file2.txt")


async def test_get_file_already_exists(s3files: AsyncS3Files, tmp_path: Path):
    """Test get_file when file already exists locally."""
    filename = "existing.txt"
    local_path = tmp_path / filename
    content = b"existing content"
    local_path.write_bytes(content)

    # Upload first
    await s3files.put_file(filename)

    # File already exists locally, should return True without downloading
    result = await s3files.get_file(filename)
    assert result is True
    assert local_path.read_bytes() == content  # Content unchanged

    # Cleanup
    await s3files.del_file(filename)


async def test_get_folder(s3files: AsyncS3Files, tmp_path: Path):
    """Test downloading entire folder."""
    # Create folder structure
    folder_path = tmp_path / "test_folder"
    folder_path.mkdir()
    (folder_path / "file1.txt").write_text("content1")
    (folder_path / "file2.txt").write_text("content2")

    # Upload folder
    await s3files.put_file("test_folder/file1.txt")
    await s3files.put_file("test_folder/file2.txt")

    # Remove local files
    (folder_path / "file1.txt").unlink()
    (folder_path / "file2.txt").unlink()

    # Download folder
    result = await s3files.get_folder("test_folder/")
    assert result is True

    # Verify files were downloaded
    assert (folder_path / "file1.txt").exists()
    assert (folder_path / "file2.txt").exists()
    assert (folder_path / "file1.txt").read_text() == "content1"
    assert (folder_path / "file2.txt").read_text() == "content2"

    # Cleanup
    await s3files.del_folder("test_folder/")


async def test_del_folder(s3files: AsyncS3Files, tmp_path: Path):
    """Test deleting entire folder."""
    # Create and upload test folder
    folder_path = tmp_path / "delete_folder"
    folder_path.mkdir()
    (folder_path / "file1.txt").write_text("delete1")
    (folder_path / "file2.txt").write_text("delete2")

    await s3files.put_file("delete_folder/file1.txt")
    await s3files.put_file("delete_folder/file2.txt")

    # Verify files exist
    assert await s3files.check_if_exists("delete_folder/file1.txt") is True
    assert await s3files.check_if_exists("delete_folder/file2.txt") is True

    # Delete folder
    result = await s3files.del_folder("delete_folder/")
    assert result is True

    # Verify files are gone
    assert await s3files.check_if_exists("delete_folder/file1.txt") is False
    assert await s3files.check_if_exists("delete_folder/file2.txt") is False


async def test_del_file_archive(s3files: AsyncS3Files, tmp_path: Path):
    """Test del_file with archive=True (Glacier storage)."""
    filename = "archive_test.txt"
    local_path = tmp_path / filename
    local_path.write_text("archive this")

    # Upload file
    await s3files.put_file(filename)
    assert await s3files.check_if_exists(filename) is True

    # Archive file (move to Glacier) - MinIO doesn't support Glacier, so this should fail
    result = await s3files.del_file(filename, archive=True)
    assert result is False  # Should fail in MinIO due to unsupported storage class

    # Regular delete should work
    result = await s3files.del_file(filename, archive=False)
    assert result is True
    assert await s3files.check_if_exists(filename) is False


async def test_error_handling_invalid_bucket():
    """Test error handling with invalid bucket configuration."""
    # Create S3Files with invalid bucket
    fs = AsyncS3Files(
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        bucket_name="nonexistent-bucket-12345",
        bucket_region=AWS_REGION,
        local_store="/tmp/",
    )
    fs._endpoint_url = MINIO_ENDPOINT

    # Operations that check bucket existence should fail
    assert await fs.check_if_exists("test.txt") is False
    assert await fs.get_size("folder/") == 0

    # Presigned URLs can be generated even for invalid buckets (they'll fail when used)
    access_url = await fs.get_access("test.txt")
    upload_url = await fs.get_upload_access("test.txt")
    assert isinstance(access_url, str) and access_url.startswith("http")
    assert isinstance(upload_url, str) and upload_url.startswith("http")

    # File operations should fail
    assert await fs.get_file("test.txt") is False
    assert await fs.put_file("test.txt") is False  # Will fail due to missing local file
    assert await fs.del_file("test.txt") is False
    assert await fs.get_folder("folder/") is False
    assert await fs.del_folder("folder/") is False


async def test_error_handling_invalid_credentials():
    """Test error handling with invalid credentials."""
    fs = AsyncS3Files(
        access_key="invalid",
        secret_key="invalid",
        bucket_name=TEST_BUCKET,
        bucket_region=AWS_REGION,
        local_store="/tmp/",
    )
    fs._endpoint_url = MINIO_ENDPOINT

    # Operations should fail due to authentication
    assert await fs.check_if_exists("test.txt") is False

    # Presigned URLs can be generated with invalid credentials (they'll fail when used)
    access_url = await fs.get_access("test.txt")
    assert isinstance(access_url, str) and access_url.startswith("http")


async def test_put_file_missing_local(s3files: AsyncS3Files):
    """Test put_file with missing local file."""
    result = await s3files.put_file("nonexistent.txt")
    assert result is False


async def test_get_file_missing_remote(s3files: AsyncS3Files):
    """Test get_file with missing remote file."""
    result = await s3files.get_file("definitely_missing.txt")
    assert result is False


async def test_get_folder_empty(s3files: AsyncS3Files):
    """Test get_folder with empty/nonexistent folder."""
    result = await s3files.get_folder("empty_nonexistent_folder/")
    assert result is True  # Should succeed even if no files


async def test_del_folder_empty(s3files: AsyncS3Files):
    """Test del_folder with empty/nonexistent folder."""
    result = await s3files.del_folder("empty_nonexistent_folder/")
    assert result is True  # Should succeed even if no files


async def test_progress_percentage_thread_safety_with_async():
    """Test that ProgressPercentage doesn't block async operations."""
    import asyncio
    import time
    from assetsstore.assets.s3.async_s3_files import ProgressPercentage

    progress = ProgressPercentage("concurrent_test.txt", 1000.0)

    async def simulate_async_work():
        """Simulate async work that should not be blocked by progress callbacks."""
        await asyncio.sleep(0.01)  # Small async delay
        return "async_done"

    def simulate_callback_work():
        """Simulate multiple rapid progress callbacks from different threads."""
        import threading

        def callback_thread(thread_id):
            for i in range(10):
                progress(10)  # Each thread reports 10 bytes, 10 times
                time.sleep(0.001)  # Small delay to simulate real work

        # Start multiple threads simulating concurrent callbacks
        threads = []
        for i in range(3):
            t = threading.Thread(target=callback_thread, args=(i,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

    # Run both async work and callback work concurrently
    start_time = time.time()

    # Start callback work in thread pool
    loop = asyncio.get_event_loop()
    callback_task = loop.run_in_executor(None, simulate_callback_work)

    # Run async work
    async_result = await simulate_async_work()

    # Wait for callback work to complete
    await callback_task

    end_time = time.time()

    # Verify async work completed
    assert async_result == "async_done"

    # Verify progress was tracked correctly (3 threads * 10 calls * 10 bytes = 300)
    assert progress._seen_so_far == 300

    # Should complete in reasonable time (not blocked)
    assert end_time - start_time < 1.0  # Should be much faster than 1 second


async def test_real_file_transfer_with_progress(s3files: AsyncS3Files, tmp_path: Path):
    """Test actual file transfer with progress callbacks to ensure no async blocking."""
    import asyncio

    # Create a larger file to ensure progress callbacks are triggered
    large_file = tmp_path / "large_test.txt"
    content = b"x" * 10000  # 10KB file
    large_file.write_bytes(content)

    async def concurrent_async_work():
        """Simulate other async work happening during file transfer."""
        results = []
        for i in range(5):
            await asyncio.sleep(0.01)  # Small delays
            results.append(f"async_work_{i}")
        return results

    # Start concurrent async work and file upload
    start_time = asyncio.get_event_loop().time()

    # Run file upload and async work concurrently
    upload_task = s3files.put_file("large_test.txt")
    async_work_task = concurrent_async_work()

    # Both should complete without blocking each other
    upload_result, async_results = await asyncio.gather(upload_task, async_work_task)

    end_time = asyncio.get_event_loop().time()

    # Verify both completed successfully
    assert upload_result is True
    assert len(async_results) == 5
    assert async_results[0] == "async_work_0"

    # Verify file exists remotely
    assert await s3files.check_if_exists("large_test.txt") is True

    # Test download with concurrent async work
    large_file.unlink()  # Remove local copy

    download_task = s3files.get_file("large_test.txt")
    async_work_task2 = concurrent_async_work()

    download_result, async_results2 = await asyncio.gather(
        download_task, async_work_task2
    )

    # Verify download completed successfully
    assert download_result is True
    assert large_file.exists()
    assert large_file.read_bytes() == content
    assert len(async_results2) == 5

    # Cleanup
    await s3files.del_file("large_test.txt")

    # Total time should be reasonable (progress callbacks didn't block event loop)
    total_time = end_time - start_time
    assert total_time < 5.0  # Should complete much faster than 5 seconds
