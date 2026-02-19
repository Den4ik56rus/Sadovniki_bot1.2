#!/usr/bin/env python3
"""
Одноразовый скрипт: извлекает данные о сортах из WooCommerce CSV-экспорта
и сохраняет в структурированный JSON для использования в промптах бота.

Запуск: python scripts/extract_varieties_from_csv.py
Результат: data/varieties_reference.json
"""

import csv
import json
import re
from html.parser import HTMLParser
from pathlib import Path


class HTMLTextExtractor(HTMLParser):
    """Извлекает чистый текст из HTML."""
    def __init__(self):
        super().__init__()
        self.result = []

    def handle_data(self, data):
        self.result.append(data)

    def get_text(self):
        return ''.join(self.result)


# Маппинг: имя в CSV → (культура, тип сорта)
# Типы вручную на основе описаний с сайта
VARIETY_INFO = {
    # Смородина
    'Джонкер Ван Тетс': ('смородина', 'среднеранний'),
    'Ядреная': ('смородина', 'среднеспелый'),
    'Селеченская 2': ('смородина', 'среднеранний'),
    'Ровада': ('смородина', 'среднепоздний'),
    # Голубика
    'Эрли Блю': ('голубика', 'ранний'),
    'Спартан': ('голубика', 'среднеранний'),
    # Жимолость
    'Аврора': ('жимолость', 'среднепоздний'),
    'Хоней Би': ('жимолость', 'среднеранний'),
    'Бореал Бист': ('жимолость', 'средний'),
    'Бореал Близзард': ('жимолость', 'средний'),
    'Бореал Бьюти': ('жимолость', 'средний'),
    'Лазурная': ('жимолость', 'среднеранний'),
    'Голубое Веретено': ('жимолость', 'ранний'),
    'Синяя Птица': ('жимолость', 'ранний'),
    # Ежевика
    'Торнфри': ('ежевика', 'поздний, бесшипный'),
    'Агавам': ('ежевика', 'ранний, с шипами'),
    # Малина
    'Гусар': ('малина', 'летний'),
    'Соколица': ('малина', 'летний'),
    'Карамелька': ('малина', 'ремонтантный'),
    'Похвалинка': ('малина', 'ремонтантный'),
    'Малиновая гряда': ('малина', 'ремонтантный'),
    'Самохвал': ('малина', 'ремонтантный'),
    'Светлячок': ('малина', 'ремонтантный, жёлтоплодный'),
    'Энросадира': ('малина', 'ремонтантный'),
    'Конёк-Горбунок': ('малина', 'ремонтантный, ранний'),
    'Сластиха': ('малина', 'ремонтантный'),
    # Клубника
    'Ания': ('клубника', 'ремонтантный НСД'),
    'Шарлотта': ('клубника', 'ремонтантный НСД'),
    'Флорис': ('клубника', 'ремонтантный НСД'),
    'Мара Де Буа': ('клубника', 'ремонтантный НСД'),
    'Флорида Бьюти': ('клубника', 'ремонтантный НСД'),
    'Сенсация': ('клубника', 'среднеранний'),
    'Мальвина': ('клубника', 'поздний'),
    'Мармелада': ('клубника', 'среднеспелый'),
    'Аллегро': ('клубника', 'ранний'),
    'Зенга-Зенгана': ('клубника', 'среднепоздний'),
    'Квики': ('клубника', 'ультраранний'),
    'Клери': ('клубника', 'ранний'),
    'Рубин': ('клубника', 'поздний'),
    'Азия': ('клубника', 'среднеранний'),
    'Мариека': ('клубника', 'среднеспелый'),
    'Александра': ('клубника', 'ранний'),
    'Румба': ('клубника', 'ранний'),
    'Федерика': ('клубника', 'поздний'),
    'Москова': ('клубника', 'поздний'),
}

# Пропускаемые строки (не сорта)
SKIP_PREFIXES = [
    'Рекомендации по работе',
    'Рекомендации по посадке',
    'Рекомендации по подготовке',
]

# Рекламные фразы для удаления
AD_PATTERNS = [
    r'Купить саженцы[^.]*\.',
    r'Саженцы сорта [^\n]*питомник[^\n]*\.',
    r'Саженцы сорта [^\n]*«Клубничная[^\n]*\.',
    r'Саженцы сорта [^\n]*заказать доставку[^\n]*\.',
    r'[^\n]*приобрести в питомнике[^\n]*\.',
    r'[^\n]*приобрести на нашем сайте[^\n]*',
    r'Мы в питомнике «Клубничная королева»[^!]*!',
    r'[^\n]*можете приобрести[^\n]*\.',
    r'Готов сделать следующие сорта[^\n]*',
]


