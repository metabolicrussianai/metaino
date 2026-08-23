#!/usr/bin/env python3
'''Регрессионные тесты: морфология, разбор дат, правило шапки документа.

Запуск: python test_morphology.py
Код возврата 1 при любом провале.

Все случаи ниже — настоящие баги, найденные 23.08.2026 прогоном кода:
  * фамилии на й давали гайдайа вместо гайдая;
  * творительный на шипящую давал шендеровичом вместо шендеровичем;
  * дата 15.03.2024 не распознавалась, из-за чего --as-of молча
    показывал текущий реестр вместо исторического;
  * плашка в шапке помечала маркированными ВСЕ упоминания в тексте,
    включая лиц, к которым она не относится.

Не удаляйте случаи из этого файла. Каждый стоит за конкретным отказом.
'''
import sys

from inoagent_check import (Hit, Record, build_index, find_hits, mark_hits,
                            parse_date, surname_forms)

FORM_CASES = {
    'Иванов': ('иванова', 'иванову', 'ивановым', 'иванове'),
    'Петрова': ('петровой', 'петрову'),
    'Невзлин': ('невзлина', 'невзлину'),
    'Гуриев': ('гуриева', 'гуриеву'),
    'Гайдай': ('гайдая', 'гайдаю', 'гайдаем'),
    'Быков': ('быкова', 'быкову'),
    'Шендерович': ('шендеровича', 'шендеровичу', 'шендеровичем'),
    'Кара-Мурза': ('кара-мурзы', 'кара-мурзе', 'кара-мурзу'),
    'Гельман': ('гельмана', 'гельману'),
    'Акунин': ('акунина', 'акунину'),
    'Улицкая': ('улицкой', 'улицкую'),
    'Троицкий': ('троицкого', 'троицкому', 'троицким'),
    'Гордон': ('гордона', 'гордону'),
    'Соболь': ('соболя', 'соболю', 'соболем'),
}

INDECLINABLE = ('Шевченко', 'Дурново', 'Черных')

DATE_CASES = (
    ('15.03.2024', '2024-03-15'),
    ('01.02.2022', '2022-02-01'),
    ('2024-03-15', '2024-03-15'),
    ('нет даты', ''),
    ('15/03/2024', ''),
    ('', ''),
)

MIN_RECALL = 1.0

failures = []


def check(title, condition, detail=''):
    if condition:
        print('ok   ' + title)
    else:
        print('FAIL ' + title + ('  ' + detail if detail else ''))
        failures.append(title)


def test_forms():
    expected_total = 0
    found_total = 0
    for base, expected in FORM_CASES.items():
        forms = surname_forms(base)
        missing = [f for f in expected if f not in forms]
        expected_total += len(expected)
        found_total += len(expected) - len(missing)
        check('падежные формы: ' + base, not missing,
              'не порождено: ' + ', '.join(missing) if missing else '')
    recall = found_total / expected_total if expected_total else 0.0
    check('recall морфологии ' + str(round(recall, 3)) + ' >= ' + str(MIN_RECALL),
          recall >= MIN_RECALL)


def test_base_form_present():
    for base in list(FORM_CASES) + list(INDECLINABLE):
        forms = surname_forms(base)
        check('исходная форма сохранена: ' + base, base.lower() in forms)


def test_indeclinable():
    for base in INDECLINABLE:
        forms = surname_forms(base)
        check('несклоняемая без лишних форм: ' + base, len(forms) == 1,
              'получено: ' + ', '.join(sorted(forms)))


def test_dates():
    for raw, expected in DATE_CASES:
        got = parse_date(raw)
        check('разбор даты ' + repr(raw), got == expected,
              'ожидалось ' + repr(expected) + ', получено ' + repr(got))


def test_short_surname_found_at_default_threshold():
    records = [Record(0, 'Быков Дмитрий Львович', 'person', '2024-01-01')]
    index = build_index(records)
    text = 'Вчера редакция сослалась на Быкова без каких-либо пояснений.'
    hits = find_hits(text, index, 0.5)
    check('короткая фамилия находится при пороге 0.5', len(hits) == 1,
          'найдено попаданий: ' + str(len(hits)))


def build_two_person_document():
    head = ('Настоящий материал произведён Ивановым И. И., включённым в реестр '
            'иностранных агентов. ')
    filler = 'Далее идёт длинный текст интервью. ' * 60
    tail = 'В финале автор ссылается на Петрову М. С. без каких-либо оговорок.'
    return head + filler + tail


def test_head_plate_does_not_cover_other_person():
    text = build_two_person_document()
    start = text.index('Петрову')
    hit = Hit(1, 'Петрова Мария Сергеевна', 0.55, start, start + 7, 'Петрову М. С.')
    mark_hits(text, [hit], None)
    check('плашка в шапке НЕ маркирует чужое упоминание', hit.marked is False)


def test_head_plate_covers_named_person():
    text = build_two_person_document()
    start = text.index('Ивановым')
    hit = Hit(0, 'Иванов Иван Иванович', 0.55, start, start + 8, 'Ивановым И. И.')
    mark_hits(text, [hit], None)
    check('плашка в шапке маркирует названное в ней лицо', hit.marked is True)


def test_marker_in_window():
    text = ('Разговор с Гельманом, включённым в реестр иностранных агентов, '
            'состоялся в мае.')
    start = text.index('Гельманом')
    hit = Hit(2, 'Гельман Марат Александрович', 0.72, start, start + 9, 'Гельманом')
    mark_hits(text, [hit], None)
    check('маркер в окне вокруг упоминания засчитывается', hit.marked is True)


def test_no_marker_anywhere():
    text = 'Мы поговорили с Гельманом о современном искусстве и уехали.'
    start = text.index('Гельманом')
    hit = Hit(2, 'Гельман Марат Александрович', 0.72, start, start + 9, 'Гельманом')
    mark_hits(text, [hit], None)
    check('без маркера упоминание остаётся непокрытым', hit.marked is False)


def main():
    test_forms()
    test_base_form_present()
    test_indeclinable()
    test_dates()
    test_short_surname_found_at_default_threshold()
    test_head_plate_does_not_cover_other_person()
    test_head_plate_covers_named_person()
    test_marker_in_window()
    test_no_marker_anywhere()
    print()
    if failures:
        print('провалов: ' + str(len(failures)))
        for title in failures:
            print('  - ' + title)
        return 1
    print('все проверки пройдены')
    return 0


if __name__ == '__main__':
    sys.exit(main())
