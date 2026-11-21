from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

import localize_ui  # noqa: E402  (sets up the pinned UnityPy environment)

UnityPy = localize_ui.UnityPy


DEFAULT_WORK = ROOT / "translation.json"

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


def compare_assets(left: Path, right: Path) -> None:
    """Compare two serialized files object by object (type, path ID, raw bytes)."""
    left_file = localize_ui.serialized_file(UnityPy.load(str(left)))
    right_file = localize_ui.serialized_file(UnityPy.load(str(right)))
    problems = []
    if left_file.unity_version != right_file.unity_version:
        problems.append("Unity version differs")
    if localize_ui.type_signature(left_file) != localize_ui.type_signature(right_file):
        problems.append("type table differs")
    left_ids, right_ids = set(left_file.objects), set(right_file.objects)
    for path_id in sorted(left_ids - right_ids)[:20]:
        problems.append(f"only in {left.name}: {path_id}")
    for path_id in sorted(right_ids - left_ids)[:20]:
        problems.append(f"only in {right.name}: {path_id}")
    for path_id in sorted(left_ids & right_ids):
        a, b = left_file.objects[path_id], right_file.objects[path_id]
        if a.type_id != b.type_id or a.get_raw_data() != b.get_raw_data():
            problems.append(f"object {path_id} ({a.type.name}) differs")
    if problems:
        print("\n".join(problems[:100]))
        raise SystemExit(1)
    identical = left.stat().st_size == right.stat().st_size and left.read_bytes() == right.read_bytes()
    print(
        f"Equivalent: {len(left_ids)} objects with identical types and raw data; "
        f"files are {'byte-identical' if identical else 'laid out differently'}"
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

    check_parser = subparsers.add_parser("check")
    check_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)

    font_inputs_parser = subparsers.add_parser("font-inputs")
    font_inputs_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    font_inputs_parser.add_argument("--characters-output", type=Path, required=True)

    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--game-asset", type=Path, required=True)
    build_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    build_parser.add_argument("--output", type=Path, required=True)

    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("--game-asset", type=Path, required=True)
    verify_parser.add_argument("--work", type=Path, default=DEFAULT_WORK)
    verify_parser.add_argument("--built-asset", type=Path, required=True)

    font_parser = subparsers.add_parser("font-fallback")
    font_parser.add_argument("--built-asset", type=Path, required=True)
    font_parser.add_argument("--donor-asset", type=Path, required=True)
    font_parser.add_argument("--output", type=Path, required=True)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("left", type=Path)
    compare_parser.add_argument("right", type=Path)

    hash_parser = subparsers.add_parser("sha256")
    hash_parser.add_argument("path", type=Path)

    args = parser.parse_args()
    if args.command == "check":
        _, errors = check_work(args.work)
        if errors:
            print("\n".join(errors))
            raise SystemExit(1)
        print("Integrity check passed")
    elif args.command == "font-inputs":
        export_font_inputs(args.work, args.characters_output)
    elif args.command == "build":
        build(args.game_asset, args.work, args.output)
    elif args.command == "verify":
        verify_built(args.game_asset, args.work, args.built_asset)
    elif args.command == "font-fallback":
        localize_ui.import_font_fallback(args.built_asset, args.donor_asset, args.output)
    elif args.command == "compare":
        compare_assets(args.left, args.right)
    elif args.command == "sha256":
        print(f"{sha256(args.path)}  {args.path.name}")


if __name__ == "__main__":
    main()
