"""Translations of every eos_sig_checker message: (de, ru, zh_Hans).

The German, Russian and Simplified Chinese translations are machine-generated and may be inaccurate.
Checked for sense, not by a native speaker - a correction goes here.

The source of truth for the catalogues - tools/translate.py writes these into
the .po files and refuses to run while a message is missing here. Add a new
message here, never in a .po file: the next run would overwrite a hand edit.

EVE jargon stays English in every language: Corporation, Alliance, Main,
Character, and what the probe scanner shows (Cosmic Signature, Cosmic
Anomaly, Combat/Data/Relic/Gas/Ore Site, Wormhole) - the pasted text is the
English client's anyway.

A short word Alliance Auth translates differently ("Name", "Type", "Group")
needs the "eos-sig-checker" context in the code; the translation test in
tests/test_translations.py names every such clash.

Plural forms: de 2, ru 3, zh_Hans 1.
"""

LANGUAGES = ("de", "ru", "zh_Hans")

PLURAL_FORMS = {
    "de": "nplurals=2; plural=(n != 1);",
    "ru": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);",
    "zh_Hans": "nplurals=1; plural=0;",
}

TRANSLATIONS = {
    "Sig Checker": ("Sig Checker", "Sig Checker", "Sig Checker"),
    "Can paste and resolve signatures": (
        "Kann Signaturen einfügen und auflösen",
        "Может вставлять и распознавать сигнатуры",
        "可以粘贴并解析信号",
    ),
    "Signature": ("Signatur", "Сигнатура", "信号"),
    "Signatures": ("Signaturen", "Сигнатуры", "信号"),
    # parser
    "Expected 6 tab-separated columns, as the probe scanner copies them.": (
        "Erwartet werden 6 durch Tabs getrennte Spalten, wie der Probe Scanner sie kopiert.",
        "Ожидается 6 столбцов, разделённых табуляцией, как их копирует Probe Scanner.",
        "应为 6 个以制表符分隔的列，与 Probe Scanner 复制的格式相同。",
    ),
    "The signature ID must look like ABC-123.": (
        "Die Signatur-ID muss wie ABC-123 aussehen.",
        "ID сигнатуры должен выглядеть как ABC-123.",
        "信号 ID 必须形如 ABC-123。",
    ),
    "The site type holds characters a site type never has.": (
        "Der Site-Typ enthält Zeichen, die ein Site-Typ nie hat.",
        "Тип сайта содержит символы, которых в типе сайта не бывает.",
        "站点类型包含站点类型中不会出现的字符。",
    ),
    "The name holds characters a site name never has.": (
        "Der Name enthält Zeichen, die ein Site-Name nie hat.",
        "Название содержит символы, которых в названии сайта не бывает.",
        "名称包含站点名称中不会出现的字符。",
    ),
    "A name without a site type does not come from the probe scanner.": (
        "Ein Name ohne Site-Typ kommt nicht aus dem Probe Scanner.",
        "Название без типа сайта не может прийти из Probe Scanner.",
        "没有站点类型的名称不可能来自 Probe Scanner。",
    ),
    "The scan strength must be a percentage between 0 and 100.": (
        "Die Scanstärke muss ein Prozentwert zwischen 0 und 100 sein.",
        "Сила сканирования должна быть процентом от 0 до 100.",
        "扫描强度必须是 0 到 100 之间的百分比。",
    ),
    "The distance must be a number with AU, km or m.": (
        "Die Entfernung muss eine Zahl mit AU, km oder m sein.",
        "Расстояние должно быть числом с AU, km или m.",
        "距离必须是带有 AU、km 或 m 的数字。",
    ),
    "The line holds control characters.": (
        "Die Zeile enthält Steuerzeichen.",
        "Строка содержит управляющие символы.",
        "该行包含控制字符。",
    ),
    # form
    "Probe scanner": ("Probe Scanner", "Probe Scanner", "Probe Scanner"),
    "Select the results in the probe scanner, copy them with Ctrl+C and paste them here.": (
        "Ergebnisse im Probe Scanner markieren, mit Strg+C kopieren und hier einfügen.",
        "Выдели результаты в Probe Scanner, скопируй их через Ctrl+C и вставь сюда.",
        "在 Probe Scanner 中选中结果，用 Ctrl+C 复制并粘贴到这里。",
    ),
    # page
    "Check": ("Prüfen", "Проверить", "检查"),
    "Pasting checks on its own": (
        "Einfügen prüft von selbst",
        "Вставка проверяется автоматически",
        "粘贴后会自动检查",
    ),
    "Too many checks: wait a second and press Check again.": (
        "Zu viele Prüfungen: eine Sekunde warten und erneut Prüfen drücken.",
        "Слишком много проверок: подожди секунду и снова нажми «Проверить».",
        "检查过于频繁：请等待一秒后再次点击检查。",
    ),
    "Result": ("Ergebnis", "Результат", "结果"),
    "Copied": ("Kopiert", "Скопировано", "已复制"),
    "Copy": ("Kopieren", "Копировать", "复制"),
    "Copy the completed list in the probe scanner format": (
        "Die vervollständigte Liste im Format des Probe Scanners kopieren",
        "Скопировать дополненный список в формате Probe Scanner",
        "以 Probe Scanner 格式复制补全后的列表",
    ),
    # the probe scanner's column words: Kind = Cosmic Signature/Anomaly,
    # Group = Combat Site, Wormhole ...
    "ID": ("ID", "ID", "ID"),
    "Kind": ("Art", "Вид", "种类"),
    "Group": ("Gruppe", "Группа", "分组"),
    "Name": ("Name", "Название", "名称"),
    "Signal": ("Signal", "Сигнал", "信号强度"),
    "Distance": ("Entfernung", "Расстояние", "距离"),
    "Last checked": ("Zuletzt geprüft", "Последняя проверка", "上次检查"),
    "new": ("neu", "новая", "新"),
    "Paste the probe scanner on the left and press Check: every line comes back here, with group and name filled in where somebody has scanned it already.": (
        "Probe Scanner links einfügen und Prüfen drücken: Jede Zeile erscheint hier wieder, mit Gruppe und Name, wo jemand sie schon gescannt hat.",
        "Вставь Probe Scanner слева и нажми «Проверить»: каждая строка появится здесь, с группой и названием там, где кто-то уже её просканировал.",
        "将 Probe Scanner 内容粘贴到左侧并点击检查：每一行都会显示在这里，已有人扫描过的会补全分组和名称。",
    ),
    "filled in from the shared list": (
        "aus der gemeinsamen Liste ergänzt",
        "дополнено из общего списка",
        "从共享列表补全",
    ),
    # settings page
    "Can change the settings and delete all signatures": (
        "Kann die Einstellungen ändern und alle Signaturen löschen",
        "Может менять настройки и удалять все сигнатуры",
        "可以更改设置并删除所有信号",
    ),
    "Configuration": ("Konfiguration", "Конфигурация", "配置"),
    "Settings": ("Einstellungen", "Настройки", "设置"),
    "Keep signatures (days)": (
        "Signaturen behalten (Tage)",
        "Хранить сигнатуры (дней)",
        "信号保留（天）",
    ),
    "Days a signature counts after its last check. After that it is ignored and removed by the daily cleanup.": (
        "Tage, die eine Signatur nach ihrer letzten Prüfung gilt. Danach wird sie ignoriert und von der täglichen Bereinigung entfernt.",
        "Сколько дней сигнатура действует после последней проверки. Затем она игнорируется и удаляется ежедневной очисткой.",
        "信号在最后一次检查后有效的天数。之后它将被忽略，并由每日清理删除。",
    ),
    "Cleanup": ("Bereinigung", "Очистка", "清理"),
    "Save": ("Speichern", "Сохранить", "保存"),
    "Settings saved.": ("Einstellungen gespeichert.", "Настройки сохранены.", "设置已保存。"),
    "Delete all signatures": ("Alle Signaturen löschen", "Удалить все сигнатуры", "删除所有信号"),
    "Cancel": ("Abbrechen", "Отмена", "取消"),
    "Delete": ("Löschen", "Удалить", "删除"),
    # signature list
    "First seen": ("Zuerst gesehen", "Впервые замечена", "首次发现"),
    "Checked by": ("Geprüft von", "Проверил", "检查者"),
    "expired": ("abgelaufen", "истекла", "已过期"),
}

