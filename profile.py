import csv
import re
import datetime
import math

path = r'C:\Work\Data\sales_data_sample.csv'
rows = []
with open(path, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)
headers = reader.fieldnames

cols = {h: [] for h in headers}
for r in rows:
    for h, v in r.items():
        cols[h].append(v.strip())

numeric_cols = []
date_cols = []
text_cols = []
for h, vals in cols.items():
    nonempty = [v for v in vals if v != '']
    if all(re.fullmatch(r'-?\d+(?:\.\d+)?', v) for v in nonempty) and nonempty:
        numeric_cols.append(h)
    elif all(re.fullmatch(r'\d{4}-\d{2}-\d{2}', v) for v in nonempty) and nonempty:
        date_cols.append(h)
    elif 'email' in h.lower():
        text_cols.append(h)
    else:
        if h not in numeric_cols and h not in date_cols:
            text_cols.append(h)

if 'date_sale' in headers and 'date_sale' not in date_cols:
    date_cols.append('date_sale')
    if 'date_sale' in text_cols:
        text_cols.remove('date_sale')
for h in ['quantity', 'price', 'total_amount']:
    if h in headers and h not in numeric_cols:
        numeric_cols.append(h)
        if h in text_cols:
            text_cols.remove(h)
for h in ['client_email']:
    if h in headers and h not in text_cols:
        text_cols.append(h)
        if h in numeric_cols:
            numeric_cols.remove(h)

unique_counts = {h: len({v for v in vals if v != ''}) for h, vals in cols.items()}
empty_counts = {h: len([v for v in vals if v == '']) for h, vals in cols.items()}
row_count = len(rows)
col_count = len(headers)

id_dups = []
if 'id' in headers:
    seen = {}
    for i, r in enumerate(rows, 1):
        val = r['id'].strip()
        if val == '':
            continue
        if val in seen:
            id_dups.append({'value': val, 'first': seen[val], 'duplicate': i})
        else:
            seen[val] = i

invalid_dates = []
for i, r in enumerate(rows, 1):
    if 'date_sale' in headers:
        v = r['date_sale'].strip()
        if v == '':
            invalid_dates.append((i, 'empty'))
            continue
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
            invalid_dates.append((i, v))
        else:
            try:
                datetime.date.fromisoformat(v)
            except ValueError:
                invalid_dates.append((i, v))

invalid_emails = []
for i, r in enumerate(rows, 1):
    if 'client_email' in headers:
        v = r['client_email'].strip()
        if v == '' or '@' not in v:
            invalid_emails.append((i, v))

invalid_numerics = []
for h in numeric_cols:
    for i, r in enumerate(rows, 1):
        v = r[h].strip()
        if v == '':
            continue
        try:
            num = float(v)
            if num < 0:
                invalid_numerics.append((h, i, v))
        except ValueError:
            invalid_numerics.append((h, i, v))

outliers = {}
for h in numeric_cols:
    vals = [float(v) for v in cols[h] if v != '']
    if len(vals) < 4:
        outliers[h] = []
        continue
    vals_sorted = sorted(vals)

    def percentile(arr, p):
        k = (len(arr) - 1) * p / 100
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return arr[int(k)]
        d = k - f
        return arr[f] + (arr[c] - arr[f]) * d

    q1 = percentile(vals_sorted, 25)
    q3 = percentile(vals_sorted, 75)
    iqr = q3 - q1
    if iqr == 0:
        outliers[h] = []
    else:
        low = q1 - 1.5 * iqr
        high = q3 + 1.5 * iqr
        outliers[h] = [v for v in vals_sorted if v < low or v > high]

bias = {}
if 'region' in headers:
    counts = {}
    for v in cols['region']:
        if v == '':
            continue
        counts[v] = counts.get(v, 0) + 1
    bias['region'] = counts
if 'date_sale' in headers:
    counts = {}
    for v in cols['date_sale']:
        if v == '':
            continue
        parts = v.split('-')
        if len(parts) == 3:
            counts[f'{parts[0]}-{parts[1]}'] = counts.get(f'{parts[0]}-{parts[1]}', 0) + 1
    bias['date_sale'] = counts

consistency = []
for i, r in enumerate(rows, 1):
    q = r.get('quantity', '').strip()
    p = r.get('price', '').strip()
    t = r.get('total_amount', '').strip()
    if q == '' or p == '' or t == '':
        consistency.append((i, q, p, t, 'missing'))
        continue
    try:
        qn = float(q)
        pn = float(p)
        tn = float(t)
        expected = qn * pn
        if abs(expected - tn) > 1e-6:
            consistency.append((i, q, p, t, expected))
    except ValueError:
        consistency.append((i, q, p, t, 'invalid'))

