from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / ".tools" / "python"))

import UnityPy  # noqa: E402


VISIBLE_REPLACEMENTS = {
    "Hide": "Скрыть",
    "Auto": "Авто",
    "Log": "История",
}

UI_TEXT_OBJECTS = {
    226875: ("Auto", "Авто"),
    239535: ("Log", "История"),
    270905: ("Hide", "Скрыть"),
}

# DeckDetailUIViewController / Right Panel / Attr Panel / Txt Statictis.
# TMP_Text 3.0.6, m_lineSpacing: increase only this scrollable text field.
DECK_STATISTICS_OBJECT = 273009
DECK_LINE_SPACING_OFFSET = 340
DECK_LINE_SPACING = (5.0, 30.0)

# TreasureButtonUIView / InnerPanel / Txt Description in its six prefab copies.
# Fixed 258.05 x 116.92 area: allow TMP to fit long descriptions, never grow
# beyond the original 26pt. A 17pt floor fits five Noto Sans lines in this area
# (115.8pt line height total), close to the previous unused 18pt minimum.
TREASURE_DESCRIPTION_OBJECTS = (230842, 236201, 242869, 254277, 259610, 283440)
TREASURE_FONT_SIZE_OFFSET = 292
TREASURE_AUTOSIZING_OFFSET = 304
TREASURE_FONT_BOUNDS_OFFSET = 308
TREASURE_FONT_BOUNDS = (17.0, 26.0)

# Standalone UI textures only; pixels are embedded without changing .resS.
UI_TEXTURES = {
    entry["texture_path_id"]: (entry["name"], *entry["size"], entry["png"])
    for entry in json.loads(
        Path(__file__).with_name("ui_image_localization.json").read_text(encoding="utf-8")
    )["textures"]
}


def patch_ui_textures(env) -> None:
    from PIL import Image

    objects = {obj.path_id: obj for obj in env.objects}
    for path_id, (name, width, height, filename) in UI_TEXTURES.items():
        obj = objects.get(path_id)
        if obj is None or obj.type.name != "Texture2D":
            raise RuntimeError(f"UI texture {path_id} is missing")
        texture = obj.read()
        if (texture.m_Name, texture.m_Width, texture.m_Height) != (name, width, height):
            raise RuntimeError(f"UI texture {path_id} differs from the supported build")
        with Image.open(ROOT / filename) as image:
            if image.size != (width, height):
                raise RuntimeError(f"Localized UI texture {filename} has the wrong size")
            texture.set_image(image.convert("RGBA"), target_format=4, mipmap_count=1)
        texture.save()


def patch_deck_statistics(env) -> None:
    objects = {obj.path_id: obj for obj in env.objects}
    obj = objects.get(DECK_STATISTICS_OBJECT)
    if obj is None:
        raise RuntimeError("Deck statistics TMP object is missing")
    raw = bytearray(obj.get_raw_data())
    if len(raw) != 508 or text_at_offset(raw) != "傷害":
        raise RuntimeError("Deck statistics TMP layout differs from the supported build")
    original, translated = DECK_LINE_SPACING
    current = struct.unpack_from("<f", raw, DECK_LINE_SPACING_OFFSET)[0]
    if current != original:
        raise RuntimeError(f"Unexpected deck line spacing: {current}")
    struct.pack_into("<f", raw, DECK_LINE_SPACING_OFFSET, translated)
    obj.set_raw_data(bytes(raw))