PLURALS = {
    "Deleted %(count)d signature.": (
        ["%(count)d Signatur gelöscht.", "%(count)d Signaturen gelöscht."],
        ["Удалена %(count)d сигнатура.", "Удалено %(count)d сигнатуры.", "Удалено %(count)d сигнатур."],
        ["已删除 %(count)d 个信号。"],
    ),
    "The shared list holds %(counter)s signature. Deleting empties it for everybody at once; it cannot be undone.": (
        [
            "Die gemeinsame Liste enthält %(counter)s Signatur. Löschen leert sie für alle auf einmal; das lässt sich nicht rückgängig machen.",
            "Die gemeinsame Liste enthält %(counter)s Signaturen. Löschen leert sie für alle auf einmal; das lässt sich nicht rückgängig machen.",
        ],
        [
            "В общем списке %(counter)s сигнатура. Удаление сразу очищает его для всех; отменить нельзя.",
            "В общем списке %(counter)s сигнатуры. Удаление сразу очищает его для всех; отменить нельзя.",
            "В общем списке %(counter)s сигнатур. Удаление сразу очищает его для всех; отменить нельзя.",
        ],
        ["共享列表中有 %(counter)s 个信号。删除会立即为所有人清空列表，且无法撤销。"],
    ),
    "Delete %(counter)s signature from the shared list?": (
        [
            "%(counter)s Signatur aus der gemeinsamen Liste löschen?",
            "Alle %(counter)s Signaturen aus der gemeinsamen Liste löschen?",
        ],
        [
            "Удалить %(counter)s сигнатуру из общего списка?",
            "Удалить все %(counter)s сигнатуры из общего списка?",
            "Удалить все %(counter)s сигнатур из общего списка?",
        ],
        ["从共享列表中删除全部 %(counter)s 个信号？"],
    ),
    "%(counter)s line skipped: no Cosmic Signature or Cosmic Anomaly of an English client (ships, structures, other client languages).": (
        [
            "%(counter)s Zeile übersprungen: keine Cosmic Signature oder Cosmic Anomaly eines englischen Clients (Schiffe, Strukturen, andere Client-Sprachen).",
            "%(counter)s Zeilen übersprungen: keine Cosmic Signature oder Cosmic Anomaly eines englischen Clients (Schiffe, Strukturen, andere Client-Sprachen).",
        ],
        [
            "%(counter)s строка пропущена: не Cosmic Signature и не Cosmic Anomaly английского клиента (корабли, структуры, другие языки клиента).",
            "%(counter)s строки пропущены: не Cosmic Signature и не Cosmic Anomaly английского клиента (корабли, структуры, другие языки клиента).",
            "%(counter)s строк пропущено: не Cosmic Signature и не Cosmic Anomaly английского клиента (корабли, структуры, другие языки клиента).",
        ],
        ["已跳过 %(counter)s 行：不是英文客户端的 Cosmic Signature 或 Cosmic Anomaly（舰船、建筑、其他客户端语言）。"],
    ),
    "At most %(max)d line per paste.": (
        ["Höchstens %(max)d Zeile pro Einfügen.", "Höchstens %(max)d Zeilen pro Einfügen."],
        [
            "Не более %(max)d строки за одну вставку.",
            "Не более %(max)d строк за одну вставку.",
            "Не более %(max)d строк за одну вставку.",
        ],
        ["每次粘贴最多 %(max)d 行。"],
    ),
    "Signatures are shared with everybody who has access and count for %(days)s day after their last check.": (
        [
            "Signaturen werden mit allen mit Zugriff geteilt und gelten %(days)s Tag nach ihrer letzten Prüfung.",
            "Signaturen werden mit allen mit Zugriff geteilt und gelten %(days)s Tage nach ihrer letzten Prüfung.",
        ],
        [
            "Сигнатуры видны всем, у кого есть доступ, и действуют %(days)s день после последней проверки.",
            "Сигнатуры видны всем, у кого есть доступ, и действуют %(days)s дня после последней проверки.",
            "Сигнатуры видны всем, у кого есть доступ, и действуют %(days)s дней после последней проверки.",
        ],
        ["信号与所有有权限的人共享，在最后一次检查后 %(days)s 天内有效。"],
    ),
}


