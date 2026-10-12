from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import shutil
import struct
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNITYPY_DIR = ROOT / ".tools" / "python"
sys.path.insert(0, str(UNITYPY_DIR))

import UnityPy  # noqa: E402
import localize_ui  # noqa: E402


DEFAULT_GAME_ASSET = Path(
    r"E:\SteamLibrary\steamapps\common\Take Me To The Dungeon!!"
    r"\Take Me To The Dungeon!!_Data\resources.assets"
)
DEFAULT_OLD_ASSET = (
    ROOT
    / ".source"
    / "old_mod"
    / "Take Me To The Dungeon!!_Data"
    / "resources.assets"
)
DEFAULT_WORK = ROOT / "translation.json"
DEFAULT_OUTPUT = ROOT / "release" / "Take Me To The Dungeon!!_Data" / "resources.assets"

CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
FOREIGN_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
LATIN_RE = re.compile(r"[A-Za-z]")
PLACEHOLDER_RE = re.compile(
    r"\{[^{}]+\}|%(?:\d+\$)?[sdif]|</?[A-Za-z][A-Za-z0-9]*(?:=[^<> ]+)?\s*/?>|\\[nrt]"
)


def script_text(data) -> str:
    value = data.m_Script
    return value if isinstance(value, str) else value.decode("utf-8", "replace")


def split_line(line: str) -> tuple[str, str] | None:
    if "=" not in line:
        return None
    return tuple(line.split("=", 1))  # type: ignore[return-value]


def load_text_assets(path: Path):
    env = UnityPy.load(str(path))
    assets = []
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        data = obj.read()
        assets.append((obj, data, script_text(data)))
    return env, assets


def english_assets(assets):
    groups = collections.defaultdict(list)
    for obj, data, script in assets:
        groups[data.m_Name].append((obj, data, script))

    selected = []
    for group in groups.values():
        if len(group) < 5:
            continue
        for obj, data, script in group:
            values = "\n".join(
                pair[1]
                for line in script.splitlines()
                if (pair := split_line(line)) is not None
            )
            line_count = sum(split_line(line) is not None for line in script.splitlines())
            latin = len(LATIN_RE.findall(values))
            foreign = len(FOREIGN_RE.findall(values))
            if line_count and latin >= max(2, foreign * 3):
                selected.append((obj, data, script))
    return selected


def old_russian_map(path: Path) -> dict[tuple[str, str], str]:
    _, assets = load_text_assets(path)
    result = {}
    for _, data, script in assets:
        values = "\n".join(
            pair[1]
            for line in script.splitlines()
            if (pair := split_line(line)) is not None
        )
        if not CYRILLIC_RE.search(values):
            continue
        for line in script.splitlines():
            pair = split_line(line)
            if pair is not None:
                result[(data.m_Name, pair[0])] = pair[1]
    return result


def export_work(game_asset: Path, old_asset: Path, work: Path) -> None:
    _, assets = load_text_assets(game_asset)
    selected = english_assets(assets)
    old = old_russian_map(old_asset)

    entries = []
    seen = set()
    for _, data, script in selected:
        for line in script.splitlines():
            pair = split_line(line)
            if pair is None:
                continue
            key, source = pair
            identity = (data.m_Name, key, source)
            if identity in seen:
                continue
            seen.add(identity)
            reused = old.get((data.m_Name, key), "")
            entries.append(
                {
                    "asset": data.m_Name,
                    "key": key,
                    "source": source,
                    "translation": reused,
                    "origin": "old_v1.2" if reused else "new",
                }
            )

    payload = {
        "format": 1,
        "source_asset": str(game_asset),
        "entries": entries,
    }
    work.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    reused = sum(bool(entry["translation"]) for entry in entries)
    print(f"Exported {len(entries)} unique strings: {reused} reused, {len(entries) - reused} untranslated")


def token_signature(value: str) -> list[str]:
    return PLACEHOLDER_RE.findall(value)


def export_font_inputs(work: Path, characters_output: Path) -> None:
    payload, errors = check_work(work)
    if errors:
        raise RuntimeError("Working file failed integrity check")

    characters = {
        character
        for entry in payload["entries"]
        for character in entry["translation"]
        if "\u0400" <= character <= "\u052f"
    }
    characters.update("Ёё№«»„“”‘’–—…\u00a0")

    characters_output.parent.mkdir(parents=True, exist_ok=True)
    characters_output.write_text("".join(sorted(characters)), encoding="utf-8")
    print(f"Exported {len(characters)} required Russian fallback characters")


def check_work(work: Path) -> tuple[dict, list[str]]:
    payload = json.loads(work.read_text(encoding="utf-8"))
    errors = []
    identities = set()
    for index, entry in enumerate(payload["entries"]):
        identity = (entry["asset"], entry["key"], entry["source"])
        if identity in identities:
            errors.append(f"duplicate entry at {index}: {identity}")
        identities.add(identity)
        source = entry["source"]
        translation = entry["translation"]
        if source.strip() and not translation.strip():
            errors.append(f"empty translation: {entry['asset']}::{entry['key']}")
        if "�" in translation:
            errors.append(f"replacement character: {entry['asset']}::{entry['key']}")
        if collections.Counter(token_signature(source)) != collections.Counter(
            token_signature(translation)
        ):
            errors.append(f"placeholder/tag mismatch: {entry['asset']}::{entry['key']}")
    return payload, errors


