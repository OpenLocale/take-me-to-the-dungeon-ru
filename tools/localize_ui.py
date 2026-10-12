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
# DrawPair overlays the number using <line-height=0%><br>; extra spacing
# moves it below its label. Keep this field at zero, not the global font.
DECK_STATISTICS_OBJECT = 273009
DECK_LINE_SPACING_OFFSET = 340
DECK_LINE_SPACING = (5.0, 0.0)

# RB-010: literal 1444 is used only by ComputeTemplateStatictis/DrawTitle
# in Steam build 25319640. TMP 3.0.6 combines primary lineHeight (28) with
# current fallback pointSize (90): 400% gives 27.38 units at 22pt, while
# 120% gives only 8.21. Preserve the IL2CPP literal length and all offsets.
DECK_METADATA_SIZE = 14062472
DECK_HEADING_FORMAT = (
    b'</b><line-height=120%><br><line-height=100%>',
    b'</b><line-height=400%><br><line-height=100%>',
)

# RB-012: literal 16605 is referenced only by DungeonButtonUIView.
# Both UTF-8 strings are 18 bytes; {0} is the numeric floor, {1} its name.
DUNGEON_FLOOR_FORMAT = (b'{0}st Floor    {1}', 'Этаж {0}   {1}'.encode('utf-8'))
RUNTIME_METADATA_REPLACEMENTS = (
    (169765, *DECK_HEADING_FORMAT),
    (612488, *DUNGEON_FLOOR_FORMAT),
)

# TreasureButtonUIView / InnerPanel / Txt Description in its six prefab copies.
# Fixed 258.05 x 116.92 area: allow TMP to fit long descriptions, never grow
# beyond the original 26pt. A 17pt floor fits five Noto Sans lines in this area
# (115.8pt line height total), close to the previous unused 18pt minimum.
TREASURE_DESCRIPTION_OBJECTS = (230842, 236201, 242869, 254277, 259610, 283440)
TREASURE_FONT_SIZE_OFFSET = 292
TREASURE_AUTOSIZING_OFFSET = 304
TREASURE_FONT_BOUNDS_OFFSET = 308
TREASURE_FONT_BOUNDS = (17.0, 26.0)

# RB-015: only DungeonTreasureShop/BuyTreasure prefab copies. Keep the
# description's 116.92-high area and text size, reserve a separate footer.
# Description bottom=-180; new owned-field top=-188.1, gap=8.1 units.
SHOP_OWNED_RECTS = (208594, 197033)
SHOP_OWNED_SHIFT = 22.0
SHOP_OWNED_HEIGHT = 26.0  # One 18pt Noto line needs 24.52 units.

# Standalone UI textures only; pixels are embedded without changing .resS.
UI_TEXTURE_ENTRIES = json.loads(
    Path(__file__).with_name("ui_image_localization.json").read_text(encoding="utf-8")
)["textures"]
UI_TEXTURES = {
    entry["texture_path_id"]: (entry["name"], *entry["size"], entry["png"])
    for entry in UI_TEXTURE_ENTRIES
}
UI_TEXTURE_OUTPUT_SIZES = {
    entry["texture_path_id"]: tuple(entry.get("output_size", entry["size"]))
    for entry in UI_TEXTURE_ENTRIES
}

