# Русификатор Take Me To The Dungeon!!

Готовый русский перевод Steam-версии игры. Переведены сюжет, интерфейс, обучение, описания карт и предметов, дополнительные сцены и галерея.

| | |
|---|---|
| **Версия перевода** | v1.7 |
| **Версия игры** | 1.7.6 (Steam) |

> С другими версиями игры русификатор может не работать.

## Ссылки для скачивания

**[Скачать TakeMeToTheDungeon-RU.zip](https://github.com/OpenLocale/take-me-to-the-dungeon-ru/releases/latest/download/TakeMeToTheDungeon-RU.zip)**

[Страница последнего релиза и контрольная сумма](https://github.com/OpenLocale/take-me-to-the-dungeon-ru/releases/latest)

## Установка

1. Закройте игру.
2. В библиотеке Steam нажмите правой кнопкой на **Take Me To The Dungeon!!** и выберите **Свойства → Установленные файлы → Обзор**.
3. Зайдите в папку `Take Me To The Dungeon!!_Data`.
4. Сделайте копию файла `resources.assets` и назовите её, например, `resources.assets.original`.
5. Распакуйте ZIP в корневую папку игры и согласитесь на замену файла.
6. Запустите игру и выберите **English** в настройках языка.

После установки получится такая структура:

```text
Take Me To The Dungeon!!/
└── Take Me To The Dungeon!!_Data/
    └── resources.assets
```

## Как удалить перевод

Закройте игру, удалите изменённый `resources.assets` и верните резервной копии прежнее имя.

Если копии не осталось, откройте свойства игры в Steam и выполните **Проверить целостность файлов игры**. Steam скачает оригинальный файл заново.

## Что важно знать

- Русский текст заменяет английскую локализацию, поэтому в игре должен быть выбран язык **English**.
- Меняется только `Take Me To The Dungeon!!_Data/resources.assets`.
- BepInEx, MelonLoader и другие загрузчики не нужны.
- Кириллица добавлена к оригинальному интерфейсному шрифту, поэтому оформление игры сохраняется.

## Нашли ошибку?

- [Сообщить об ошибке перевода](https://github.com/OpenLocale/take-me-to-the-dungeon-ru/issues/new?template=translation-error.yml)
- [Сообщить о проблеме с установкой или отображением текста](https://github.com/OpenLocale/take-me-to-the-dungeon-ru/issues/new?template=technical-problem.yml)

Укажите версии игры и русификатора, место ошибки и приложите скриншот, если это возможно.

## О проекте

- [Готовый текст руководства для Steam](STEAM_GUIDE.txt)
- [История проекта](HISTORY.md)
- [Список изменений](CHANGELOG.md)
- [Как собирается русификатор](tools/README.md)
- [Правовой статус материалов](RIGHTS.md)

Это неофициальный проект OpenLocale. Он не связан с разработчиками или издателем игры. Для установки нужна легально приобретённая копия Take Me To The Dungeon!!.