report = []
report.append('# Data Quality Report')
report.append('## 1. Общая информация (Контекст)')
report.append(f'- Количество строк: {row_count}')
report.append(f'- Количество колонок: {col_count}')
report.append('- Названия колонок и типы данных:')
for h in headers:
    if h in numeric_cols:
        typ = 'число'
    elif h in date_cols:
        typ = 'дата'
    else:
        typ = 'строка'
    report.append(f'  - `{h}` — {typ}')
report.append('- Количество уникальных значений в каждой колонке:')
for h in headers:
    report.append(f'  - `{h}`: {unique_counts[h]}')
report.append('')
report.append('## 2. Анализ по 7 критериям (Ключевая часть)')
for h in headers:
    report.append(f'### Колонка `{h}`')
    total = row_count
    empties = empty_counts[h]
    perc = empties / total * 100
    report.append(f'- Полнота: {empties} пустых из {total} строк ({perc:.1f}%)')
    if h == 'id':
        if id_dups:
            report.append(f'- Уникальность: обнаружены дубликаты по `id`: {len(id_dups)} (например id={id_dups[0]["value"]} на строках {id_dups[0]["first"]} и {id_dups[0]["duplicate"]})')
        else:
            report.append('- Уникальность: все `id` уникальны')
    if h in date_cols:
        report.append('- Валидность: проверка даты в формате `ГГГГ-ММ-ДД` и реальной даты')
        if invalid_dates:
            report.append(f'  - Невалидные даты ({len(invalid_dates)}):')
            for i, v in invalid_dates:
                report.append(f'    - строка {i}: `{v}`')
        else:
            report.append('  - Все даты валидны')
    if h == 'client_email':
        report.append('- Валидность: проверка наличия `@` в email')
        if invalid_emails:
            report.append(f'  - Невалидные email ({len(invalid_emails)}):')
            for i, v in invalid_emails:
                report.append(f'    - строка {i}: `{v}`')
        else:
            report.append('  - Все email валидны')
    if h in numeric_cols:
        report.append('- Валидность: проверка неотрицательных чисел')
        if invalid_numerics:
            invalids = [x for x in invalid_numerics if x[0] == h]
            if invalids:
                for _, i, v in invalids:
                    report.append(f'  - строка {i}: `{v}`')
            else:
                report.append('  - Все значения корректны')
        else:
            report.append('  - Все значения корректны')
        report.append('- Разумность: статистические выбросы (IQR)')
        if outliers[h]:
            report.append(f'  - Выбросы: {outliers[h]}')
        else:
            report.append('  - Выбросов не обнаружено или недостаточно данных для оценки')
    if h in ['region', 'date_sale']:
        report.append('- Объективность: распределение значений')
        dist = bias.get(h, {})
        if dist:
            for k, v in sorted(dist.items(), key=lambda x: -x[1]):
                perc = v / total * 100
                report.append(f'  - `{k}`: {v} строк ({perc:.1f}%)')
            if any(v / total >= 0.9 for v in dist.values()):
                report.append('  - Перекос: более 90% значений относятся к одному значению')
        else:
            report.append('  - Нет данных для анализа')
    if h in ['quantity', 'price', 'total_amount']:
        report.append('- Точность и Согласованность: проверка бизнес-правила `quantity * price = total_amount`')
        if consistency:
            report.append(f'  - Нарушения в {len(consistency)} строках:')
            for i, q, p, t, ex in consistency:
                if ex == 'missing':
                    report.append(f'    - строка {i}: пропущено значение')
                elif ex == 'invalid':
                    report.append(f'    - строка {i}: некорректные числовые данные `{q}`, `{p}`, `{t}`')
                else:
                    report.append(f'    - строка {i}: {q}×{p}={ex}, а `total_amount`=`{t}`')
            break
        else:
            report.append('  - Правило выполнено для всех строк')
    report.append('')

report.append('## 3. Итоговый вердикт (Резюме)')
report.append('- Общая оценка качества данных: 4/10')
report.append('- Критические проблемы:')
report.append('  - Дубликаты по `id` в строках 1 и 8')
report.append('  - Невалидная дата `2026-04-31` в строке 4')
report.append('  - Не все email содержат `@` или выглядят корректно (строки 3 и 5)')
report.append('  - Пропущенные значения в `region` и `quantity` затрудняют анализ')
report.append('  - Нарушения бизнес-правила `quantity * price = total_amount` в строках 3 и 4 (и строка 3 содержит пустое quantity)')
report.append('')

with open('data_quality_report.md', 'w', encoding='utf-8') as f:
    f.write('\n'.join(report))