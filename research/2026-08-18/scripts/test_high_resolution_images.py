import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from high_resolution_images import download_high_resolution_image
from report_analysis_runner import _shared_image_cache, default_args


def jpeg_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (1000, 800), "white").save(stream, format="JPEG")
    return stream.getvalue()


class SharedImageCacheTest(unittest.TestCase):
    def test_report_jobs_share_cache_under_their_common_root(self):
        first = _shared_image_cache(default_args(), Path("jobs/one"))
        second = _shared_image_cache(default_args(), Path("jobs/two"))

        self.assertEqual(Path("jobs/_image_cache"), first)
        self.assertEqual(first, second)

    def test_reuses_valid_cached_image_across_report_jobs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "shared-cache"
            with patch("high_resolution_images._download", return_value=jpeg_bytes()) as fetch:
                first = download_high_resolution_image(
                    store_id="motel", product_id="one", position=1,
                    source_url="https://example.com/image.jpg",
                    output_dir=root / "job-one", cache_dir=cache,
                )
                second = download_high_resolution_image(
                    store_id="motel", product_id="two", position=1,
                    source_url="https://example.com/image.jpg",
                    output_dir=root / "job-two", cache_dir=cache,
                )

            self.assertEqual(1, fetch.call_count)
            self.assertEqual(first.path, second.path)
            self.assertEqual(first.sha256, second.sha256)
            self.assertFalse(first.cache_hit)
            self.assertTrue(second.cache_hit)
            self.assertTrue(Path(second.path).is_file())

    def test_redownloads_when_cached_image_is_corrupt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "shared-cache"
            with patch("high_resolution_images._download", return_value=jpeg_bytes()) as fetch:
                first = download_high_resolution_image(
                    store_id="motel", product_id="one", position=1,
                    source_url="https://example.com/image.jpg",
                    output_dir=root / "job-one", cache_dir=cache,
                )
                Path(first.path).write_bytes(b"broken")
                repaired = download_high_resolution_image(
                    store_id="motel", product_id="two", position=1,
                    source_url="https://example.com/image.jpg",
                    output_dir=root / "job-two", cache_dir=cache,
                )

            self.assertEqual(2, fetch.call_count)
            self.assertEqual(jpeg_bytes(), Path(repaired.path).read_bytes())


if __name__ == "__main__":
    unittest.main()
