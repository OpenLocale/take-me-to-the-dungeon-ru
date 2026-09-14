# Инструменты проекта

Здесь находятся очищенные исходники инструментов, реально использованных для подготовки v0.8.0. Они публикуются для прозрачности процесса, но не превращают репозиторий в универсальный localization framework.

## `localize.py`

Работает с таблицами локализации для пяти языков. Они хранятся в `TextAsset` внутри `resources.assets` и используют формат `key=value`:

- извлекает английские записи;
- проверяет уникальность ключей, пустые переводы, placeholders, теги и повреждённую кодировку;
- заменяет только английские значения;
- проверяет читаемость результата через UnityPy.

Рабочий `translation.json` не опубликован, поскольку содержит полный исходный английский текст игры вместе с русским переводом. Локальные пути передаются параметрами командной строки либо размещаются в игнорируемом каталоге `.local`.

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

Path ID внутри importer относятся только к Steam-сборке игры 1.7.6. Перед использованием с другой версией их необходимо заново проверить.

## Минимальная последовательность

1. Проверить `translation.json` командой `localize.py check`.
2. Собрать TextAsset-патч командой `localize.py build` из оригинального `resources.assets`.
3. Выпечь статический TMP fallback в Unity.
4. Внедрить fallback через `font-importer`.
5. Выполнить `localize.py verify`.
6. Упаковать только пользовательские файлы.
