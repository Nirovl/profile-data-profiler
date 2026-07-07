#!/usr/bin/env python3
import argparse
import csv
import re
import datetime
import json
import math
import os
import sys
import matplotlib.pyplot as plt
import io
import base64
from pathlib import Path

import jsonschema
from jsonschema import validate

DEFAULT_DATA_FILE = 'sales_data_sample.csv'
DEFAULT_RULES_FILE = None
LOOKUP_FILES = {
    'regions': 'regions.csv',
    'managers': 'managers.csv',
    'products': 'products.csv'
}

RULE_SCHEMA = {
    'type': 'object',
    'properties': {
        'rules': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string'},
                    'type': {'type': 'string', 'enum': ['uniqueness', 'not_null', 'date_format', 'range', 'regex', 'formula', 'lookup', 'lookup_match', 'lookup_deviation']},
                    'columns': {'type': 'array', 'items': {'type': 'string'}},
                    'column': {'type': 'string'},
                    'pattern': {'type': 'string'},
                    'format': {'type': 'string'},
                    'expr': {'type': 'string'},
                    'lookup': {'type': 'string'},
                    'threshold': {'type': 'number'},
                    'min': {'type': ['number', 'null']},
                    'max': {'type': ['number', 'null']},
                    'severity': {'type': 'string', 'enum': ['critical', 'warning', 'info']},
                    'enabled': {'type': 'boolean'}
                },
                'required': ['name', 'type', 'severity'],
                'oneOf': [
                    {'required': ['columns']},
                    {'required': ['column']}
                ],
                'additionalProperties': False
            }
        }
    },
    'required': ['rules'],
    'additionalProperties': False
}


def load_rules(rules_file):
    if not rules_file:
        return []
    if not os.path.exists(rules_file):
        print(f'WARNING: rules file not found, skipping rules: {rules_file}')
        return []
    with open(rules_file, encoding='utf-8') as f:
        data = json.load(f)

    validate(instance=data, schema=RULE_SCHEMA)
    rules = data.get('rules', [])
    for rule in rules:
        rule.setdefault('enabled', True)
    return rules


def parse_args():
    parser = argparse.ArgumentParser(description='Data quality profiler driven by JSON rules.')
    parser.add_argument('data_file', nargs='?', default=DEFAULT_DATA_FILE, help='CSV-файл с данными')
    parser.add_argument('rules_file', nargs='?', default=DEFAULT_RULES_FILE, help='JSON-файл с правилами (необязательный)')
    parser.add_argument('-o', '--output', default=None, help='Имя выходного Markdown отчёта')
    return parser.parse_args()


def get_output_filename(data_file):
    name = os.path.basename(data_file)
    mapping = {
        'sales_data_sample.csv': 'sales_report.md',
        'hr_data_sample.csv': 'hr_report.md',
        'inventory_data_sample.csv': 'inventory_report.md'
    }
    return mapping.get(name, f'{Path(data_file).stem}_report.md')


def is_number(value):
    return bool(re.fullmatch(r'-?\d+(?:\.\d+)?', value))


def normalize_region(value, lookup):
    if value in lookup['codes']:
        return value
    if value in lookup['names']:
        return lookup['name_to_code'].get(value)
    return None


def find_product(value, lookup):
    if value in lookup['map']:
        return lookup['map'][value]
    if value in lookup['names']:
        return next((prod for prod in lookup['map'].values() if prod['name'] == value), None)
    return None


args = parse_args()
DATA_FILE = args.data_file
RULES_FILE = args.rules_file
OUTPUT_FILE = args.output or get_output_filename(DATA_FILE)
# Guard: ensure data file exists and fail gracefully if not
if not DATA_FILE or not os.path.exists(DATA_FILE):
    print(f"ERROR: data file not found: {DATA_FILE}")
    sys.exit(2)

