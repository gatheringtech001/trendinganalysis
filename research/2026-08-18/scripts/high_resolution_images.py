from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import socket
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from PIL import Image


MAX_DOWNLOAD_BYTES = 20_000_000
MIN_PIXELS = 800_000
MIN_LONG_EDGE = 1_000
MIN_SHORT_EDGE = 600
SHEIN_THUMBNAIL = re.compile(r"_thumbnail_\d+x\d*(?=\.[^.]+$)", re.IGNORECASE)
WORDPRESS_SIZE = re.compile(r"-\d{2,4}x\d{2,4}(?=\.[^.]+$)", re.IGNORECASE)


@dataclass(frozen=True)
class DownloadedImage:
    store_id: str
    product_id: str
    position: int
    source_url: str
    resolved_url: str
    path: str
    width: int
    height: int
    bytes: int
    sha256: str
    mime_type: str
    cache_hit: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def high_resolution_candidates(store_id: str, source_url: str) -> list[str]:
    parts = urlsplit(source_url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("image URL must be an absolute HTTP URL")
    paths = []
    if store_id == "aloruh_shein":
        paths.append(SHEIN_THUMBNAIL.sub("", parts.path))
    if store_id == "aloruh_local" and "/wp-content/uploads/" in parts.path:
        paths.append(WORDPRESS_SIZE.sub("", parts.path))
    urls = [urlunsplit((parts.scheme, parts.netloc, path, parts.query, "")) for path in paths]
    urls.append(urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, "")))
    return list(dict.fromkeys(urls))


def _validate_public_host(url: str) -> None:
    hostname = urlsplit(url).hostname
    if not hostname:
        raise ValueError("image URL has no hostname")
    addresses = {item[4][0] for item in socket.getaddrinfo(hostname, None)}
    if not addresses:
        raise ValueError("image hostname did not resolve")
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValueError("image URL must resolve only to public addresses")


def inspect_image(content: bytes) -> tuple[int, int, str, str]:
    with Image.open(BytesIO(content)) as image:
        image.verify()
    with Image.open(BytesIO(content)) as image:
        width, height = image.size
        image_format = (image.format or "").upper()
    mime = Image.MIME.get(image_format)
    suffix = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(image_format)
    if not mime or not suffix:
        raise ValueError(f"unsupported image format: {image_format or 'unknown'}")
    return width, height, mime, suffix


def _is_high_resolution(width: int, height: int) -> bool:
    return (
        width * height >= MIN_PIXELS
        and max(width, height) >= MIN_LONG_EDGE
        and min(width, height) >= MIN_SHORT_EDGE
    )


def _download(url: str, timeout: int) -> bytes:
    _validate_public_host(url)
    request = Request(url, headers={"User-Agent": "FashionScope/1.0"})
    with urlopen(request, timeout=timeout) as response:
        content = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(content) > MAX_DOWNLOAD_BYTES:
        raise ValueError("image exceeds 20 MB download limit")
    return content


def _cache_key(store_id: str, source_url: str) -> str:
    value = f"{store_id}\0{source_url}".encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def _cached_image(
    cache_dir: Path, cache_key: str, *, store_id: str, product_id: str,
    position: int, source_url: str,
) -> DownloadedImage | None:
    metadata_path = cache_dir / f"{cache_key}.json"
    if not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        file_name = metadata["file"]
        if Path(file_name).name != file_name:
            return None
        path = cache_dir / file_name
        if path.stat().st_size > MAX_DOWNLOAD_BYTES:
            return None
        content = path.read_bytes()
        width, height, mime, _suffix = inspect_image(content)
        digest = hashlib.sha256(content).hexdigest()
        if not _is_high_resolution(width, height):
            return None
        if digest != metadata["sha256"] or len(content) != metadata["bytes"]:
            return None
        return DownloadedImage(
            store_id, product_id, position, source_url, metadata["resolved_url"],
            str(path), width, height, len(content), digest, mime, True,
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return None


def _write_cached_image(
    cache_dir: Path, cache_key: str, content: bytes, *, resolved_url: str,
    width: int, height: int, mime: str, suffix: str, digest: str,
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / f"{cache_key}{suffix}"
    building = path.with_suffix(path.suffix + ".building")
    building.write_bytes(content)
    os.replace(building, path)
    metadata = {
        "file": path.name, "resolved_url": resolved_url, "width": width,
        "height": height, "bytes": len(content), "sha256": digest,
        "mime_type": mime,
    }
    metadata_path = cache_dir / f"{cache_key}.json"
    metadata_building = metadata_path.with_suffix(".json.building")
    metadata_building.write_text(json.dumps(metadata), encoding="utf-8")
    os.replace(metadata_building, metadata_path)
    return path


def download_high_resolution_image(
    *, store_id: str, product_id: str, position: int, source_url: str,
    output_dir: Path, timeout: int = 30, cache_dir: Path | None = None,
) -> DownloadedImage:
    cache_key = _cache_key(store_id, source_url)
    if cache_dir is not None:
        cached = _cached_image(
            Path(cache_dir), cache_key, store_id=store_id, product_id=product_id,
            position=position, source_url=source_url,
        )
        if cached is not None:
            return cached
    errors = []
    for candidate in high_resolution_candidates(store_id, source_url):
        try:
            content = _download(candidate, timeout)
            width, height, mime, suffix = inspect_image(content)
            if not _is_high_resolution(width, height):
                raise ValueError(f"resolution {width}x{height} is below HD threshold")
            digest = hashlib.sha256(content).hexdigest()
            safe_product = re.sub(r"[^A-Za-z0-9._-]+", "_", product_id)[:100]
            if cache_dir is not None:
                path = _write_cached_image(
                    Path(cache_dir), cache_key, content, resolved_url=candidate,
                    width=width, height=height, mime=mime, suffix=suffix,
                    digest=digest,
                )
            else:
                output_dir.mkdir(parents=True, exist_ok=True)
                path = output_dir / f"{store_id}__{safe_product}__{position}__{digest[:12]}{suffix}"
                path.write_bytes(content)
            return DownloadedImage(
                store_id, product_id, position, source_url, candidate, str(path),
                width, height, len(content), digest, mime,
            )
        except Exception as error:  # Try the original URL after an upgrade fails.
            errors.append(f"{candidate}: {error}")
    raise ValueError("no HD image candidate succeeded; " + " | ".join(errors))
