from __future__ import annotations

from pathlib import Path

import UnityPy


UI_TEXT_OBJECTS = {
    226875: ("Auto", "Авто"),
    239535: ("Log", "История"),
    270905: ("Hide", "Скрыть"),
}


def serialized_string(value: str) -> bytes:
    encoded = value.encode("utf-8")
    padding = b"\0" * ((-len(encoded)) % 4)
    return len(encoded).to_bytes(4, "little") + encoded + padding


def patch_environment(env) -> tuple[int, int]:
    changed_objects = 0
    changed_fields = 0
    for obj in env.objects:
        replacement = UI_TEXT_OBJECTS.get(obj.path_id)
        if replacement is None:
            continue
        source, translation = replacement
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
    return changed_objects, changed_fields


def verify_environment(env) -> None:
    objects = {obj.path_id: obj for obj in env.objects}
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