def problems():
    """What is malformed in the entries above, as readable lines.

    tools/translate.py stops on any of these before it touches a catalogue,
    and the normal test suite runs the same check: a tuple one language short
    would otherwise end in an IndexError deep inside the fill, and a plural
    with the wrong number of forms or a lost placeholder would only show when
    a page renders it.
    """
    import re

    placeholder = re.compile(r"%\([a-z_]+\)[sd]|\{[^}]*\}")
    found = []

    def check(msgid, text, where):
        if not isinstance(text, str) or not text:
            found.append(f"{where}: {msgid!r} has an empty or non-text translation")
        elif sorted(placeholder.findall(text)) != sorted(placeholder.findall(msgid)):
            found.append(f"{where}: {msgid!r} has other placeholders than the English")

    for msgid, values in TRANSLATIONS.items():
        if not isinstance(values, tuple) or len(values) != len(LANGUAGES):
            found.append(f"{msgid!r} needs one translation per language {LANGUAGES}")
            continue
        for language, text in zip(LANGUAGES, values):
            check(msgid, text, language)

    for msgid, values in PLURALS.items():
        if not isinstance(values, tuple) or len(values) != len(LANGUAGES):
            found.append(f"{msgid!r} needs one list of plural forms per language {LANGUAGES}")
            continue
        for language, forms in zip(LANGUAGES, values):
            wanted = int(re.search(r"nplurals=(\d+)", PLURAL_FORMS[language]).group(1))
            if not isinstance(forms, list) or len(forms) != wanted:
                found.append(f"{language}: {msgid!r} needs {wanted} plural forms")
                continue
            for text in forms:
                check(msgid, text, language)

    return found
