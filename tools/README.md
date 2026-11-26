# Инструменты проекта

Исходники pipeline, которым собраны опубликованные выпуски для Steam build `25319640`. Это инструменты конкретной сборки игры, а не универсальный localization framework: смещения и path ID проверяются для `25319640`.

## Окружение

- Python **3.12** (64-bit), версия закреплена в `.python-version`. Бинарные пакеты в `.tools/python` собраны под cp312; на другой версии Python скрипты сразу сообщают об ошибке окружения.
- Точный набор пакетов — `tools/requirements.txt`. Установка в каталог проекта:

```powershell
py -3.12 -m pip install --target .tools/python -r tools/requirements.txt
```

- Unity и .NET SDK для обычной сборки не нужны (см. «Шрифт»).

## Входные данные

Все входы приватные и в Git не хранятся:

- `translation.json` — рабочий корпус (содержит полный английский текст игры);
- оригинальный `resources.assets` Steam build `25319640` (например, сохранённый `resources.assets.ru-original`);
- оригинальный `global-metadata.dat` той же сборки (`global-metadata.dat.build25319640.ru-original`);
- 85 PNG `tools/ui_*_ru*.png` (список и метод — `tools/ui_image_localization.json`) и `audit/ui_loading_ru.json`, `audit/ui_loading_ru.atlas`, `audit/ui_win_ru_v3.json`;
- донор шрифта — `resources.assets` из опубликованного выпуска для той же сборки игры (сейчас v0.9.2).

Установленный в игре локализованный файл никогда не используется как исход сборки.

## Сборка

```powershell
py -3.12 -B tools/localize.py check --work translation.json
py -3.12 -B tools/localize.py build --game-asset <оригинальный resources.assets> --work translation.json --output build/fontless.resources.assets
py -3.12 -B tools/localize.py font-fallback --built-asset build/fontless.resources.assets --donor-asset <resources.assets выпуска v0.9.2> --output build/resources.assets
py -3.12 -B tools/localize.py verify --game-asset <оригинальный resources.assets> --work translation.json --built-asset build/resources.assets
py -3.12 -B tools/localize_ui.py patch-runtime-metadata <оригинальный global-metadata.dat> build/global-metadata.dat
py -3.12 -B tools/localize_ui.py verify-runtime-metadata <оригинальный global-metadata.dat> build/global-metadata.dat
```

Контроль воспроизводимости — сравнение с последним выпуском:

```powershell
py -3.12 -B tools/localize.py compare build/resources.assets <resources.assets выпуска>
```

`compare` сравнивает таблицу типов и каждый объект по path ID и сырым байтам и сообщает, совпадают ли файлы побайтно. Из корпуса v0.9.2 и оригиналов `25319640` оба игровых файла собираются побайтно идентичными v0.9.2.

## `localize.py`

Работает с таблицами локализации пяти языков в `TextAsset` формата `key=value`:

- `check` — уникальность ключей, пустые переводы, placeholders, теги, повреждённая кодировка;
- `build` — заменяет только английские значения и применяет UI-правки `localize_ui.py`;
- `font-fallback` — подключает статический кириллический fallback (см. «Шрифт»);
- `verify` — читаемость результата, тексты, точные пиксели текстур, адресные поля интерфейса и наличие fallback-шрифта;
- `compare` — пообъектное сравнение двух `resources.assets`.

`font-inputs` формирует список обязательных символов для перевыпечки шрифта.

## `localize_ui.py`

Правки вне `TextAsset`: 85 текстур (кодирование задаёт поле `encoding` манифеста: BC7 для текстур, которые игра хранила сжатыми, иначе RGBA32; `verify` требует точного совпадения пикселей для RGBA32 и не менее 38 дБ PSNR для BC7), шесть UI-подписей, интервалы и автоподбор размеров отдельных полей, анимации «ЗАГРУЗКА...» и «ПОБЕДА», русский логотип, контраст боевых диалогов, статический режим основного шрифта.

Метаданные IL2CPP (`patch-runtime-metadata`) меняются адресно: размеросохраняющие форматы статистики и этажей, подпись слота сохранения «Сохр.» (`attributeData`), а форматы уровней и «Особое» дописываются в конец literal pool со сдвигом последующих смещений заголовка. Исходник — чистые метаданные Steam `25319640`; прочие байты сохраняются, что проверяет `verify-runtime-metadata`.

## Шрифт

Основной TMP font asset игры `CJKtc SDF` не заменяется. Кириллица подключается статическим fallback `CJKtc RU SDF`, выпеченным из `Noto Sans Regular` (OFL, файл и лицензия — в `unity-font-builder`).

**Обычная сборка:** `localize.py font-fallback` копирует готовые FontAsset, Material и атлас из `resources.assets` опубликованного выпуска и добавляет ссылку в таблицу fallback `CJKtc SDF`. Донор проверяется: та же версия Unity, та же таблица типов, совпадающая таблица объектов. Результат идентичен работе `font-importer` с исходным бандлом.

**Перевыпечка шрифта** (только при доказанной проблеме с глифами):

- `unity-font-builder` — Unity `2022.3.62f3`, TextMeshPro `3.0.6`, `SDFAA_HINTED`, атлас `2048×2048`, sampling `90`, padding `9`, режим `Static`:

```powershell
<Unity.exe> -batchmode -nographics -projectPath tools/unity-font-builder -executeMethod BuildCyrillicFont.Build -logFile tools/unity-font-builder/font-build.log
```

- `font-importer` — .NET 8 SDK, AssetsTools.NET; переносит бандл в собранный `resources.assets`:

```powershell
dotnet run --project tools/font-importer -- <cjkru-sdf-bundle> <input-resources.assets> <output-resources.assets>
```

После перевыпечки новый выпуск становится донором для последующих сборок.

## Выпуск

В `TakeMeToTheDungeon-RU.zip` упаковываются `release/README.txt` и два файла: `Take Me To The Dungeon!!_Data/resources.assets` и `Take Me To The Dungeon!!_Data/il2cpp_data/Metadata/global-metadata.dat`. Установка в игру — только по явному запросу и при закрытой игре.
