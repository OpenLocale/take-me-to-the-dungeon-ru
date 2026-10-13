# Русификатор Take Me To The Dungeon!!

Основной текст игры переведён. Перевод охватывает сюжет, интерфейс, обучение, карты, предметы, дополнительные сцены и галерею.

| Параметр | Значение |
|---|---|
| Версия перевода | v0.9.1 |
| Совместимость | Steam build `25319640` |

## Скачать

[Скачать v0.9.1](https://github.com/OpenLocale/take-me-to-the-dungeon-ru/releases/download/v0.9.1/TakeMeToTheDungeon-RU.zip) · [Страница выпуска](https://github.com/OpenLocale/take-me-to-the-dungeon-ru/releases/tag/v0.9.1)

Архив `TakeMeToTheDungeon-RU.zip` содержит инструкцию `README.txt` и два игровых файла:

- `Take Me To The Dungeon!!_Data/resources.assets`
- `Take Me To The Dungeon!!_Data/il2cpp_data/Metadata/global-metadata.dat`

Устанавливайте оба файла из одного выпуска русификатора. Дополнительные программы не требуются.

## Установка

1. Закройте игру.
2. В Steam: ПКМ по игре → **Свойства → Установленные файлы → Обзор**.
3. Проверьте сборку: в `steamapps/appmanifest_1793250.acf` этой библиотеки Steam значение `buildid` должно быть `25319640`. Изменять файл не требуется.
4. В папке `Take Me To The Dungeon!!_Data` создайте резервные копии `resources.assets` и `il2cpp_data/Metadata/global-metadata.dat`, например с окончанием `.bak`. При обновлении перевода сохраняйте имеющиеся копии оригиналов.
5. Распакуйте содержимое ZIP в корневую папку игры, объедините папки и подтвердите замену **обоих файлов**.
6. В настройках игры выберите **English**: русский перевод заменяет английскую локализацию.

Пути установленных файлов:

```text
Take Me To The Dungeon!!/
└── Take Me To The Dungeon!!_Data/
    ├── resources.assets
    └── il2cpp_data/Metadata/global-metadata.dat
```

`README.txt` размещается в корне игры и не влияет на её работу. Совместимость с другими сборками игры не гарантируется.

## Обновление и удаление

Для обновления закройте игру и замените оба игровых файла файлами совместимого выпуска. Сохраните резервные копии оригиналов.

Для удаления восстановите оригинальные `resources.assets` и `global-metadata.dat` в соответствующих папках. У копий с окончанием `.bak` восстановите исходные имена.

Если резервных копий нет, в Steam выберите **Свойства → Установленные файлы → Проверить целостность файлов игры**.

После обновления игры проверьте совместимость на [странице выпусков](https://github.com/OpenLocale/take-me-to-the-dungeon-ru/releases) перед повторной установкой перевода.

## Изменения v0.9.1

- Добавлен русский логотип главного меню и перевод обозначений уровней.
- Улучшено отображение текста и анимаций интерфейса.

[Полная история изменений](https://github.com/OpenLocale/take-me-to-the-dungeon-ru/blob/main/CHANGELOG.md).

## Сообщить об ошибке

[Форма на GitHub](https://github.com/OpenLocale/take-me-to-the-dungeon-ru/issues/new/choose).

Укажите версию перевода, сборку игры, место ошибки и описание проблемы. Приложите скриншот, если возможно.

## О проекте

Неофициальный перевод OpenLocale, не связанный с разработчиками или издателем игры. Требуется легально приобретённая копия Take Me To The Dungeon!!.

- [Руководство Steam](https://steamcommunity.com/sharedfiles/filedetails/?id=3784428462)
- [История проекта](https://github.com/OpenLocale/take-me-to-the-dungeon-ru/blob/main/HISTORY.md)
- [Правовой статус материалов](https://github.com/OpenLocale/take-me-to-the-dungeon-ru/blob/main/RIGHTS.md)