def google_translate(text: str) -> str:
    query = urllib.parse.urlencode(
        {"client": "gtx", "sl": "en", "tl": "ru", "dt": "t", "q": text}
    )
    request = urllib.request.Request(
        "https://translate.googleapis.com/translate_a/single?" + query,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read())
    return "".join(part[0] for part in result[0] if part[0])


def translate_nonplot(work: Path) -> None:
    payload = json.loads(work.read_text(encoding="utf-8"))
    pending = [
        entry
        for entry in payload["entries"]
        if not entry["translation"] and not entry["asset"].startswith("Plot")
    ]
    batches = []
    batch = []
    batch_size = 0
    for entry in pending:
        if batch and batch_size + len(entry["source"]) > 3200:
            batches.append(batch)
            batch = []
            batch_size = 0
        batch.append(entry)
        batch_size += len(entry["source"]) + 24
    if batch:
        batches.append(batch)

    for batch_index, entries in enumerate(batches, 1):
        protected = []
        placeholder_sets = []
        for entry_index, entry in enumerate(entries):
            placeholders = token_signature(entry["source"])
            value = entry["source"]
            for placeholder_index, placeholder in enumerate(placeholders):
                value = value.replace(
                    placeholder,
                    f"ZXQPH{entry_index:03d}X{placeholder_index:02d}ZXQ",
                    1,
                )
            protected.append(value)
            placeholder_sets.append(placeholders)

        separators = [f"ZXQSEP{index:04d}ZXQ" for index in range(len(entries) - 1)]
        combined_parts = []
        for index, value in enumerate(protected):
            combined_parts.append(value)
            if index < len(separators):
                combined_parts.append("\n" + separators[index] + "\n")
        translated = google_translate("".join(combined_parts))
        pattern = r"\s*ZXQSEP\d{4}ZXQ\s*"
        values = re.split(pattern, translated)
        if len(values) != len(entries):
            raise RuntimeError(
                f"Translation batch {batch_index} split into {len(values)} values; expected {len(entries)}"
            )
        for entry_index, (entry, value, placeholders) in enumerate(
            zip(entries, values, placeholder_sets)
        ):
            for placeholder_index, placeholder in enumerate(placeholders):
                token = f"ZXQPH{entry_index:03d}X{placeholder_index:02d}ZXQ"
                value = value.replace(token, placeholder)
            entry["translation"] = value.strip()
            entry["origin"] = "translated_ui"
        work.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"Translated UI batch {batch_index}/{len(batches)} ({len(entries)} strings)")
        time.sleep(0.15)


def translate_plots(work: Path) -> None:
    payload = json.loads(work.read_text(encoding="utf-8"))
    by_asset = collections.OrderedDict()
    for entry in payload["entries"]:
        if not entry["translation"] and entry["asset"].startswith("Plot"):
            by_asset.setdefault(entry["asset"], []).append(entry)

    batches = []
    for asset, asset_entries in by_asset.items():
        batch = []
        batch_size = 0
        for entry in asset_entries:
            if batch and batch_size + len(entry["source"]) > 3200:
                batches.append((asset, batch))
                batch = []
                batch_size = 0
            batch.append(entry)
            batch_size += len(entry["source"]) + 24
        if batch:
            batches.append((asset, batch))

    for batch_index, (asset, entries) in enumerate(batches, 1):
        protected = []
        placeholder_sets = []
        for entry_index, entry in enumerate(entries):
            placeholders = token_signature(entry["source"])
            value = entry["source"]
            for placeholder_index, placeholder in enumerate(placeholders):
                value = value.replace(
                    placeholder,
                    f"ZXQPH{entry_index:03d}X{placeholder_index:02d}ZXQ",
                    1,
                )
            protected.append(value)
            placeholder_sets.append(placeholders)

        separators = [f"ZXQSEP{index:04d}ZXQ" for index in range(len(entries) - 1)]
        combined_parts = []
        for index, value in enumerate(protected):
            combined_parts.append(value)
            if index < len(separators):
                combined_parts.append("\n" + separators[index] + "\n")
        translated = google_translate("".join(combined_parts))
        values = re.split(r"\s*ZXQSEP\d{4}ZXQ\s*", translated)
        if len(values) != len(entries):
            raise RuntimeError(
                f"Scene batch {asset}/{batch_index} split into {len(values)} values; expected {len(entries)}"
            )
        for entry_index, (entry, value, placeholders) in enumerate(
            zip(entries, values, placeholder_sets)
        ):
            for placeholder_index, placeholder in enumerate(placeholders):
                token = f"ZXQPH{entry_index:03d}X{placeholder_index:02d}ZXQ"
                value = value.replace(token, placeholder)
            entry["translation"] = value.strip()
            entry["origin"] = "translated_scene"
        work.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(
            f"Translated scene batch {batch_index}/{len(batches)}: {asset} ({len(entries)} strings)"
        )
        time.sleep(0.15)