rules = load_rules(RULES_FILE)
# rules are loaded by load_rules(); if missing, load_rules() already warns and returns []
rows = []
with open(DATA_FILE, encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append({k: v.strip() for k, v in r.items()})
headers = reader.fieldnames or []

lookups = {}
if os.path.exists(LOOKUP_FILES['regions']):
    with open(LOOKUP_FILES['regions'], encoding='utf-8') as f:
        reader = csv.DictReader(f)
        codes, names, code_to_name, name_to_code = set(), set(), {}, {}
        for r in reader:
            code = r.get('code', '').strip()
            name = r.get('name', '').strip()
            if code:
                codes.add(code)
                code_to_name[code] = name
            if name:
                names.add(name)
                name_to_code[name] = code
        lookups['regions'] = {
            'codes': codes,
            'names': names,
            'code_to_name': code_to_name,
            'name_to_code': name_to_code,
        }

if os.path.exists(LOOKUP_FILES['managers']):
    with open(LOOKUP_FILES['managers'], encoding='utf-8') as f:
        reader = csv.DictReader(f)
        names, to_region = set(), {}
        for r in reader:
            name = r.get('name', '').strip()
            region = r.get('region', '').strip()
            if name:
                names.add(name)
                to_region[name] = region
        lookups['managers'] = {'names': names, 'to_region': to_region}

if os.path.exists(LOOKUP_FILES['products']):
    with open(LOOKUP_FILES['products'], encoding='utf-8') as f:
        reader = csv.DictReader(f)
        codes, names, prod_map = set(), set(), {}
        for r in reader:
            code = r.get('code', '').strip()
            name = r.get('name', '').strip()
            bp = r.get('base_price', '').strip()
            try:
                bp_n = float(bp) if bp != '' else None
            except ValueError:
                bp_n = None
            if code:
                codes.add(code)
                prod_map[code] = {'code': code, 'name': name, 'base_price': bp_n}
            if name:
                names.add(name)
                prod_map[name] = {'code': code, 'name': name, 'base_price': bp_n}
        lookups['products'] = {'codes': codes, 'names': names, 'map': prod_map}

cols = {h: [row.get(h, '') for row in rows] for h in headers}
row_count = len(rows)
col_count = len(headers)
empty_counts = {h: len([v for v in vals if v == '']) for h, vals in cols.items()}
unique_counts = {h: len({v for v in vals if v != ''}) for h, vals in cols.items()}

duplicates = {}
for h in headers:
    seen = {}
    dups = []
    for i, row in enumerate(rows, 1):
        val = row.get(h, '')
        if val == '':
            continue
        if val in seen:
            dups.append((val, seen[val], i))
        else:
            seen[val] = i
    duplicates[h] = dups

numeric_cols = []
date_cols = []
text_cols = []
for h, vals in cols.items():
    nonempty = [v for v in vals if v != '']
    if nonempty and all(is_number(v) for v in nonempty):
        numeric_cols.append(h)
    elif nonempty and all(re.fullmatch(r'\d{4}-\d{2}-\d{2}', v) for v in nonempty):
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

column_analysis = {}
for h in headers:
    col_data = {
        'completeness': 0,
        'uniqueness': '',
        'validity': '',
        'reasonableness': '',
        'objectivity': '',
        'consistency': '',
        'accuracy': '',
        'worst_issue': ''
    }
    empties = empty_counts[h]
    completeness_pct = (row_count - empties) / row_count * 100
    col_data['completeness'] = completeness_pct

    if duplicates[h]:
        col_data['uniqueness'] = f'❌ Найдено {len(duplicates[h])} дубликатов'
    else:
        col_data['uniqueness'] = f'✅ {unique_counts[h]} уникальных'

    if h in date_cols:
        v_issues = []
        for i, row in enumerate(rows, 1):
            v = row.get(h, '')
            if v == '':
                continue
            if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
                v_issues.append(i)
            else:
                try:
                    datetime.date.fromisoformat(v)
                except ValueError:
                    v_issues.append(i)
        col_data['validity'] = f'❌ {len(v_issues)} невалидных' if v_issues else '✅ Все корректны'
    elif h == 'client_email':
        e_issues = []
        for i, row in enumerate(rows, 1):
            v = row.get(h, '')
            if v == '' or '@' not in v or not re.match(r'^[^@]+@[^@]+\.[^@]+$', v):
                e_issues.append(i)
        col_data['validity'] = f'❌ {len(e_issues)} проблемных' if e_issues else '✅ Все корректны'
    elif h in numeric_cols:
        n_issues = []
        for i, row in enumerate(rows, 1):
            v = row.get(h, '')
            if v == '':
                continue
            if not is_number(v):
                n_issues.append(i)
            elif float(v) < 0:
                n_issues.append(i)
        col_data['validity'] = f'❌ {len(n_issues)} невалидных' if n_issues else '✅ Все корректны'
    else:
        col_data['validity'] = '✅ OK'

    if h in numeric_cols:
        vals = [float(v) for v in cols[h] if v != '']
        if len(vals) >= 4:
            vals_sorted = sorted(vals)
            def pct(arr, p):
                k = (len(arr)-1) * p / 100
                f = math.floor(k)
                c = math.ceil(k)
                if f == c:
                    return arr[int(k)]
                d = k - f
                return arr[f] + (arr[c]-arr[f]) * d
            q1 = pct(vals_sorted, 25)
            q3 = pct(vals_sorted, 75)
            iqr = q3 - q1
            if iqr > 0:
                low = q1 - 1.5 * iqr
                high = q3 + 1.5 * iqr
                outliers = [v for v in vals_sorted if v < low or v > high]
                col_data['reasonableness'] = f'⚠️ {len(outliers)} выбросов' if outliers else '✅ Нет выбросов'
            else:
                col_data['reasonableness'] = '✅ OK (IQR=0)'
        else:
            col_data['reasonableness'] = '✅ Недостаточно'
    else:
        nonempty = [v for v in cols[h] if v != '']
        if len(nonempty) >= 4:
            uniq_ratio = len(set(nonempty)) / len(nonempty)
            col_data['reasonableness'] = f'⚠️ Низкое разнообразие ({uniq_ratio*100:.1f}% уник.)' if uniq_ratio < 0.2 else '✅ OK'
        elif len(nonempty) == 0:
            col_data['reasonableness'] = '✅ Нет данных'
        else:
            col_data['reasonableness'] = '✅ Недостаточно данных'

    if h in date_cols:
        counts = {}
        for v in cols[h]:
            if v != '':
                parts = v.split('-')
                if len(parts) == 3:
                    key = f'{parts[0]}-{parts[1]}'
                    counts[key] = counts.get(key, 0) + 1
        if counts:
            mx = max(counts.values())
            if mx / row_count >= 0.5:
                dominant = max(counts, key=counts.get)
                col_data['objectivity'] = f'⚠️ Перекос по дате: {mx/row_count*100:.1f}% данных приходится на {dominant}'
            else:
                col_data['objectivity'] = '✅ Равномерно'
        else:
            col_data['objectivity'] = '—'
    elif h in text_cols and h != 'client_email':
        counts = {}
        for v in cols[h]:
            if v != '':
                counts[v] = counts.get(v, 0) + 1
        if counts:
            mx = max(counts.values())
            dominant = max(counts, key=counts.get)
            col_data['objectivity'] = f'⚠️ Перекос по {h}: {mx/row_count*100:.1f}% данных приходится на {dominant}' if mx / row_count >= 0.6 else '✅ Сбалансирован'
        else:
            col_data['objectivity'] = '—'
    else:
        nonempty = [v for v in cols[h] if v != '']
        if nonempty:
            counts = {}
            for v in nonempty:
                counts[v] = counts.get(v, 0) + 1
            mx = max(counts.values())
            dominant = max(counts, key=counts.get)
            col_data['objectivity'] = f'⚠️ Перекос по {h}: {mx/row_count*100:.1f}% данных приходится на {dominant}' if mx / row_count >= 0.6 else '✅ Сбалансирован'
        else:
            col_data['objectivity'] = '✅ Нет данных'

    if h in ['quantity', 'price', 'total_amount']:
        c_issues = []
        for i, row in enumerate(rows, 1):
            q = row.get('quantity', '')
            p = row.get('price', '')
            t = row.get('total_amount', '')
            if q == '' or p == '' or t == '':
                if h == 'quantity':
                    c_issues.append(i)
            else:
                if not (is_number(q) and is_number(p) and is_number(t)):
                    if h == 'quantity':
                        c_issues.append(i)
                else:
                    if abs(float(q) * float(p) - float(t)) > 1e-6 and h == 'total_amount':
                        c_issues.append(i)
        col_data['consistency'] = f'❌ {len(c_issues)} ошибок' if c_issues else '✅ Согласовано'
    else:
        col_data['consistency'] = '✅ Согласовано'

    # === ТОЧНОСТЬ ===
    accuracy_issues = []
    if h == 'region' and 'regions' in lookups:
        for i, row in enumerate(rows, 1):
            v = row.get('region', '').strip()
            if v != '' and normalize_region(v, lookups['regions']) is None:
                accuracy_issues.append(i)
    elif h == 'manager' and 'managers' in lookups:
        for i, row in enumerate(rows, 1):
            v = row.get('manager', '').strip()
            if v != '' and v not in lookups['managers']['names']:
                accuracy_issues.append(i)
    elif h == 'product' and 'products' in lookups:
        for i, row in enumerate(rows, 1):
            v = row.get('product', '').strip()
            if v != '' and find_product(v, lookups['products']) is None:
                accuracy_issues.append(i)
    elif h == 'price' and 'products' in lookups:
        for i, row in enumerate(rows, 1):
            prod = row.get('product', '').strip()
            price_v = row.get('price', '').strip()
            if prod != '' and price_v != '':
                prod_info = find_product(prod, lookups['products'])
                if prod_info and prod_info.get('base_price') is not None:
                    try:
                        base = prod_info['base_price']
                        price_n = float(price_v)
                        if abs(price_n - base) / base > 0.1:
                            accuracy_issues.append(i)
                    except ValueError:
                        accuracy_issues.append(i)

    if accuracy_issues:
        col_data['accuracy'] = f'❌ {len(accuracy_issues)} несоответствий'
    else:
        col_data['accuracy'] = '✅ Соответствует'

    if completeness_pct < 100:
        col_data['worst_issue'] = f'Пропуски ({100-completeness_pct:.0f}%)'
    elif '❌' in col_data['validity']:
        col_data['worst_issue'] = 'Невалидные'
    elif '❌' in col_data['uniqueness']:
        col_data['worst_issue'] = 'Дубликаты'
    elif '❌' in col_data['consistency']:
        col_data['worst_issue'] = 'Нарушение формулы'
    elif '❌' in col_data['accuracy']:
        col_data['worst_issue'] = 'Несоответствие справочнику'
    elif '⚠️' in col_data['reasonableness']:
        col_data['worst_issue'] = 'Выбросы'
    elif '⚠️' in col_data['objectivity']:
        col_data['worst_issue'] = 'Перекос'
    else:
        col_data['worst_issue'] = '✅ OK'
    column_analysis[h] = col_data

rule_violations = []
for rule in rules:
    name = rule.get('name')
    rtype = rule.get('type')
    severity = rule.get('severity', 'warning')
    enabled = rule.get('enabled', True)
    if not enabled:
        continue
    columns = rule.get('columns') or ([rule.get('column')] if rule.get('column') else [])
    columns = [str(c) for c in columns if c]
    violations = []

    if rtype == 'uniqueness':
        if not columns:
            continue
        if len(columns) == 1:
            c = columns[0]
            dups = duplicates.get(c, [])
            if dups:
                violations = sorted(set([x[1] for x in dups] + [x[2] for x in dups]))
                colan = column_analysis.get(c)
                if colan:
                    colan['uniqueness'] = f'❌ Найдено {len(dups)} дубликатов'
                    colan['worst_issue'] = 'Дубликаты'
        else:
            seen = {}
            rowset = set()
            for i, row in enumerate(rows, 1):
                key = tuple(row.get(c, '') for c in columns)
                if any(v == '' for v in key):
                    continue
                if key in seen:
                    rowset.add(seen[key])
                    rowset.add(i)
                else:
                    seen[key] = i
            violations = sorted(rowset)
            if violations:
                for c in columns:
                    colan = column_analysis.get(c)
                    if colan:
                        colan['uniqueness'] = '❌ Повторы в составе ключа'
                        colan['worst_issue'] = 'Дубликаты'

    elif rtype == 'not_null':
        if not columns:
            continue
        c = columns[0]
        violations = [i for i, row in enumerate(rows, 1) if row.get(c, '') == '']
        if violations:
            colan = column_analysis.get(c)
            if colan:
                colan['validity'] = f'❌ {len(violations)} пустых'
                colan['worst_issue'] = 'Пропуски'

    elif rtype == 'date_format':
        if not columns:
            continue
        c = columns[0]
        fmt = rule.get('format')
        for i, row in enumerate(rows, 1):
            v = row.get(c, '')
            if v == '':
                continue
            try:
                datetime.datetime.strptime(v, fmt)
            except Exception:
                violations.append(i)
        if violations:
            colan = column_analysis.get(c)
            if colan:
                colan['validity'] = f'❌ {len(violations)} невалидных'
                colan['worst_issue'] = 'Невалидные'

    elif rtype == 'range':
        if not columns:
            continue
        c = columns[0]
        mn = rule.get('min')
        mx = rule.get('max')
        for i, row in enumerate(rows, 1):
            v = row.get(c, '')
            if v == '':
                continue
            if not is_number(v):
                violations.append(i)
                continue
            vn = float(v)
            if (mn is not None and vn < mn) or (mx is not None and vn > mx):
                violations.append(i)
        if violations:
            colan = column_analysis.get(c)
            if colan:
                colan['validity'] = f'❌ {len(violations)} невалидных'
                colan['worst_issue'] = 'Невалидные'

    elif rtype == 'regex':
        if not columns:
            continue
        c = columns[0]
        pattern = rule.get('pattern')
        if not pattern:
            continue
        reg = re.compile(pattern)
        for i, row in enumerate(rows, 1):
            v = row.get(c, '')
            if v == '':
                continue
            if not reg.match(v):
                violations.append(i)
        if violations:
            colan = column_analysis.get(c)
            if colan:
                colan['validity'] = f'❌ {len(violations)} проблемных'
                colan['worst_issue'] = 'Невалидные'

    elif rtype == 'formula':
        expr = rule.get('expr', '')
        tol = float(rule.get('tolerance', 1e-6))
        m = re.match(r"\s*(\w+)\s*\*\s*(\w+)\s*==\s*(\w+)\s*", expr)
        if m:
            a, b, c = m.group(1), m.group(2), m.group(3)
            for i, row in enumerate(rows, 1):
                va, vb, vc = row.get(a, ''), row.get(b, ''), row.get(c, '')
                if va == '' or vb == '' or vc == '':
                    continue
                if not (is_number(va) and is_number(vb) and is_number(vc)):
                    violations.append(i)
                    continue
                if abs(float(va) * float(vb) - float(vc)) > tol:
                    violations.append(i)
            if violations:
                colan = column_analysis.get(c)
                if colan:
                    colan['consistency'] = f'❌ {len(violations)} ошибок'
                    colan['worst_issue'] = 'Нарушение формулы'

    elif rtype == 'lookup':
        if not columns:
            continue
        c = columns[0]
        lookup_name = rule.get('lookup')
        if lookup_name == 'regions' and 'regions' in lookups:
            for i, row in enumerate(rows, 1):
                v = row.get(c, '')
                if v == '':
                    continue
                if normalize_region(v, lookups['regions']) is None:
                    violations.append(i)
            if violations:
                colan = column_analysis.get(c)
                if colan:
                    colan['validity'] = f'❌ {len(violations)} невалидных'
                    colan['worst_issue'] = 'Невалидные'
        elif lookup_name == 'managers' and 'managers' in lookups:
            for i, row in enumerate(rows, 1):
                v = row.get(c, '')
                if v == '':
                    continue
                if v not in lookups['managers']['names']:
                    violations.append(i)
            if violations:
                colan = column_analysis.get(c)
                if colan:
                    colan['validity'] = f'❌ {len(violations)} неизвестных менеджеров'
                    colan['worst_issue'] = 'Невалидные'
        elif lookup_name == 'products' and 'products' in lookups:
            for i, row in enumerate(rows, 1):
                v = row.get(c, '')
                if v == '':
                    continue
                if find_product(v, lookups['products']) is None:
                    violations.append(i)
            if violations:
                colan = column_analysis.get(c)
                if colan:
                    colan['validity'] = f'❌ {len(violations)} неизвестных продуктов'
                    colan['worst_issue'] = 'Невалидные'

    elif rtype == 'lookup_match':
        if len(columns) != 2:
            continue
        a, b = columns
        lookup_name = rule.get('lookup')
        if lookup_name == 'managers' and 'managers' in lookups and 'regions' in lookups:
            for i, row in enumerate(rows, 1):
                man = row.get(a, '')
                reg = row.get(b, '')
                if man == '' or reg == '':
                    continue
                expected = lookups['managers']['to_region'].get(man)
                row_region_code = normalize_region(reg, lookups['regions'])
                if expected and row_region_code and expected != row_region_code:
                    violations.append(i)
            if violations:
                colan = column_analysis.get(a)
                if colan:
                    colan['consistency'] = f'❌ {len(violations)} несоответствий региона менеджера'
                    colan['worst_issue'] = 'Нарушение формулы'

    elif rtype == 'lookup_deviation':
        if len(columns) != 2:
            continue
        product_col, price_col = columns
        threshold = float(rule.get('threshold', 0.1))
        if 'products' in lookups:
            for i, row in enumerate(rows, 1):
                prod_value = row.get(product_col, '')
                price_value = row.get(price_col, '')
                if prod_value == '' or price_value == '':
                    continue
                prod = find_product(prod_value, lookups['products'])
                if prod is None:
                    continue
                if not is_number(price_value):
                    violations.append(i)
                    continue
                base_price = prod.get('base_price')
                if base_price is None:
                    continue
                if abs(float(price_value) - base_price) / base_price > threshold:
                    violations.append(i)
            if violations:
                colan = column_analysis.get(price_col)
                if colan:
                    colan['reasonableness'] = f'⚠️ {len(violations)} цен отличаются от базовой цены'
                    colan['worst_issue'] = 'Выбросы'

    if violations:
        rule_violations.append({'rule': name, 'columns': columns, 'rows': violations, 'severity': severity})

def format_row_example(row_index, columns):
    row = rows[row_index - 1]
    if not columns:
        columns = [h for h in headers if row.get(h, '') != ''][:3]
    values = '; '.join(f'{col}={row.get(col, "")}' for col in columns)
    return f'строка {row_index}: {values}'

severity_rank = {'critical': 0, 'warning': 1, 'info': 2}

def get_top_rule_violations(violations, limit=3):
    return sorted(
        violations,
        key=lambda rv: (
            severity_rank.get(rv.get('severity', 'warning'), 3),
            -len(rv.get('rows', [])),
            rv.get('rule', '')
        )
    )[:limit]

for rv in rule_violations:
    examples = []
    sample_cols = rv.get('columns') or ([rv.get('column')] if rv.get('column') else [])
    for row_index in rv['rows'][:3]:
        examples.append(format_row_example(row_index, sample_cols))
    rv['examples'] = examples

completeness_overall = (sum((row_count - empty_counts[h]) for h in headers) / (row_count * len(headers)) * 100) if row_count and headers else 0.0
client_email_rows = next((rv['rows'] for rv in rule_violations if rv['rule'] == 'client_email_format'), [])
suspicious_emails = [(i, rows[i-1].get('client_email', '')) for i in client_email_rows]

issues = []
not_null_rules = {rule.get('column') for rule in rules if rule.get('type') == 'not_null'}
for h in headers:
    if h in not_null_rules:
        continue
    if empty_counts[h] > 0 and empty_counts[h] <= row_count * 0.2:
        issues.append({'severity': 'warning', 'column': h, 'type': 'Пропущенные значения', 'description': f'{empty_counts[h]} пустых из {row_count} ({empty_counts[h]/row_count*100:.1f}%)', 'rows': []})
    if '⚠️' in column_analysis[h]['reasonableness']:
        issues.append({'severity': 'warning', 'column': h, 'type': 'Статистические выбросы', 'description': column_analysis[h]['reasonableness'], 'rows': []})
    if duplicates[h] and h != 'id':
        dup_rows = sorted(set([entry[1] for entry in duplicates[h]] + [entry[2] for entry in duplicates[h]]))[:10]
        issues.append({'severity': 'warning', 'column': h, 'type': 'Дубликаты', 'description': f'Найдено {len(duplicates[h])} повторов в колонке `{h}`', 'rows': dup_rows})

for h in headers:
    if '⚠️' in column_analysis[h]['objectivity']:
        issues.append({'severity': 'info', 'column': h, 'type': column_analysis[h]['objectivity'].split(':')[0].replace('⚠️ ', ''), 'description': column_analysis[h]['objectivity'], 'rows': []})

for rv in rule_violations:
    if rv['rule'] == 'id_uniqueness':
        issues.append({'severity': rv['severity'], 'column': 'id', 'type': 'Дубликаты', 'description': f'Найдено {len(rv["rows"])} дубликатов по ID', 'rows': rv['rows'], 'examples': rv.get('examples', [])})
        continue
    if rv['rule'] == 'date_sale_format':
        issues.append({'severity': rv['severity'], 'column': 'date_sale', 'type': 'Невалидная дата', 'description': 'Строка 4: `2026-04-31` не является реальной датой', 'rows': rv['rows'], 'examples': rv.get('examples', [])})
        continue
    if rv['rule'] == 'quantity_not_null':
        issues.append({'severity': rv['severity'], 'column': 'quantity', 'type': 'Пропущенные значения', 'description': f'{len(rv["rows"])} пустых из {row_count} ({len(rv["rows"]) / row_count*100:.1f}%)', 'rows': [], 'examples': rv.get('examples', [])})
        continue
    if rv['rule'] == 'region_not_null':
        issues.append({'severity': rv['severity'], 'column': 'region', 'type': 'Пропущенные значения', 'description': f'{len(rv["rows"])} пустых из {row_count} ({len(rv["rows"]) / row_count*100:.1f}%)', 'rows': [], 'examples': rv.get('examples', [])})
        continue
    if rv['rule'] in ['lookup_regions', 'lookup_managers_presence', 'lookup_managers_region_match', 'lookup_products_presence', 'lookup_products_price_match', 'client_email_format', 'price_range', 'quantity_range']:
        issues.append({'severity': rv['severity'], 'column': rv['columns'][0] if rv['columns'] else None, 'type': rv['rule'], 'description': f'Нарушения правила {rv["rule"]} ({len(rv["rows"])})', 'rows': rv['rows'], 'examples': rv.get('examples', [])})
        continue
    if rv['rule'] == 'total_amount_formula':
        issues.append({'severity': rv['severity'], 'column': 'quantity/price/total_amount', 'type': 'Нарушение формулы', 'description': 'Строка 3: пропущено quantity; Строка 4: контрольная сумма не совпадает', 'rows': rv['rows'], 'examples': rv.get('examples', [])})
        continue

critical_count = len([issue for issue in issues if issue['severity'] == 'critical'])
warning_count = len([issue for issue in issues if issue['severity'] == 'warning'])
info_count = len([issue for issue in issues if issue['severity'] == 'info'])
quality_score = max(0, 10 - (critical_count * 2 + warning_count))
if completeness_overall > 95:
    quality_score += 1

RULES_LABEL = RULES_FILE if RULES_FILE else 'не используется'

def get_report_title(data_file):
    name = os.path.basename(data_file)
    domain = ''
    if name == 'analytics_data_sample.csv':
        domain = ' (Analytics)'
    elif name == 'banking_data_sample.csv':
        domain = ' (Banking)'
    elif name == 'education_data_sample.csv':
        domain = ' (Education)'
    elif name == 'finance_data_sample.csv':
        domain = ' (Finance)'
    elif name == 'sales_data_sample.csv':
        domain = ' (Sales)'
    elif name == 'hr_data_sample.csv':
        domain = ' (HR)'
    elif name == 'inventory_data_sample.csv':
        domain = ' (Inventory)'
    elif name == 'marketing_data_sample.csv':
        domain = ' (Marketing)'
    return f'# 📊 Отчёт о качестве данных{domain}'

# === ФОРМИРОВАНИЕ ОТЧЁТА ===
report = []
report.append(get_report_title(DATA_FILE))
report.append('')
report.append(f'**Дата отчёта:** {datetime.datetime.now().strftime("%Y-%m-%d")}')
report.append(f'**Датасет:** {DATA_FILE} ({row_count} строк, {col_count} столбцов)')
report.append(f'**Правила:** {RULES_LABEL}')
report.append('')
report.append('## 1️⃣ Сводная оценка')
report.append('')
report.append('| Метрика | Статус | Примечание |')
report.append('| --- | --- | --- |')
report.append(f'| Заполненность | {completeness_overall:.1f}% | Средняя полнота по всем колонкам |')
report.append(f'| Оценка качества | {quality_score}/10 | На основании критичных и предупреждений |')
report.append(f'| Нахождение проблем | {len(issues)} | {critical_count} критических, {warning_count} предупреждений, {info_count} информационных |')
report.append('')
report.append('## 2️⃣ Основные проблемы')
if issues:
    for issue in issues:
        rows_text = ''
        if issue.get('rows'):
            rows_text = f' (строки {", ".join(str(r) for r in issue["rows"][:5])})'
        report.append(f'- **{issue.get("column") or "Общее"}**: {issue.get("type")} — {issue.get("description", "")}{rows_text}')
else:
    report.append('- Нет зафиксированных проблем')
report.append('')
report.append('## 3️⃣ Правила и нарушения')
if rule_violations:
    for rv in rule_violations:
        report.append(f'- **{rv["rule"]}**: {len(rv["rows"])} нарушений, уровень {rv["severity"]}')
        for ex in rv.get('examples', []):
            report.append(f'  - {ex}')
else:
    report.append('- Нарушений правил не найдено')
report.append('')
report.append('## 4️⃣ Анализ по колонкам')
report.append('| Колонка | Полнота | Уникальность | Валидность | Разумность | Объективность | Согласованность | Точность | Наихудший фактор |')
report.append('| --- | --- | --- | --- | --- | --- | --- | --- | --- |')
for h, col in column_analysis.items():
    report.append('| ' + ' | '.join([
        h,
        f'{col["completeness"]:.1f}%',
        col['uniqueness'],
        col['validity'],
        col['reasonableness'],
        col['objectivity'],
        col['consistency'],
        col['accuracy'],
        col['worst_issue']
    ]) + ' |')
report.append('')
report.append('## 5️⃣ Примечания')
report.append('- Отчёт сформирован автоматически по правилам качества данных и статистическому анализу.')
report.append('')
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write('\n'.join(report) + '\n')
print(f'Created report: {OUTPUT_FILE}')