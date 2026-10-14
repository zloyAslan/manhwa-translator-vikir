"""
Master Downloader module package.
"""

from .tg_cloud_relay import (
    TelegramCloudRelay,
    format_chapter_filename,
    format_chapter_caption,
    generate_title_code,
    extract_chapter_number,
    parse_chapter_range
)

__all__ = [
    "TelegramCloudRelay",
    "format_chapter_filename",
    "format_chapter_caption",
    "generate_title_code",
    "extract_chapter_number",
    "parse_chapter_range"
]