def patch_treasure_descriptions(env) -> None:
    objects = {obj.path_id: obj for obj in env.objects}
    for path_id in TREASURE_DESCRIPTION_OBJECTS:
        obj = objects.get(path_id)
        if obj is None:
            raise RuntimeError(f"Treasure description TMP {path_id} is missing")
        raw = bytearray(obj.get_raw_data())
        if len(raw) != 508 or text_at_offset(raw) != "描述":
            raise RuntimeError(f"Treasure description TMP {path_id} layout differs")
        if struct.unpack_from("<ff", raw, TREASURE_FONT_SIZE_OFFSET) != (26.0, 26.0):
            raise RuntimeError(f"Treasure description TMP {path_id} font size differs")
        if struct.unpack_from("<i", raw, TREASURE_AUTOSIZING_OFFSET)[0] != 0:
            raise RuntimeError(f"Treasure description TMP {path_id} autosizing differs")
        if struct.unpack_from("<ff", raw, TREASURE_FONT_BOUNDS_OFFSET) != (18.0, 72.0):
            raise RuntimeError(f"Treasure description TMP {path_id} font bounds differ")
        struct.pack_into("<i", raw, TREASURE_AUTOSIZING_OFFSET, 1)
        struct.pack_into("<ff", raw, TREASURE_FONT_BOUNDS_OFFSET, *TREASURE_FONT_BOUNDS)
        obj.set_raw_data(bytes(raw))


def serialized_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    padding = b"\0" * ((-len(encoded)) % 4)
    return len(encoded).to_bytes(4, "little") + encoded + padding


def text_at_offset(raw: bytes, offset: int = 88) -> str | None:
    if len(raw) < offset + 4:
        return None
    length = int.from_bytes(raw[offset : offset + 4], "little")
    if length <= 0 or length > 500 or offset + 4 + length > len(raw):
        return None
    try:
        value = raw[offset + 4 : offset + 4 + length].decode("utf-8")
    except UnicodeDecodeError:
        return None
    if any(ord(character) < 32 and character not in "\r\n\t" for character in value):
        return None
    return value


def walk(value, path=()):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, (*path, index))
    else:
        yield path, value


def scan(asset: Path, all_text: bool = False) -> None:
    env = UnityPy.load(str(asset))
    matches = 0
    for obj in env.objects:
        raw = obj.get_raw_data()
        raw_terms = []
        for term in (*VISIBLE_REPLACEMENTS, "Lovense"):
            encoded = term.encode()
            marker = len(encoded).to_bytes(4, "little") + encoded
            offset = raw.find(marker)
            if offset >= 0:
                raw_terms.append(f"{term}@{offset}")
        if raw_terms:
            owner = ""
            if obj.type.name == "MonoBehaviour":
                try:
                    data = obj.read()
                    owner = f" owner={data.m_GameObject.read().m_Name!r}"
                except Exception:
                    pass
            print(f"RAW {obj.type.name} {obj.path_id}{owner}: {', '.join(raw_terms)}")
        if all_text and obj.type.name == "MonoBehaviour":
            possible_text = text_at_offset(raw)
            if possible_text and re.search(r"[A-Za-z]", possible_text):
                print(f"TEXT {obj.path_id}: {possible_text!r}")
        try:
            tree = obj.read_typetree()
        except Exception:
            continue
        for field_path, value in walk(tree):
            if isinstance(value, str) and value in {*VISIBLE_REPLACEMENTS, "Lovense"}:
                print(f"{obj.type.name} {obj.path_id} {'.'.join(map(str, field_path))}: {value!r}")
                matches += 1
    print(f"Found {matches} exact visible labels")


def patch_environment(env) -> tuple[int, int]:
    changed_objects = 0
    changed_fields = 0
    for obj in env.objects:
        raw_replacement = UI_TEXT_OBJECTS.get(obj.path_id)
        if raw_replacement is None:
            continue
        source, translation = raw_replacement
        raw = obj.get_raw_data()
        marker = serialized_string(source)
        if raw.count(marker) != 1:
            raise RuntimeError(
                f"Expected one serialized {source!r} in object {obj.path_id}, "
                f"found {raw.count(marker)}"
            )
        obj.set_raw_data(raw.replace(marker, serialized_string(translation), 1))
        changed_objects += 1
        changed_fields += 1

    if changed_fields != len(UI_TEXT_OBJECTS):
        raise RuntimeError(
            f"Patched {changed_fields} UI labels; expected {len(UI_TEXT_OBJECTS)}"
        )
    patch_deck_statistics(env)
    patch_treasure_descriptions(env)
    patch_ui_textures(env)
    return changed_objects, changed_fields