def build(game_asset: Path, work: Path, output: Path) -> None:
    payload, errors = check_work(work)
    if errors:
        print("Integrity check failed:")
        print("\n".join(errors[:100]))
        if len(errors) > 100:
            print(f"... and {len(errors) - 100} more")
        raise SystemExit(1)

    translations = {
        (entry["asset"], entry["key"], entry["source"]): entry["translation"]
        for entry in payload["entries"]
    }
    env, assets = load_text_assets(game_asset)
    changed = 0
    changed_lines = 0
    for _, data, script in english_assets(assets):
        output_lines = []
        local_changes = 0
        for line in script.splitlines(keepends=True):
            ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
            body = line[: -len(ending)] if ending else line
            pair = split_line(body)
            if pair is None:
                output_lines.append(line)
                continue
            key, source = pair
            translated = translations.get((data.m_Name, key, source))
            if translated is None:
                raise RuntimeError(f"Missing working entry for {data.m_Name}::{key}")
            output_lines.append(f"{key}={translated}{ending}")
            local_changes += 1
        if local_changes:
            data.m_Script = "".join(output_lines)
            data.save()
            changed += 1
            changed_lines += local_changes

    ui_objects, ui_labels = localize_ui.patch_environment(env)

    output.parent.mkdir(parents=True, exist_ok=True)
    serialized_files = [item for item in env.files.values() if hasattr(item, "save")]
    if len(serialized_files) != 1:
        raise RuntimeError(f"Expected one serialized file, found {len(serialized_files)}")
    output.write_bytes(serialized_files[0].save())
    print(
        f"Built {output} with {changed_lines} translated lines across {changed} TextAssets; "
        f"localized {ui_labels} UI labels across {ui_objects} objects; "
        f"{len(localize_ui.UI_TEXTURES)} UI textures; deck statistics line spacing; "
        f"{len(localize_ui.TREASURE_DESCRIPTION_OBJECTS)} treasure descriptions autosizing"
    )


def verify_built(game_asset: Path, work: Path, built_asset: Path) -> None:
    payload, errors = check_work(work)
    if errors:
        raise RuntimeError("Working file failed integrity check")
    _, original_assets = load_text_assets(game_asset)
    built_env, built_assets = load_text_assets(built_asset)
    localize_ui.verify_environment(built_env)
    original_selected = english_assets(original_assets)
    built_cyrillic = 0
    for _, data, script in built_assets:
        if CYRILLIC_RE.search(script):
            built_cyrillic += 1
    if built_cyrillic < len(original_selected):
        raise RuntimeError(
            f"Built asset contains only {built_cyrillic} Cyrillic TextAssets; expected at least {len(original_selected)}"
        )
    expected = len(payload["entries"])
    print(
        f"Verified readable build: {built_cyrillic} Cyrillic TextAssets; "
        f"{expected} unique working strings; {len(localize_ui.UI_TEXT_OBJECTS)} localized UI labels; "
        f"{len(localize_ui.UI_TEXTURES)} localized UI textures; deck statistics line spacing; "
        f"{len(localize_ui.TREASURE_DESCRIPTION_OBJECTS)} treasure descriptions autosizing"
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--game-asset", type=Path, default=DEFAULT_GAME_ASSET)
    export_parser.add_argument("--old-asset", type=Path, default=DEFAULT_OLD_ASSET)
    export_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)

    translate_ui_parser = subparsers.add_parser("translate-ui")
    translate_ui_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)

    translate_plot_parser = subparsers.add_parser("translate-plots")
    translate_plot_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)

    font_inputs_parser = subparsers.add_parser("font-inputs")
    font_inputs_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    font_inputs_parser.add_argument("--characters-output", type=Path, required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--game-asset", type=Path, default=DEFAULT_GAME_ASSET)
    build_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    build_parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--game-asset", type=Path, default=DEFAULT_GAME_ASSET)
    verify_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    verify_parser.add_argument("--built-asset", type=Path, default=DEFAULT_OUTPUT)

    hash_parser = subparsers.add_parser("sha256")
    hash_parser.add_argument("path", type=Path)

    args = parser.parse_args()
    if args.command == "export":
        export_work(args.game_asset, args.old_asset, args.work)
    elif args.command == "check":
        _, errors = check_work(args.work)
        if errors:
            print("\n".join(errors))
            raise SystemExit(1)
        print("Integrity check passed")
    elif args.command == "translate-ui":
        translate_nonplot(args.work)
    elif args.command == "translate-plots":
        translate_plots(args.work)
    elif args.command == "font-inputs":
        export_font_inputs(args.work, args.characters_output)
    elif args.command == "build":
        build(args.game_asset, args.work, args.output)
    elif args.command == "verify":
        verify_built(args.game_asset, args.work, args.built_asset)
    elif args.command == "sha256":
        print(f"{sha256(args.path)}  {args.path.name}")


if __name__ == "__main__":
    main()
