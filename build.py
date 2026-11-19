#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wykazy Ursus — pobieranie, parsowanie i generowanie strony.

Użycie:
    python build.py                 # bieżący rocznik
    python build.py --all           # wszystkie roczniki od 2019 do bieżącego
    python build.py --years 2019-2026
    python build.py --year 2025     # pojedynczy rocznik
    python build.py --offline       # użyj plików z raw/ (bez sieci)

Roczniki 2019–2020 są publikowane tylko jako PDF — do ich odczytu
potrzebny jest pdfplumber (python -m pip install pdfplumber).

Wynik:
    data/wykazy-<rok>.json          znormalizowane dane rocznika
    data/index.json                 manifest wszystkich roczników
    site/index.html                 gotowa strona (samodzielna, bez zależności)
"""

import argparse
import base64
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import warnings

warnings.filterwarnings('ignore')

try:
    import openpyxl
except ImportError:
    sys.exit('Brak openpyxl. Zainstaluj:  python -m pip install openpyxl')

try:
    import pdfplumber
except ImportError:
    pdfplumber = None   # roczniki 2019–2020 są tylko w PDF

ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, 'raw')
DATA = os.path.join(ROOT, 'data')
SITE = os.path.join(ROOT, 'site')
TPL = os.path.join(ROOT, 'templates')

BASE = 'https://ursus.um.warszawa.pl'
# Roczniki 2024+ mają adres z prefiksem /-/, starsze bez niego.
PAGES = (BASE + '/-/wykazy-za-rok-{year}', BASE + '/wykazy-za-rok-{year}')
PAGE = PAGES[0]

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# --------------------------------------------------------------------------
# Konfiguracja rejestrów
#   match     – fragment nazwy pliku (albo lista fragmentów), po którym
#               rozpoznajemy załącznik
#   header    – numer wiersza z nagłówkami (1-based, tylko podpowiedź —
#               parser i tak szuka wiersza z „Lp.”)
#   date      – kolumna z datą
#   mode      – 'date' (prawdziwa data) | 'text' (data zaszyta w tekście)
#   cols      – (klucz, kolumna, etykieta, szerokość)
#   pdf_title – oczekiwany tytuł dokumentu PDF (bez polskich znaków);
#               chroni przed podmienionym plikiem w źródle
# --------------------------------------------------------------------------

REGISTERS = [
    dict(
        id='dec_wz', match='rejestr_dec_wz',
        name='Decyzje o warunkach zabudowy', short='Decyzje WZ',
        desc='Decyzje o ustaleniu warunków zabudowy i zagospodarowania terenu.',
        header=4, date=2, mode='text', pdf_title='rejestr wz',
        cols=[('nr', 2, 'Nr decyzji', 'nr'),
              ('inw', 3, 'Rodzaj inwestycji', 'wide'),
              ('wn', 4, 'Wnioskodawca', 'mid'),
              ('nier', 5, 'Nieruchomość', 'mid'),
              ('adr', 6, 'Adres', ''),
              ('roz', 7, 'Rozstrzygnięcie', '')],
    ),
    dict(
        id='dec_pnb', match='rejestr_decyzji_o_pozw_na_bud',
        name='Decyzje o pozwoleniu na budowę', short='Decyzje PnB',
        desc='Pozwolenia na budowę, rozbiórkę oraz decyzje odmowne i umorzenia.',
        header=7, date=2, mode='text', pdf_title='rejestr pnb',
        cols=[('nr', 2, 'Nr decyzji', 'nr'),
              ('inw', 3, 'Rodzaj inwestycji', 'wide'),
              ('wn', 4, 'Wnioskodawca', 'mid'),
              ('nier', 5, 'Nieruchomość', 'mid'),
              ('adr', 6, 'Adres', ''),
              ('rodz', 7, 'Rodzaj decyzji', '')],
    ),
    dict(
        id='dec_lcp', match='rejestr_decyzji_lcp',
        name='Decyzje o lokalizacji inwestycji celu publicznego', short='Decyzje LCP',
        desc='Decyzje o ustaleniu lokalizacji inwestycji celu publicznego.',
        header=2, date=3, mode='text', pdf_title='rejestr decyzji lcp',
        cols=[('nr', 3, 'Nr decyzji', 'nr'),
              ('organ', 2, 'Organ', 'mid'),
              ('wn', 4, 'Wnioskodawca', 'mid'),
              ('inw', 5, 'Rodzaj inwestycji', 'wide'),
              ('roz', 6, 'Rozstrzygnięcie', ''),
              ('teren', 7, 'Teren inwestycji', 'mid')],
    ),
    dict(
        id='dec_zrid', match='rejestr_decyzji_zrid',
        name='Decyzje ZRID', short='Decyzje ZRID',
        desc='Decyzje o zezwoleniu na realizację inwestycji drogowej.',
        header=2, date=3, mode='text', pdf_title='rejestr decyzji zrid',
        cols=[('nr', 3, 'Nr decyzji', 'nr'),
              ('organ', 2, 'Organ', 'mid'),
              ('wn', 4, 'Wnioskodawca', 'mid'),
              ('streszcz', 5, 'Streszczenie ustaleń', 'wide'),
              ('inw', 6, 'Rodzaj inwestycji', 'wide'),
              ('teren', 7, 'Teren inwestycji', 'mid')],
    ),
    dict(
        id='wn_wz', match='rejestr_wnioskow_o_wz',
        name='Wnioski o warunki zabudowy', short='Wnioski WZ',
        desc='Wnioski o ustalenie warunków zabudowy wraz z datą wpływu.',
        header=4, date=2, mode='date', pdf_title='rejestr wnioskow wz',
        cols=[('inw', 3, 'Rodzaj inwestycji', 'wide'),
              ('wn', 4, 'Wnioskodawca', 'mid'),
              ('nier', 5, 'Nieruchomość', 'mid'),
              ('adr', 6, 'Adres', '')],
    ),
    dict(
        id='wn_pnb', match='rejestr_wnioskow_o_pozw_na',
        name='Wnioski o pozwolenie na budowę', short='Wnioski PnB',
        desc='Wnioski o pozwolenie na budowę, rozbiórkę i inne opracowania.',
        header=3, date=2, mode='date', pdf_title='rejestr wnioskow pnb',
        cols=[('inw', 3, 'Rodzaj inwestycji', 'wide'),
              ('wn', 4, 'Wnioskodawca', 'mid'),
              ('nier', 5, 'Nieruchomość', 'mid'),
              ('adr', 6, 'Adres', '')],
    ),
    dict(
        id='wn_lcp', match='rejestr_wnioskow_lcp',
        name='Wnioski o lokalizację inwestycji celu publicznego', short='Wnioski LCP',
        desc='Wnioski o wydanie decyzji o ustaleniu lokalizacji inwestycji celu publicznego.',
        header=2, date=2, mode='date', pdf_title='rejestr wnioskow lcp',
        cols=[('inw', 3, 'Rodzaj inwestycji', 'wide'),
              ('wn', 4, 'Wnioskodawca', 'mid'),
              ('nier', 5, 'Nieruchomość', 'mid'),
              ('adr', 6, 'Adres', '')],
    ),
    dict(
        id='zgl', match='rejestr_zgloszen',
        name='Zgłoszenia robót budowlanych', short='Zgłoszenia RB',
        desc='Zgłoszenia robót budowlanych, rozbiórek i innych prac.',
        header=8, date=2, mode='date', pdf_title='rejestr zgloszen',
        cols=[('inw', 3, 'Rodzaj inwestycji', 'wide'),
              ('wn', 4, 'Wnioskodawca', 'mid'),
              ('nier', 5, 'Nieruchomość', 'mid'),
              ('adr', 6, 'Adres', '')],
    ),
    dict(
        id='umowy16', match=['rejestr_umowyart16', 'art.+16', 'art. 16'],
        name='Umowy z art. 16 ustawy o drogach publicznych', short='Umowy art. 16',
        desc='Umowy z inwestorami o budowę dróg, podpisane na podstawie '
             'art. 16 ustawy o drogach publicznych.',
        header=3, date=4, mode='date', pdf_title=None,
        cols=[('nr', 2, 'Nr umowy', 'nr'),
              ('inwestor', 3, 'Inwestor', 'mid'),
              ('przedmiot', 5, 'Przedmiot umowy', 'wide')],
    ),
]

# --------------------------------------------------------------------------
# Pobieranie
# --------------------------------------------------------------------------


def fetch(url, timeout=90):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept-Language': 'pl-PL,pl;q=0.9,en;q=0.8',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        # CDN m.st. Warszawy odrzuca żądania bez Referer (HTTP 403)
        'Referer': BASE + '/',
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def hub_html(year, offline=False):
    """HTML strony rocznika — pobierany raz, potem czytany z raw/<rok>.html.

    Zwraca (html, url). Roczniki 2024+ mają adres z prefiksem /-/, starsze
    bez niego, więc próbujemy obu wariantów.
    """
    cache = os.path.join(RAW, '%d.html' % year)
    if offline:
        if not os.path.exists(cache):
            raise RuntimeError('brak pliku %s' % os.path.basename(cache))
        with open(cache, encoding='utf-8', errors='replace') as f:
            return f.read(), PAGES[0].format(year=year)

    last = None
    for tpl in PAGES:
        url = tpl.format(year=year)
        try:
            html = fetch(url).decode('utf-8', 'replace')
        except Exception as e:
            last = e
            continue
        os.makedirs(RAW, exist_ok=True)
        with open(cache, 'w', encoding='utf-8') as f:
            f.write(html)
        return html, url
    raise last


def attachments(year, offline=False):
    """Zwraca (lista załączników, url strony rocznika)."""
    html, page_url = hub_html(year, offline=offline)
    out = []
    for m in re.finditer(r'<a\s+href="([^"]+)"[^>]*class="attachment-link"[^>]*>(.*?)</a>',
                         html, re.S):
        url, inner = m.group(1), m.group(2)
        nm = re.search(r'class="attachment-name"[^>]*>(.*?)</span>', inner, re.S)
        label = re.sub(r'<[^>]+>', '', nm.group(1)).strip() if nm else ''
        fname = url.split('/')[-2] if url.count('/') > 3 else url.split('/')[-1]
        fname = urllib.parse.unquote(fname.split('?')[0])
        out.append({'file': fname, 'url': url, 'label': label})
    return out, page_url


def download(url, dest):
    data = fetch(url, timeout=180)
    with open(dest, 'wb') as f:
        f.write(data)
    return len(data)


# --------------------------------------------------------------------------
# Parsowanie
# --------------------------------------------------------------------------

MONTHS_PL = ['stycznia', 'lutego', 'marca', 'kwietnia', 'maja', 'czerwca',
             'lipca', 'sierpnia', 'września', 'października', 'listopada', 'grudnia']

RE_DMY = re.compile(r'(\d{1,2})\s*[.\-/]\s*(\d{2,3})\s*[.\-/]\s*(\d{4})')
RE_YMD = re.compile(r'(\d{4})-(\d{2})-(\d{2})')

# daty zapisane słownie: "23 lutego 2026", "3 luty 2026 r.",
# "30 KWIETNIA2024R." — klucze bez polskich znaków, porównanie przez fold()
MONTH_WORDS = {
    'styczen': 1, 'stycznia': 1,
    'luty': 2, 'lutego': 2,
    'marzec': 3, 'marca': 3,
    'kwiecien': 4, 'kwietnia': 4,
    'maj': 5, 'maja': 5,
    'czerwiec': 6, 'czerwca': 6,
    'lipiec': 7, 'lipca': 7,
    'sierpien': 8, 'sierpnia': 8,
    'wrzesien': 9, 'wrzesnia': 9,
    'pazdziernik': 10, 'pazdziernika': 10,
    'listopad': 11, 'listopada': 11,
    'grudzien': 12, 'grudnia': 12,
}
RE_WORDS = re.compile(r'(\d{1,2})\s+([A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]+)\s*(\d{4})')


def fold(s):
    """Usuwa polskie znaki diakrytyczne — do porównań tekstowych."""
    return (s.replace('ą', 'a').replace('ć', 'c').replace('ę', 'e')
             .replace('ł', 'l').replace('ń', 'n').replace('ó', 'o')
             .replace('ś', 's').replace('ź', 'z').replace('ż', 'z'))


def clean(v):
    if v is None:
        return ''
    # komórki-formaty daty muszą wyjść jako tekst, inaczej json.dump wywala
    # się na "Object of type datetime is not JSON serializable"
    if isinstance(v, dt.datetime):
        return '%02d.%02d.%04d' % (v.day, v.month, v.year)
    if isinstance(v, dt.date):
        return '%02d.%02d.%04d' % (v.day, v.month, v.year)
    s = str(v)
    s = s.replace('\xa0', ' ').replace('\u200b', '')
    s = re.sub(r'[ \t\r\n]+', ' ', s).strip()
    return s


def parse_date(value):
    """Zwraca ISO 'YYYY-MM-DD' albo None."""
    if value is None or value == '':
        return None
    if isinstance(value, dt.datetime):
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    if isinstance(value, (int, float)) and 20000 < float(value) < 80000:
        # numer seryjny Excela
        return (dt.date(1899, 12, 30) + dt.timedelta(days=int(value))).isoformat()

    s = str(value)
    m = RE_YMD.search(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return '%04d-%02d-%02d' % (y, mo, d)

    m = RE_DMY.search(s)
    if m:
        d, mo_raw, y = int(m.group(1)), m.group(2), int(m.group(3))
        mo = int(mo_raw)
        if mo > 12 and len(mo_raw) == 3:   # literówka typu "07.035.2026"
            mo = int(mo_raw[:2])
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return '%04d-%02d-%02d' % (y, mo, d)

    # literówka bez drugiej kropki: "14.062019"
    m = re.search(r'\b(\d{1,2})\.(\d{2})(\d{4})\b', s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return '%04d-%02d-%02d' % (y, mo, d)

    # bardzo tolerancyjny zapis: brak separatora albo podwójny separator,
    # np. "15 .01 2020", "18.06,.2020"
    m = re.search(r'(\d{1,2})\s*[.,/\-]+\s*(\d{1,2})\s*[.,/\-]*\s*(\d{4})', s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return '%04d-%02d-%02d' % (y, mo, d)

    m = RE_WORDS.search(s)
    if m:
        d, word, y = int(m.group(1)), m.group(2).lower(), int(m.group(3))
        mo = MONTH_WORDS.get(fold(word))
        if mo and 1 <= d <= 31:
            return '%04d-%02d-%02d' % (y, mo, d)
    return None


def is_junk_row(cells):
    """Wiersze typu 'Kolumna 1 | Kolumna 2 | ...' albo puste."""
    joined = ' '.join(str(c) for c in cells if c)
    if not joined.strip():
        return True
    if re.match(r'^(Kolumna\s*\d+\s*)+$', joined.strip(), re.I):
        return True
    return False


RE_LP = re.compile(r'^l\s*\.?\s*p\s*\.?$', re.I)
RE_LP_VALUE = re.compile(r'^\d+\.?$')


def detect_header(ws, hint):
    """Wiersz nagłówka = pierwszy, w którym kolumna A zawiera 'Lp.'/'LP.'.

    Urząd zmienia układ arkuszy między rocznikami (np. rejestr decyzji PnB
    ma nagłówek w wierszu 6 w 2024/2025, a w 7 w 2026), więc szukamy go
    po zawartości, a nie po stałym numerze. `hint` to wartość zapasowa.
    """
    for r in range(1, min(20, ws.max_row + 1)):
        v = ws.cell(row=r, column=1).value
        if v is not None and RE_LP.match(str(v).strip()):
            return r
    return hint


def parse_register_xlsx(cfg, path, year):
    wb = openpyxl.load_workbook(path, data_only=True, read_only=False)
    ws = wb.worksheets[0]

    header = detect_header(ws, cfg['header'])

    rows = []
    for r in range(header + 1, ws.max_row + 1):
        raw = [ws.cell(row=r, column=c).value for c in range(1, ws.max_column + 1)]
        if is_junk_row(raw):
            continue

        lp = clean(raw[0]) if raw else ''
        if not RE_LP_VALUE.match(str(lp).strip()):
            continue

        date_val = raw[cfg['date'] - 1] if len(raw) >= cfg['date'] else None
        iso = parse_date(date_val)

        cells = {}
        for key, col, _label, _w in cfg['cols']:
            v = raw[col - 1] if len(raw) >= col else None
            v = clean(v)
            if isinstance(v, str):
                v = v.strip(' ,;')
            cells[key] = v

        # wiersze-szkielety: urząd numeruje wiersze i wpisuje z góry nazwę
        # organu, a resztę zostawia pustą. Taki wiersz ma wypełnioną tylko
        # jedną kolumnę — odrzucamy go, żeby nie tworzyć pustych pozycji.
        if sum(1 for v in cells.values() if v) < 2:
            continue

        rows.append({'d': iso, 'c': cells})

    wb.close()

    # sortowanie: daty rosnąco, bez daty na końcu
    rows.sort(key=lambda x: (x['d'] is None, x['d'] or '9999-99-99'))
    return rows


# --------------------------------------------------------------------------
# PDF — roczniki 2019–2020 urząd publikował wyłącznie w PDF
# --------------------------------------------------------------------------


# PDF-y 2019–2020 mają kolumnę "Wnioskodawca" tak wąską, że "osoba fizyczna"
# skleja się w jedno słowo (88 wystąpień w dwóch rocznikach). Reszta sklejeń
# jest zbyt niejednoznaczna, żeby je automatycznie rozdzielać.
PDF_GLUED = [
    (re.compile(r'\bosobafizyczn\w*', re.I), 'osoba fizyczna'),
]


def clean_pdf(v):
    if v is None:
        return ''
    s = str(v).replace('\xa0', ' ')
    s = re.sub(r'\s+', ' ', s).strip()
    for pat, rep in PDF_GLUED:
        s = pat.sub(rep, s)
    return s


def pdf_title(path):
    """Tytuł dokumentu — pierwsza niepusta komórka pierwszej tabeli."""
    with pdfplumber.open(path) as pdf:
        table = pdf.pages[0].extract_table()
    if not table:
        return ''
    for row in table[:3]:
        for c in row:
            if c and c.strip():
                return clean_pdf(c)
    return ''


def parse_register_pdf(cfg, path, year):
    if pdfplumber is None:
        print('    ! brak pdfplumber — pomijam %s' % os.path.basename(path))
        return []

    want = cfg.get('pdf_title')
    if want:
        got = fold(pdf_title(path).lower())
        if want not in got:
            print('    ! zły dokument w źródle: %r zamiast %r — pomijam'
                  % (got[:44], want))
            return []

    rows = []
    started = False
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            table = page.extract_table()
            if not table:
                continue
            for raw in table:
                cells_raw = [clean_pdf(c) for c in raw]
                filled = [c for c in cells_raw if c]
                if not filled:
                    continue

                # wiersz z numeracją kolumn: "1 2 3 4 5 6"
                if all(re.fullmatch(r'\d{1,2}', c) for c in filled):
                    continue

                date_raw = (cells_raw[cfg['date'] - 1]
                            if len(cells_raw) >= cfg['date'] else '')
                iso = parse_date(date_raw) if date_raw else None
                if iso and int(iso[:4]) < 2000:
                    iso = None      # numeracja kolumn odczytana jako data

                if not started:
                    # nagłówek bywa wielowierszowy — zaczynamy dopiero od
                    # pierwszego wiersza z prawdziwą datą
                    if not iso:
                        continue
                    started = True

                cells = {}
                for key, col, _label, _w in cfg['cols']:
                    v = cells_raw[col - 1] if len(cells_raw) >= col else ''
                    cells[key] = v.strip(' ,;')

                if sum(1 for v in cells.values() if v) < 2:
                    continue

                rows.append({'d': iso, 'c': cells})

    rows.sort(key=lambda x: (x['d'] is None, x['d'] or '9999-99-99'))
    return rows


def parse_register(cfg, path, year):
    if path.lower().endswith('.pdf'):
        return parse_register_pdf(cfg, path, year)
    return parse_register_xlsx(cfg, path, year)


def matches(cfg, fname):
    pats = cfg['match']
    if isinstance(pats, str):
        pats = [pats]
    return any(p in fname for p in pats)


# --------------------------------------------------------------------------
# Budowa danych
# --------------------------------------------------------------------------


def build_data(year, offline=False):
    os.makedirs(RAW, exist_ok=True)
    os.makedirs(DATA, exist_ok=True)

    atts = []
    source_url = PAGES[0].format(year=year)
    try:
        atts, source_url = attachments(year, offline=offline)
        print('  znaleziono %d załączników na stronie' % len(atts))
    except Exception as e:
        print('  ! nie udało się pobrać strony: %s' % e)
        print('  -> korzystam z plików w raw/')

    registers = []
    for cfg in REGISTERS:
        att = next((a for a in atts if matches(cfg, a['file'])), None)

        if att:
            dest = os.path.join(RAW, att['file'])
            if offline:
                if not os.path.exists(dest):
                    print('  - pominięto %s (brak w cache)' % cfg['id'])
                    continue
                print('  ~ %-46s (cache)' % att['file'])
            else:
                try:
                    size = download(att['url'], dest)
                    print('  + %-46s %7d B' % (att['file'], size))
                except Exception as e:
                    print('  ! pobieranie %s: %s' % (att['file'], e))
                    if not os.path.exists(dest):
                        continue
        else:
            # szukamy w cache — tylko pliki z właściwego rocznika
            cand = [f for f in os.listdir(RAW)
                    if matches(cfg, f) and f.lower().endswith(('.xlsx', '.pdf'))
                    and str(year) in f]
            if not cand:
                print('  - pominięto %s (brak pliku)' % cfg['id'])
                continue
            dest = os.path.join(RAW, sorted(cand)[0])
            print('  ~ %-46s (cache)' % os.path.basename(dest))

        try:
            rows = parse_register(cfg, dest, year)
        except Exception as e:
            print('  ! parsowanie %s: %s' % (cfg['id'], e))
            continue

        if not rows:
            print('  - pominięto %s (brak pozycji)' % cfg['id'])
            continue

        no_date = sum(1 for r in rows if not r['d'])
        print('    -> %3d pozycji%s' % (len(rows), ' (%d bez daty)' % no_date if no_date else ''))

        registers.append({
            'id': cfg['id'],
            'name': cfg['name'],
            'short': cfg['short'],
            'desc': cfg['desc'],
            'file': os.path.basename(dest),
            'url': att['url'] if att else '',
            'cols': [{'k': k, 'l': l, 'w': w} for k, _c, l, w in cfg['cols']],
            'rows': rows,
        })

    total = sum(len(r['rows']) for r in registers)
    data = {
        'year': year,
        'source': source_url,
        'generated': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
        'total': total,
        'registers': registers,
    }
    return data


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------


def read(path):
    with open(path, encoding='utf-8') as f:
        return f.read()


def wrap_json(s):
    """Wstawia znak nowej linii po każdym `}` i `]` poza literałem tekstowym.

    Bez tego cała paczka danych (ponad 1 MB) ląduje w jednej linii pliku HTML:
    git nie potrafi wtedy pokazać sensownego diffu, a narzędzia czytające plik
    po liniach gubią zawartość. Nowe linie są wewnątrz JSON-a, więc dla
    przeglądarki nic się nie zmienia.
    """
    out = []
    in_str = False
    esc = False
    for ch in s:
        out.append(ch)
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch in '}]':
            out.append('\n')
    return ''.join(out)


def render(bundle):
    os.makedirs(SITE, exist_ok=True)

    tpl = read(os.path.join(TPL, 'index.html'))
    css = read(os.path.join(TPL, 'style.css'))
    js = read(os.path.join(TPL, 'app.js'))

    # osadzone fonty (base64 w data URI) doklejamy przed stylem —
    # strona zostaje jednym plikiem, bez CDN.
    fonts_css = os.path.join(TPL, 'fonts.css')
    if os.path.exists(fonts_css):
        css = read(fonts_css) + '\n' + css

    # logo wklejamy jako data URI — strona zostaje jednym plikiem.
    # Źródłem jest PNG; jeśli go nie ma (np. w repozytorium, gdzie pliki
    # binarne idą przez kanał tekstowy), bierzemy zapis base64 z .b64.
    logo_png = os.path.join(TPL, 'logo-bizu.png')
    logo_b64 = os.path.join(TPL, 'logo-bizu.b64')
    logo_uri = ''
    if os.path.exists(logo_png):
        with open(logo_png, 'rb') as f:
            logo_uri = ('data:image/png;base64,'
                        + base64.b64encode(f.read()).decode('ascii'))
    elif os.path.exists(logo_b64):
        with open(logo_b64, encoding='ascii') as f:
            logo_uri = 'data:image/png;base64,' + f.read().strip()

    payload = json.dumps(bundle, ensure_ascii=False, separators=(',', ':'))
    payload = payload.replace('</', '<\\/')
    payload = wrap_json(payload)

    years = bundle['years']
    default = bundle['default']
    total = sum(bundle['data'][str(y)]['total'] for y in years)

    gen = dt.datetime.fromisoformat(bundle['generated'])
    updated = '%d %s %d, %s' % (gen.day, MONTHS_PL[gen.month - 1], gen.year,
                                gen.strftime('%H:%M'))

    if len(years) == 1:
        span = str(default)
        title = 'Wykazy i rejestry %d — Dzielnica Ursus' % default
    else:
        span = '%d–%d' % (years[0], years[-1])
        title = 'Wykazy i rejestry %d–%d — Dzielnica Ursus' % (years[0], years[-1])

    desc = ('Decyzje i wnioski z zakresu zagospodarowania przestrzennego i procesu '
            'budowlanego w Dzielnicy Ursus — %d pozycji w układzie miesięcznym, '
            'roczniki %s.' % (total, span))

    html = (tpl
            .replace('__STYLE__', css)
            .replace('__SCRIPT__', js)
            .replace('__DATA__', payload)
            .replace('__TITLE__', title)
            .replace('__DESCRIPTION__', desc)
            .replace('__YEAR__', str(default))
            .replace('__YEARS__', span)
            .replace('__SOURCE__', bundle['data'][str(default)]['source'])
            .replace('__COUNT__', str(total))
            .replace('__UPDATED__', updated)
            .replace('__LOGO__', logo_uri))

    out = os.path.join(SITE, 'index.html')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)

    size = os.path.getsize(out)
    print('\n  -> %s  (%.0f kB)' % (os.path.relpath(out, ROOT), size / 1024))
    return out


# --------------------------------------------------------------------------


def parse_years(spec):
    out = []
    for part in str(spec).split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            out.extend(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return sorted(set(out))


def render_only(years):
    """Przebudowuje HTML z plików data/wykazy-*.json, bez ruszania źródeł.

    Przydaje się przy pracy nad szablonem: pełny build ośmiu roczników
    trwa kilka minut (PDF-y 2019–2020), a samo renderowanie — sekundy.
    """
    bundle = {'years': [], 'default': None, 'data': {}}
    for y in years:
        path = os.path.join(DATA, 'wykazy-%d.json' % y)
        if not os.path.exists(path):
            print('  ! brak %s — pomijam' % os.path.relpath(path, ROOT))
            continue
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        bundle['years'].append(y)
        bundle['data'][str(y)] = data
        print('  %d: %d pozycji' % (y, data['total']))

    if not bundle['years']:
        sys.exit('\nBrak plików w data/ — uruchom pełny build.')

    bundle['default'] = bundle['years'][-1]
    bundle['generated'] = dt.datetime.now().astimezone().isoformat(timespec='seconds')
    render(bundle)


def main():
    ap = argparse.ArgumentParser(description='Generator strony z wykazami Ursus')
    ap.add_argument('--year', type=int, help='pojedynczy rocznik')
    ap.add_argument('--years', help='lista roczników, np. 2024,2025,2026 albo 2024-2026')
    ap.add_argument('--all', action='store_true',
                    help='wszystkie roczniki od 2019 do bieżącego')
    ap.add_argument('--offline', action='store_true', help='nie pobieraj, użyj cache')
    ap.add_argument('--render-only', action='store_true',
                    help='tylko przebuduj HTML z gotowych data/wykazy-*.json '
                         '(bez pobierania i parsowania — sekundy zamiast minut)')
    args = ap.parse_args()

    this_year = dt.date.today().year
    if args.years:
        years = parse_years(args.years)
    elif args.year:
        years = [args.year]
    elif args.all:
        years = list(range(2019, this_year + 1))
    else:
        years = [this_year]

    print('Wykazy Ursus — roczniki: %s' % ', '.join(str(y) for y in years))
    print('-' * 62)

    if args.render_only:
        render_only(years)
        return

    os.makedirs(DATA, exist_ok=True)

    bundle = {'years': [], 'default': years[-1], 'data': {}}
    manifest = {'generated': None, 'default': years[-1], 'years': []}

    for y in years:
        print('\n[%d]' % y)
        try:
            data = build_data(y, offline=args.offline)
        except Exception as e:
            print('  ! rocznik %d pominięty: %s' % (y, e))
            continue

        if not data['registers']:
            print('  ! brak danych — rocznik pominięty')
            continue

        jpath = os.path.join(DATA, 'wykazy-%d.json' % y)
        with open(jpath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print('  -> %s' % os.path.relpath(jpath, ROOT))
        print('  razem: %d pozycji w %d rejestrach' % (data['total'], len(data['registers'])))

        bundle['years'].append(y)
        bundle['data'][str(y)] = data
        manifest['years'].append({
            'year': y,
            'total': data['total'],
            'registers': len(data['registers']),
            'generated': data['generated'],
            'source': data['source'],
            'file': 'wykazy-%d.json' % y,
        })

    if not bundle['years']:
        sys.exit('\nBrak danych — przerywam.')

    bundle['generated'] = dt.datetime.now().astimezone().isoformat(timespec='seconds')
    manifest['generated'] = bundle['generated']

    mpath = os.path.join(DATA, 'index.json')
    with open(mpath, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print('\n  -> %s' % os.path.relpath(mpath, ROOT))

    grand = sum(bundle['data'][str(y)]['total'] for y in bundle['years'])
    print('\n  RAZEM: %d pozycji w %d rocznikach' % (grand, len(bundle['years'])))
    render(bundle)


if __name__ == '__main__':
    main()