def clean_name(raw_name: str) -> str:
    """Убирает суффиксы возраста: '2х летка', '1,5 летка', etc."""
    name = raw_name.strip()
    name = re.sub(r'\s*\d[,.]?\d?\s*х?\s*лет\w*', '', name)
    name = re.sub(r'\s*\(Плодоносящий куст.*?\)', '', name)
    return name.strip()


def extract_text(html: str) -> str:
    """HTML → чистый текст."""
    extractor = HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def clean_description(text: str) -> str:
    """Убирает рекламу питомника и лишние пробелы."""
    # Нормализуем литеральные \\n → настоящие \n
    text = text.replace('\\n', '\n')
    for pattern in AD_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text


def split_dash_items(text: str) -> list[str]:
    """Разбивает текст по '—' или нумерации на отдельные пункты."""
    text = text.strip()

    # Разбиваем по длинному тире (—) НЕ между цифрами (чтобы не ломать "10—15 кг")
    # Также по нумерации emoji (1️⃣, 2️⃣...)
    parts = re.split(r'(?<!\d)—(?!\d)|\d️⃣\s*', text)
    result = []
    for part in parts:
        part = part.strip().lstrip('–- ').strip()
        if part and len(part) > 5:
            result.append(part)
    return result


def extract_structured_info(name: str, variety_type: str, text: str) -> dict:
    """Извлекает структурированную информацию о сорте из текста описания."""
    info = {
        'name': name,
        'type': variety_type,
    }

    # Извлекаем преимущества (секция "Преимущества сорта\n— ...")
    pros_match = re.search(
        r'Преимущества сорта[:\s]*\n?(.*?)(?=\n[🟦\s]*Недостатки|\nМинусы|\nСаженцы сорта|$)',
        text, re.DOTALL | re.IGNORECASE
    )
    if pros_match:
        info['pros'] = split_dash_items(pros_match.group(1))

    # Извлекаем недостатки (может быть с emoji 🟦 перед "Недостатки")
    cons_match = re.search(
        r'[🟦\s]*Недостатки сорта[:\s]*\n?(.*?)(?=\nСаженцы сорта|\nПреимущества|$)',
        text, re.DOTALL | re.IGNORECASE
    )
    if cons_match:
        info['cons'] = split_dash_items(cons_match.group(1))

    # Для старого формата: "Достоинства сорта: текст через запятую."
    if 'pros' not in info:
        old_pros = re.search(
            r'Достоинства сорта[:\s]*(.*?)(?:\.\n|\.$)',
            text, re.IGNORECASE
        )
        if old_pros:
            items = [p.strip() for p in old_pros.group(1).split(',') if p.strip() and len(p.strip()) > 3]
            info['pros'] = items

    # Основное описание (до преимуществ/недостатков)
    desc_parts = re.split(
        r'(?:\nПреимущества сорта|\nДостоинства сорта|\nНедостатки сорта)',
        text, flags=re.IGNORECASE
    )
    if desc_parts:
        info['description'] = desc_parts[0].strip()

    return info


def main():
    project_root = Path(__file__).parent.parent
    csv_path = project_root / 'data' / 'documents' / 'Сорта' / 'wc-product-export-18-2-2026-1771408583386.csv'
    output_path = project_root / 'data' / 'varieties_reference.json'

    if not csv_path.exists():
        print(f'CSV не найден: {csv_path}')
        return

    varieties_by_culture = {}
    seen_names = set()

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        next(reader)  # skip header

        for row in reader:
            if len(row) < 2:
                continue

            raw_name = row[0].strip()
            if any(raw_name.startswith(prefix) for prefix in SKIP_PREFIXES):
                continue

            name = clean_name(raw_name)
            if name in seen_names:
                continue
            seen_names.add(name)

            variety_info = VARIETY_INFO.get(name)
            if not variety_info:
                print(f'  ⚠️  Не найден в VARIETY_INFO: {name}')
                continue
            culture, variety_type = variety_info

            html_desc = row[1]
            if not html_desc.strip():
                print(f'  ⚠️  Пустое описание: {name}')
                continue

            text = extract_text(html_desc)
            text = clean_description(text)
            info = extract_structured_info(name, variety_type, text)

            if culture not in varieties_by_culture:
                varieties_by_culture[culture] = []
            varieties_by_culture[culture].append(info)

    # Сохраняем JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(varieties_by_culture, f, ensure_ascii=False, indent=2)

    # Статистика
    print(f'\nРезультат сохранён в {output_path}')
    print(f'Культур: {len(varieties_by_culture)}')
    for culture, varieties in sorted(varieties_by_culture.items()):
        print(f'  {culture}: {len(varieties)} сортов')
        for v in varieties:
            pros = v.get('pros', [])
            cons = v.get('cons', [])
            print(f'    - {v["name"]} ({v["type"]}), ✅{len(pros)} ❌{len(cons)}')
            for p in pros:
                print(f'        ✅ {p}')
            for c in cons:
                print(f'        ❌ {c}')


if __name__ == '__main__':
    main()