def verify_environment(env) -> None:
    from PIL import Image

    objects = {obj.path_id: obj for obj in env.objects}
    for path_id, (name, width, height, filename) in UI_TEXTURES.items():
        obj = objects.get(path_id)
        if obj is None or obj.type.name != "Texture2D":
            raise RuntimeError(f"UI texture {path_id} is missing")
        texture = obj.read()
        if (texture.m_Name, texture.m_Width, texture.m_Height) != (name, width, height):
            raise RuntimeError(f"Localized UI texture {path_id} has the wrong layout")
        if texture.m_StreamData and texture.m_StreamData.path:
            raise RuntimeError(f"Localized UI texture {path_id} is not embedded")
        with Image.open(ROOT / filename) as image:
            if texture.image.tobytes() != image.convert("RGBA").tobytes():
                raise RuntimeError(f"Localized UI texture {path_id} pixels differ")
    statistics = objects.get(DECK_STATISTICS_OBJECT)
    if statistics is None:
        raise RuntimeError("Deck statistics TMP object is missing")
    raw = statistics.get_raw_data()
    if len(raw) != 508 or text_at_offset(raw) != "傷害":
        raise RuntimeError("Deck statistics TMP layout differs from the supported build")
    if struct.unpack_from("<f", raw, DECK_LINE_SPACING_OFFSET)[0] != DECK_LINE_SPACING[1]:
        raise RuntimeError("Deck statistics line spacing was not localized")
    for path_id in TREASURE_DESCRIPTION_OBJECTS:
        obj = objects.get(path_id)
        if obj is None:
            raise RuntimeError(f"Treasure description TMP {path_id} is missing")
        raw = obj.get_raw_data()
        if len(raw) != 508 or text_at_offset(raw) != "描述":
            raise RuntimeError(f"Treasure description TMP {path_id} layout differs")
        if struct.unpack_from("<ff", raw, TREASURE_FONT_SIZE_OFFSET) != (26.0, 26.0):
            raise RuntimeError(f"Treasure description TMP {path_id} font size changed")
        if struct.unpack_from("<i", raw, TREASURE_AUTOSIZING_OFFSET)[0] != 1:
            raise RuntimeError(f"Treasure description TMP {path_id} is not autosizing")
        if struct.unpack_from("<ff", raw, TREASURE_FONT_BOUNDS_OFFSET) != TREASURE_FONT_BOUNDS:
            raise RuntimeError(f"Treasure description TMP {path_id} font bounds differ")
    for path_id, (source, translation) in UI_TEXT_OBJECTS.items():
        obj = objects.get(path_id)
        if obj is None:
            raise RuntimeError(f"UI text object {path_id} is missing")
        raw = obj.get_raw_data()
        if serialized_string(source) in raw:
            raise RuntimeError(f"UI label {source!r} remains in object {path_id}")
        if raw.count(serialized_string(translation)) != 1:
            raise RuntimeError(
                f"Expected one localized label {translation!r} in object {path_id}"
            )


def patch(asset: Path, output: Path) -> None:
    env = UnityPy.load(str(asset))
    changed_objects, changed_fields = patch_environment(env)

    serialized_files = [item for item in env.files.values() if hasattr(item, "save")]
    if len(serialized_files) != 1:
        raise RuntimeError(f"Expected one serialized file, found {len(serialized_files)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(serialized_files[0].save())
    print(f"Patched {changed_fields} UI labels across {changed_objects} objects")


def main() -> None:
    parser = argparse.ArgumentParser(description="Patch visible UI labels outside TextAssets")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan_parser = subparsers.add_parser("scan")
    scan_parser.add_argument("asset", type=Path)
    scan_parser.add_argument("--all-text", action="store_true")
    patch_parser = subparsers.add_parser("patch")
    patch_parser.add_argument("asset", type=Path)
    patch_parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.command == "scan":
        scan(args.asset, args.all_text)
    else:
        patch(args.asset, args.output)


if __name__ == "__main__":
    main()
