"""Subtitle detection and on-the-fly WebVTT conversion service."""

import logging
import re
from typing import ClassVar

from app.interfaces.storage import StorageBackend
from app.interfaces.types import StoredFile
from app.models.user import User
from app.schemas.files import SubtitleListResponse, SubtitleTrackResponse
from app.services.drive import DriveApiStorage

logger = logging.getLogger(__name__)

# Standard mapping from common language codes and language names to (ISO-639-1, Display Name)
LANG_MAP: dict[str, tuple[str, str]] = {
    "en": ("en", "English"),
    "eng": ("en", "English"),
    "english": ("en", "English"),
    "es": ("es", "Spanish"),
    "spa": ("es", "Spanish"),
    "spanish": ("es", "Spanish"),
    "esp": ("es", "Spanish"),
    "fr": ("fr", "French"),
    "fre": ("fr", "French"),
    "fra": ("fr", "French"),
    "french": ("fr", "French"),
    "de": ("de", "German"),
    "ger": ("de", "German"),
    "deu": ("de", "German"),
    "german": ("de", "German"),
    "it": ("it", "Italian"),
    "ita": ("it", "Italian"),
    "italian": ("it", "Italian"),
    "pt": ("pt", "Portuguese"),
    "por": ("pt", "Portuguese"),
    "portuguese": ("pt", "Portuguese"),
    "br": ("pt", "Portuguese (BR)"),
    "pob": ("pt", "Portuguese (BR)"),
    "ru": ("ru", "Russian"),
    "rus": ("ru", "Russian"),
    "russian": ("ru", "Russian"),
    "ja": ("ja", "Japanese"),
    "jpn": ("ja", "Japanese"),
    "japanese": ("ja", "Japanese"),
    "ko": ("ko", "Korean"),
    "kor": ("ko", "Korean"),
    "korean": ("ko", "Korean"),
    "zh": ("zh", "Chinese"),
    "chi": ("zh", "Chinese"),
    "zho": ("zh", "Chinese"),
    "chinese": ("zh", "Chinese"),
    "hi": ("hi", "Hindi"),
    "hin": ("hi", "Hindi"),
    "hindi": ("hi", "Hindi"),
    "ar": ("ar", "Arabic"),
    "ara": ("ar", "Arabic"),
    "arabic": ("ar", "Arabic"),
    "nl": ("nl", "Dutch"),
    "dut": ("nl", "Dutch"),
    "dutch": ("nl", "Dutch"),
    "pl": ("pl", "Polish"),
    "pol": ("pl", "Polish"),
    "polish": ("pl", "Polish"),
    "tr": ("tr", "Turkish"),
    "tur": ("tr", "Turkish"),
    "turkish": ("tr", "Turkish"),
    "sv": ("sv", "Swedish"),
    "swe": ("sv", "Swedish"),
    "swedish": ("sv", "Swedish"),
    "da": ("da", "Danish"),
    "dan": ("da", "Danish"),
    "danish": ("da", "Danish"),
    "fi": ("fi", "Finnish"),
    "fin": ("fi", "Finnish"),
    "finnish": ("fi", "Finnish"),
    "no": ("no", "Norwegian"),
    "nor": ("no", "Norwegian"),
    "norwegian": ("no", "Norwegian"),
    "cs": ("cs", "Czech"),
    "cze": ("cs", "Czech"),
    "ces": ("cs", "Czech"),
    "czech": ("cs", "Czech"),
    "el": ("el", "Greek"),
    "gre": ("el", "Greek"),
    "greek": ("el", "Greek"),
    "he": ("he", "Hebrew"),
    "heb": ("he", "Hebrew"),
    "hebrew": ("he", "Hebrew"),
    "uk": ("uk", "Ukrainian"),
    "ukr": ("uk", "Ukrainian"),
    "ukrainian": ("uk", "Ukrainian"),
}

MEDIA_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".flv", ".wmv"}
SUBTITLE_EXTENSIONS = {".srt", ".vtt"}


def parse_subtitle_info(sub_name: str, media_stem: str) -> tuple[str, str]:
    """Extract (language_code, label) from a subtitle filename relative to the media name."""
    sub_lower = sub_name.lower()
    # Strip known extension
    for ext in SUBTITLE_EXTENSIONS:
        if sub_lower.endswith(ext):
            sub_name_stem = sub_name[: -len(ext)]
            break
    else:
        sub_name_stem = sub_name

    # Check for modifiers like forced, sdh, cc
    is_forced = bool(re.search(r"\bforced\b", sub_name_stem, re.IGNORECASE))
    is_sdh = bool(re.search(r"\b(sdh|cc)\b", sub_name_stem, re.IGNORECASE))

    # Strip the media stem if it is a prefix
    remaining = sub_name_stem
    if media_stem and sub_name_stem.lower().startswith(media_stem.lower()):
        remaining = sub_name_stem[len(media_stem) :].strip("._- ")

    # Tokenize remainder
    tokens = re.split(r"[._\-\s]+", remaining)
    lang_code = "und"
    lang_label = "Unknown"

    for token in tokens:
        t_clean = token.lower()
        if t_clean in LANG_MAP:
            lang_code, lang_label = LANG_MAP[t_clean]
            break

    # If no language token matched, default label
    if lang_label == "Unknown":
        if remaining:
            lang_label = remaining.replace("_", " ").title()
        else:
            lang_label = "Default"

    # Append modifiers if applicable
    if is_forced and "forced" not in lang_label.lower():
        lang_label = f"{lang_label} (Forced)"
    elif is_sdh and "sdh" not in lang_label.lower() and "cc" not in lang_label.lower():
        lang_label = f"{lang_label} (SDH)"

    return lang_code, lang_label


