# Инструменты проекта

Здесь находятся исходники рабочего pipeline: публичная база v0.8.1 и изменения локальной ветки v0.9.0-dev. Итоговая сборка с RB-009 проверена и установлена 2026-10-13; публичный выпуск не выполнялся. Инструменты сохраняются для прозрачности процесса, не как универсальный localization framework.

## `localize.py`

Работает с таблицами локализации для пяти языков. Они хранятся в `TextAsset` внутри `resources.assets` и используют формат `key=value`:

- извлекает английские записи;
- проверяет уникальность ключей, пустые переводы, placeholders, теги и повреждённую кодировку;
- заменяет только английские значения;
- проверяет читаемость результата через UnityPy.

Рабочий `translation.json` не опубликован, поскольку содержит полный исходный английский текст игры вместе с русским переводом. Активный приватный корпус находится в корне этой рабочей ветки, результат — в `release/Take Me To The Dungeon!!_Data`. Пути передаются параметрами командной строки. Для сборки обязательно указывать сохранённый `resources.assets.ru-original`, не установленный локализованный файл. Зависимости берутся из локального `.tools/python` или установленного Python-окружения.

В `localize_ui.py` добавлены 55 проверенных текстур по `ui_image_localization.json`, адресный интервал статистики колоды и автоподбор 17–26 для шести полей описаний сокровищ. `verify` проверяет текст, пиксели встроенных изображений и эти параметры. Манифесты `ui_image_localization.json` и `ui_tutorial_localization.json` фиксируют методы, промпты, сохранённые области и текущий статус установки. PNG игровых ассетов остаются локальными и не коммитятся.

## `unity-font-builder`

Минимальный Unity-проект для выпечки `CJKtc RU SDF`:

- Unity `2022.3.62f3`;
- TextMeshPro `3.0.6`;
- `SDFAA_HINTED`;
- atlas `2048×2048`;
- sampling size `90`;
- padding `9`;
- итоговый режим `Static`.

В качестве кириллического fallback используется `Noto Sans Regular`, распространяемый по OFL и включённый в проект вместе с текстом лицензии. Импортированные TMP Essentials и готовый AssetBundle не публикуются. Исходный игровой `CJKtc SDF` не заменяется: новый шрифт добавляется к нему как fallback.

Пример batchmode-выпечки:

```powershell
<Unity.exe> -batchmode -nographics -projectPath tools/unity-font-builder -executeMethod BuildCyrillicFont.Build -logFile tools/unity-font-builder/font-build.log
```

## `font-importer`

.NET 8-инструмент на AssetsTools.NET переносит выпеченные TMP FontAsset, Material и Texture2D в готовый `resources.assets` и добавляет русский fallback в `CJKtc SDF`.

```powershell
dotnet run --project tools/font-importer -- <cjkru-sdf-bundle> <input-resources.assets> <output-resources.assets>
```

Path ID внутри importer проверены для Steam-сборки игры 1.7.6, build `25319640`. Перед использованием с другой версией их необходимо заново проверить.

## Минимальная последовательность

1. Проверить `translation.json` командой `localize.py check`.
2. Собрать TextAsset/UI-патч командой `localize.py build --game-asset <resources.assets.ru-original>`.
3. Использовать уже готовый статический TMP fallback `tools/unity-font-builder/FontBundle/cjkru-sdf`; без доказанной проблемы заново не выпекать.
4. Внедрить fallback через `font-importer`.
5. Выполнить `localize.py verify`.
6. По явному запросу установить проверенный `resources.assets` при закрытой игре; метаданные копировать только когда они требуют изменения. При публичном выпуске упаковать только пользовательские файлы. Хэши не вычислять, игру автоматически не запускать.
