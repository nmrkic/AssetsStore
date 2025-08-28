import pytest
import os
from assetsstore.assets import FileAssets


def test_it_raises_error_if_asset_store_is_not_set():
    with pytest.raises(Exception) as exc:
        FileAssets.get_asset()
    assert "Environment variable ASSET_STORE is not set." in str(exc.value)


def test_it_uploads_and_downloads_from_local(tmp_path):
    # Create a temporary test file instead of using shared fixture
    test_file = tmp_path / "fixtures" / "test.txt"
    test_file.parent.mkdir(parents=True)
    test_file.write_text("This is a test file for unit tests.")

    results_dir = tmp_path / "results"
    results_dir.mkdir()

    os.environ["ASSET_STORE"] = "LocalFiles"
    handler = FileAssets.get_asset(
        location=str(results_dir / "remote") + "/",
        local_store=str(test_file.parent) + "/",
    )
    assert handler.put_file("test.txt") is True

    handler = FileAssets.get_asset(
        location=str(results_dir / "remote") + "/",
        local_store=str(results_dir) + "/",
    )
    assert handler.get_file("test.txt") is True

    # get again to check if it exists
    assert handler.get_file("test.txt") is True

    # delete remote file
    assert handler.del_file("test.txt") is True

    # delete local file
    assert handler.del_local_file("test.txt") is True
