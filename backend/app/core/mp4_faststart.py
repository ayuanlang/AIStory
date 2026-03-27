import os
import struct
import tempfile


_DEFAULT_FASTSTART_MAX_MB = 64


def _get_faststart_max_bytes() -> int:
    raw = str(os.getenv("MP4_FASTSTART_MAX_MB", str(_DEFAULT_FASTSTART_MAX_MB)) or "").strip()
    try:
        max_mb = int(raw)
    except Exception:
        max_mb = _DEFAULT_FASTSTART_MAX_MB
    if max_mb <= 0:
        return 0
    return max_mb * 1024 * 1024


_CONTAINER_BOX_TYPES = {
    "moov",
    "trak",
    "mdia",
    "minf",
    "stbl",
    "edts",
    "dinf",
    "mvex",
    "moof",
    "traf",
    "mfra",
    "udta",
    "meta",
    "ilst",
}

_FULLBOX_CONTAINER_TYPES = {"meta"}


def optimize_mp4_faststart(file_path: str) -> bool:
    if not file_path or not str(file_path).lower().endswith(".mp4"):
        return False
    if not os.path.exists(file_path):
        return False

    max_bytes = _get_faststart_max_bytes()
    if max_bytes > 0:
        try:
            file_size = os.path.getsize(file_path)
        except Exception:
            file_size = 0
        if file_size > max_bytes:
            return False

    with open(file_path, "rb") as handle:
        data = handle.read()

    top_level_boxes = list(_iter_boxes(data, 0, len(data)))
    moov_box = _find_box(top_level_boxes, "moov")
    mdat_box = _find_box(top_level_boxes, "mdat")
    if not moov_box or not mdat_box:
        return False
    if moov_box["start"] < mdat_box["start"]:
        return False

    moov_bytes = bytearray(data[moov_box["start"]:moov_box["end"]])
    _patch_moov_chunk_offsets(moov_bytes, moov_box["size"])

    reordered_parts = []
    moov_inserted = False
    for box in top_level_boxes:
        if box["type"] == "moov":
            continue
        reordered_parts.append(data[box["start"]:box["end"]])
        if not moov_inserted and box["type"] == "ftyp":
            reordered_parts.append(bytes(moov_bytes))
            moov_inserted = True

    if not moov_inserted:
        reordered_parts.insert(0, bytes(moov_bytes))

    new_data = b"".join(reordered_parts)
    if len(new_data) != len(data):
        raise ValueError("mp4 faststart rewrite changed file size unexpectedly")

    with tempfile.NamedTemporaryFile(delete=False, dir=os.path.dirname(file_path), suffix=".mp4") as tmp:
        tmp.write(new_data)
        temp_path = tmp.name

    os.replace(temp_path, file_path)
    return True


def _find_box(boxes, box_type: str):
    for box in boxes:
        if box["type"] == box_type:
            return box
    return None


def _iter_boxes(buffer: bytes, start: int, end: int):
    cursor = start
    while cursor + 8 <= end:
        size = struct.unpack_from(">I", buffer, cursor)[0]
        box_type = bytes(buffer[cursor + 4:cursor + 8]).decode("latin1")
        header_size = 8

        if size == 1:
            if cursor + 16 > end:
                raise ValueError("invalid mp4 extended-size atom")
            size = struct.unpack_from(">Q", buffer, cursor + 8)[0]
            header_size = 16
        elif size == 0:
            size = end - cursor

        if size < header_size:
            raise ValueError(f"invalid mp4 atom size for {box_type}")

        box_end = cursor + size
        if box_end > end:
            raise ValueError(f"mp4 atom exceeds bounds for {box_type}")

        yield {
            "type": box_type,
            "start": cursor,
            "end": box_end,
            "size": size,
            "header_size": header_size,
            "payload_start": cursor + header_size,
            "payload_end": box_end,
        }
        cursor = box_end


def _patch_moov_chunk_offsets(moov_bytes: bytearray, delta: int) -> None:
    moov_header_size = _box_header_size(moov_bytes, 0, len(moov_bytes))
    _patch_boxes(moov_bytes, moov_header_size, len(moov_bytes), delta)


def _patch_boxes(buffer: bytearray, start: int, end: int, delta: int) -> None:
    for box in _iter_boxes(buffer, start, end):
        box_type = box["type"]
        if box_type == "stco":
            _patch_stco(buffer, box["payload_start"], box["payload_end"], delta)
            continue
        if box_type == "co64":
            _patch_co64(buffer, box["payload_start"], box["payload_end"], delta)
            continue
        if box_type not in _CONTAINER_BOX_TYPES:
            continue

        child_start = box["payload_start"]
        if box_type in _FULLBOX_CONTAINER_TYPES:
            child_start += 4
        if child_start < box["payload_end"]:
            _patch_boxes(buffer, child_start, box["payload_end"], delta)


def _patch_stco(buffer: bytearray, payload_start: int, payload_end: int, delta: int) -> None:
    if payload_start + 8 > payload_end:
        raise ValueError("invalid stco atom")
    entry_count = struct.unpack_from(">I", buffer, payload_start + 4)[0]
    entries_start = payload_start + 8
    entries_end = entries_start + (entry_count * 4)
    if entries_end > payload_end:
        raise ValueError("stco atom truncated")
    for index in range(entry_count):
        offset_pos = entries_start + (index * 4)
        current_offset = struct.unpack_from(">I", buffer, offset_pos)[0]
        new_offset = current_offset + delta
        if new_offset > 0xFFFFFFFF:
            raise ValueError("stco offset overflow during faststart optimization")
        struct.pack_into(">I", buffer, offset_pos, new_offset)


def _patch_co64(buffer: bytearray, payload_start: int, payload_end: int, delta: int) -> None:
    if payload_start + 8 > payload_end:
        raise ValueError("invalid co64 atom")
    entry_count = struct.unpack_from(">I", buffer, payload_start + 4)[0]
    entries_start = payload_start + 8
    entries_end = entries_start + (entry_count * 8)
    if entries_end > payload_end:
        raise ValueError("co64 atom truncated")
    for index in range(entry_count):
        offset_pos = entries_start + (index * 8)
        current_offset = struct.unpack_from(">Q", buffer, offset_pos)[0]
        struct.pack_into(">Q", buffer, offset_pos, current_offset + delta)


def _box_header_size(buffer: bytes, start: int, end: int) -> int:
    if start + 8 > end:
        raise ValueError("invalid mp4 atom header")
    size = struct.unpack_from(">I", buffer, start)[0]
    if size == 1:
        if start + 16 > end:
            raise ValueError("invalid mp4 extended atom header")
        return 16
    return 8