# RB-013: private Spine geometry/UV data for the longer Russian loading word.
LOADING_TEXT_ASSETS = {
    5010: ("Loading", 10080, "audit/ui_loading_ru.json"),
    5030: ("Loading.atlas", 281, "audit/ui_loading_ru.atlas"),
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
            if image.size != UI_TEXTURE_OUTPUT_SIZES[path_id]:
                raise RuntimeError(f"Localized UI texture {filename} has the wrong size")
            texture.set_image(image.convert("RGBA"), target_format=4, mipmap_count=1)
        texture.save()


def patch_loading_animation(env) -> None:
    objects = {obj.path_id: obj for obj in env.objects}
    for path_id, (name, source_size, filename) in LOADING_TEXT_ASSETS.items():
        obj = objects.get(path_id)
        if obj is None or obj.type.name != "TextAsset":
            raise RuntimeError(f"Loading TextAsset {path_id} is missing")
        data = obj.read()
        source = data.m_Script
        if isinstance(source, bytes):
            source = source.decode("utf-8")
        if data.m_Name != name or len(source.encode("utf-8")) != source_size:
            raise RuntimeError(f"Loading TextAsset {path_id} differs from the supported build")
        translated = (ROOT / filename).read_text(encoding="utf-8")
        if path_id == 5010:
            original = json.loads(source)
            result = json.loads(translated)
            if original["skeleton"]["spine"] != "4.0.63" or result["skeleton"]["spine"] != "4.0.63":
                raise RuntimeError("Loading Spine version changed")
            if original["slots"] != result["slots"] or original["animations"] != result["animations"]:
                raise RuntimeError("Loading slots or animation curves changed")
            if [(b["name"], b.get("parent")) for b in original["bones"]] != [
                (b["name"], b.get("parent")) for b in result["bones"]
            ]:
                raise RuntimeError("Loading bone hierarchy changed")
        elif "size:65,133" not in source or "size:128,128" not in translated:
            raise RuntimeError("Unexpected Loading atlas dimensions")
        data.m_Script = translated
        data.save()


def patch_shop_footers(env) -> None:
    objects = {obj.path_id: obj for obj in env.objects}
    for path_id in SHOP_OWNED_RECTS:
        obj = objects.get(path_id)
        if obj is None or obj.type.name != "RectTransform":
            raise RuntimeError(f"Shop owned-field RectTransform {path_id} is missing")
        rect = obj.read()
        if rect.m_GameObject.read().m_Name != "Txt Owned":
            raise RuntimeError(f"Unexpected shop owned-field {path_id}")
        if abs(rect.m_AnchoredPosition.y + 179.1) > 0.01 or abs(rect.m_SizeDelta.y - 42.51451) > 0.01:
            raise RuntimeError(f"Shop owned-field {path_id} layout differs")
        rect.m_AnchoredPosition.y -= SHOP_OWNED_SHIFT
        rect.m_SizeDelta.y = SHOP_OWNED_HEIGHT
        rect.save()


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


def patch_runtime_metadata(source: Path, output: Path) -> None:
    data = source.read_bytes()
    if len(data) != DECK_METADATA_SIZE or data[:8] != struct.pack('<II', 0xFAB11BAF, 31):
        raise RuntimeError('UI metadata differs from Steam build 25319640')
    for offset, original, translated in RUNTIME_METADATA_REPLACEMENTS:
        if len(original) != len(translated) or data.count(original) != 1:
            raise RuntimeError('Expected one size-preserving UI format')
        if data[offset:offset + len(original)] != original:
            raise RuntimeError(f'Unexpected UI metadata format at {offset}')
        data = data.replace(original, translated, 1)
    if source.resolve() == output.resolve():
        raise RuntimeError('Write patched metadata to a separate build file')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(data)
    print(f'Patched {len(RUNTIME_METADATA_REPLACEMENTS)} scoped UI formats in {output}; byte size preserved')


def verify_runtime_metadata(source: Path, output: Path) -> None:
    data = source.read_bytes()
    result = output.read_bytes()
    if len(data) != DECK_METADATA_SIZE or len(result) != len(data):
        raise RuntimeError('Unexpected UI metadata size')
    for offset, original, translated in RUNTIME_METADATA_REPLACEMENTS:
        if data.count(original) != 1 or data[offset:offset + len(original)] != original:
            raise RuntimeError('Unexpected UI metadata source')
        data = data.replace(original, translated, 1)
    if result != data:
        raise RuntimeError('Metadata changes extend beyond the scoped UI formats')
    print('Verified scoped UI formats; all other metadata bytes unchanged')


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
    patch_loading_animation(env)
    patch_shop_footers(env)
    return changed_objects, changed_fields


def verify_environment(env) -> None:
    from PIL import Image

    objects = {obj.path_id: obj for obj in env.objects}
    for path_id, (name, width, height, filename) in UI_TEXTURES.items():
        obj = objects.get(path_id)
        if obj is None or obj.type.name != "Texture2D":
            raise RuntimeError(f"UI texture {path_id} is missing")
        texture = obj.read()
        target_width, target_height = UI_TEXTURE_OUTPUT_SIZES[path_id]
        if (texture.m_Name, texture.m_Width, texture.m_Height) != (name, target_width, target_height):
            raise RuntimeError(f"Localized UI texture {path_id} has the wrong layout")
        if texture.m_StreamData and texture.m_StreamData.path:
            raise RuntimeError(f"Localized UI texture {path_id} is not embedded")
        with Image.open(ROOT / filename) as image:
            if texture.image.tobytes() != image.convert("RGBA").tobytes():
                raise RuntimeError(f"Localized UI texture {path_id} pixels differ")
    for path_id, (name, _, filename) in LOADING_TEXT_ASSETS.items():
        obj = objects.get(path_id)
        if obj is None or obj.type.name != "TextAsset":
            raise RuntimeError(f"Loading TextAsset {path_id} is missing")
        data = obj.read()
        script = data.m_Script
        if isinstance(script, bytes):
            script = script.decode("utf-8")
        if data.m_Name != name or script != (ROOT / filename).read_text(encoding="utf-8"):
            raise RuntimeError(f"Loading TextAsset {path_id} differs from localized source")
    for path_id in SHOP_OWNED_RECTS:
        obj = objects.get(path_id)
        if obj is None or obj.type.name != "RectTransform":
            raise RuntimeError(f"Shop owned-field RectTransform {path_id} is missing")
        rect = obj.read()
        if abs(rect.m_AnchoredPosition.y + 179.1 + SHOP_OWNED_SHIFT) > 0.01 or rect.m_SizeDelta.y != SHOP_OWNED_HEIGHT:
            raise RuntimeError(f"Shop owned-field {path_id} footer was not separated")
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
    for command in ('patch-runtime-metadata', 'verify-runtime-metadata'):
        metadata_parser = subparsers.add_parser(command)
        metadata_parser.add_argument('source', type=Path)
        metadata_parser.add_argument('output', type=Path)
    args = parser.parse_args()

    if args.command == "scan":
        scan(args.asset, args.all_text)
    elif args.command == 'patch-runtime-metadata':
        patch_runtime_metadata(args.source, args.output)
    elif args.command == 'verify-runtime-metadata':
        verify_runtime_metadata(args.source, args.output)
    else:
        patch(args.asset, args.output)


if __name__ == "__main__":
    main()