def convert_srt_to_vtt(srt_text: str) -> str:
    """Convert standard SubRip (SRT) format to WebVTT format.

    - Normalizes line endings to LF.
    - Strips UTF-8 BOM if present.
    - Converts comma millisecond separators (00:01:20,500) to period (00:01:20.500).
    - Preserves cue structure, formatting tags, and cue timings.
    - Ensures valid WEBVTT header.
    """
    if not srt_text:
        return "WEBVTT\n\n"

    # Clean BOM and linebreaks
    text = srt_text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")

    # If already valid WebVTT, return directly
    if text.strip().startswith("WEBVTT"):
        return text

    # SRT timestamp regex: HH:MM:SS,mmm --> HH:MM:SS,mmm
    # Replace comma before millisecond with a dot
    timestamp_pattern = re.compile(
        r"(\d{2}:\d{2}:\d{2}),(\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}),(\d{3})"
    )

    def _replace_ts(match: re.Match[str]) -> str:
        return f"{match.group(1)}.{match.group(2)} --> {match.group(3)}.{match.group(4)}"

    vtt_body = timestamp_pattern.sub(_replace_ts, text)

    # Clean redundant blank lines at the top
    vtt_body = vtt_body.lstrip()

    return f"WEBVTT\n\n{vtt_body}"


class SubtitleService:
    """Service to discover, list, and format subtitles for stored media files."""

    MEDIA_EXTENSIONS: ClassVar[set[str]] = MEDIA_EXTENSIONS
    SUBTITLE_EXTENSIONS: ClassVar[set[str]] = SUBTITLE_EXTENSIONS

    def __init__(self, storage: StorageBackend | None = None) -> None:
        self._storage = storage

    def _get_storage(self) -> StorageBackend:
        if self._storage is not None:
            return self._storage
        return DriveApiStorage()

    async def list_subtitles(self, user: User, file_id: str) -> SubtitleListResponse:
        """Find sidecar subtitle files matching the requested media file in storage."""
        storage = self._get_storage()
        media_file = await storage.get_file(user, file_id)

        parent_id = media_file.parent_id
        if not parent_id:
            return SubtitleListResponse(subtitles=[])

        folder_contents = await storage.list_folder(user, parent_id)

        # Determine media file stem
        media_name = media_file.name
        media_stem = media_name
        for ext in self.MEDIA_EXTENSIONS:
            if media_name.lower().endswith(ext):
                media_stem = media_name[: -len(ext)]
                break

        # Count total media files in directory
        sibling_media = [
            f
            for f in folder_contents
            if any(f.name.lower().endswith(ext) for ext in self.MEDIA_EXTENSIONS)
        ]

        sub_files: list[StoredFile] = []
        subs_folders: list[StoredFile] = []

        for item in folder_contents:
            lower = item.name.lower()
            if any(lower.endswith(ext) for ext in self.SUBTITLE_EXTENSIONS):
                sub_files.append(item)
            elif lower in {"subs", "subtitles"} and item.mime_type.endswith("folder"):
                subs_folders.append(item)

        # Also inspect "subs" or "subtitles" subfolders if present
        for sub_folder in subs_folders:
            try:
                sub_folder_items = await storage.list_folder(user, sub_folder.id)
                for item in sub_folder_items:
                    if any(item.name.lower().endswith(ext) for ext in self.SUBTITLE_EXTENSIONS):
                        sub_files.append(item)
            except Exception as err:
                logger.warning(
                    "Failed to inspect subfolder %s for subtitles: %s", sub_folder.id, err
                )

        # Match subtitle files to this media file
        tracks: list[SubtitleTrackResponse] = []
        for sf in sub_files:
            sf_lower = sf.name.lower()
            media_stem_lower = media_stem.lower()

            is_match = False
            # 1. Subtitle stem starts with or equals media stem
            if sf_lower.startswith(media_stem_lower):
                is_match = True
            # 2. Only one media file exists in this directory
            elif len(sibling_media) == 1:
                is_match = True
            # 3. Media stem appears somewhere inside subtitle name
            elif media_stem_lower in sf_lower:
                is_match = True

            if is_match:
                fmt = "vtt" if sf_lower.endswith(".vtt") else "srt"
                lang_code, label = parse_subtitle_info(sf.name, media_stem)
                tracks.append(
                    SubtitleTrackResponse(
                        id=sf.id,
                        name=sf.name,
                        label=label,
                        language=lang_code,
                        format=fmt,
                    )
                )

        # Sort tracks by label for stable ordering
        tracks.sort(key=lambda t: (t.language == "und", t.label))
        return SubtitleListResponse(subtitles=tracks)

    async def get_subtitle_content(self, user: User, file_id: str, sub_id: str) -> str:
        """Fetch, decode, and convert subtitle file content into valid WebVTT string."""
        storage = self._get_storage()

        # Verify access and get subtitle metadata
        sub_file = await storage.get_file(user, sub_id)

        # Read subtitle file bytes
        chunks: list[bytes] = []
        async for chunk in storage.open_range(user, sub_id, 0, None):
            chunks.append(chunk)
        raw_bytes = b"".join(chunks)

        # Decode using utf-8 with fallback encodings
        text = ""
        for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1", "iso-8859-1"):
            try:
                text = raw_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            text = raw_bytes.decode("utf-8", errors="replace")

        # Convert to WebVTT
        if sub_file.name.lower().endswith(".vtt"):
            if not text.lstrip("\ufeff").startswith("WEBVTT"):
                return f"WEBVTT\n\n{text.lstrip()}"
            return text.lstrip("\ufeff")

        return convert_srt_to_vtt(text)
