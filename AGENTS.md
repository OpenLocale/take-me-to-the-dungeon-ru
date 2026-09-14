# AGENTS.md

## Назначение

Репозиторий содержит неофициальный русский перевод Take Me To The Dungeon!! и инструменты, реально использованные для сборки assets-патча.

## Основные правила

- Не коммитить готовые Release ZIP и скомпилированный `resources.assets`.
- Не добавлять `.exe`, `.ps1`, `.bat` или автоматический установщик без отдельного решения проекта.
- Основной пользовательский способ установки — ручное копирование файлов из Release ZIP.
- Каждый Release обязан указывать версии перевода и поддерживаемой игры.
- Не публиковать извлечённые из игры шрифты, исходные assets, полный оригинальный сценарий и другие ненужные данные игры. Открытый `Noto Sans` и его лицензия являются частью воспроизводимого font-builder.
- Не изменять бинарные игровые файлы без понимания `tools/localize.py`, TMP font-builder и `tools/font-importer`.
- Сохранять ключи, порядок записей, placeholders, rich-text tags и терминологию перевода.
- Перед изменением структуры сначала изучить существующий pipeline.
- При выпуске новой версии обновлять README, Release notes и `STEAM_GUIDE.txt` одновременно.

## Структура

- `README.md` — пользовательская установка и совместимость.
- `STEAM_GUIDE.txt` — готовый BBCode-текст руководства для Steam.
- `.github/ISSUE_TEMPLATE/` — формы ошибок перевода и технических проблем.
- `tools/localize.py` — extraction, integrity check, TextAsset write-back и verify.
- `tools/font-importer/` — перенос статического TMP fallback в `resources.assets`.
- `tools/unity-font-builder/` — минимальные исходники Unity/TMP-выпечки с открытым `Noto Sans Regular`; извлечённый из игры `CJKtc.ttf` не публикуется.

Рабочий `translation.json`, исходные assets и результаты сборки хранятся вне Git. Публичный репозиторий намеренно не является полным дампом сценария игры.

## Проверка и сборка

Python-зависимость:

```powershell
python -m pip install -r tools/requirements.txt
```

Проверка корпуса:

```powershell
python tools/localize.py check --work <translation.json>
```

Сборка текстового assets из оригинального файла:

```powershell
python tools/localize.py build --game-asset <resources.assets.ru-original> --work <translation.json> --output <build/resources.assets>
```

Проверка собранного файла:

```powershell
python tools/localize.py verify --game-asset <resources.assets.ru-original> --work <translation.json> --built-asset <build/resources.assets>
```

Статический TMP fallback выпекается из включённого `NotoSans-Regular.ttf` в Unity `2022.3.62f3` с TextMeshPro `3.0.6`, после чего импортируется `tools/font-importer`. Готовый AssetBundle собирается локально и не входит в Git.

Release формируется вручную: `README.txt` и итоговый `Take Me To The Dungeon!!_Data/resources.assets` упаковываются в `TakeMeToTheDungeon-RU.zip`. Хэши в текущем рабочем процессе не вычисляются.

## Правила этой игры

- Русский текст физически заменяет English locale; в игре пользователь выбирает English.
- Поддерживаемая версия текущего релиза — Steam 1.7.6; версия русификатора — `v0.8.0` до следующего подтверждённого обновления.
- Основной TMP font asset остаётся `CJKtc SDF`; кириллица подключается статическим fallback.
- Font importer содержит path ID, специфичные для этой сборки игры. Не применять его к другой версии без повторной проверки структуры assets.
- Финальный патч всегда собирать из сохранённого оригинального `resources.assets`, а не из ранее модифицированной версии.
