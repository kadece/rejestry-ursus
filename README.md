# Wykazy Ursus

Strona prezentująca rejestry decyzji i wniosków z Dzielnicy Ursus
(m.st. Warszawa) w układzie miesięcznym — dla **ośmiu roczników:
2019–2026**, z przełącznikiem roku w nagłówku.

Dane pochodzą z oficjalnych stron
[ursus.um.warszawa.pl/-/wykazy-za-rok-2026](https://ursus.um.warszawa.pl/-/wykazy-za-rok-2026)
(i analogicznych dla lat poprzednich), gdzie urząd publikuje pliki XLSX —
a dla roczników 2019–2020 wyłącznie PDF-y. Skrypt pobiera je, wyciąga daty
i buduje jedną samodzielną stronę HTML — bez bazy danych, bez zależności
frontendowych, bez CDN.

W prawym górnym rogu nagłówka jest logo **BiZU — Bezpieczny i Zielony
Ursus** ([zielonyursus.pl](https://zielonyursus.pl)), wtopione w plik jako
data URI, więc strona dalej jest jednym plikiem.

---

## Szybki start

```bash
python -m pip install openpyxl pdfplumber
python build.py --all           # 2019 … 2026
python build.py --years 2024-2026
python build.py --year 2026     # pojedynczy rocznik
python build.py --all --offline # bez sieci, z plików w raw/
python build.py --all --render-only  # tylko HTML z gotowych data/*.json
```

`pdfplumber` jest potrzebny tylko dla roczników 2019–2020 (PDF). Bez niego
build przejdzie, ale te dwa lata zostaną pominięte z ostrzeżeniem.

Wynik:

| Plik | Co to jest |
|---|---|
| `site/index.html` | gotowa strona (~1,1 MB, wszystko w środku) |
| `data/wykazy-<rok>.json` | znormalizowane dane rocznika (do dalszego użycia) |
| `data/index.json` | manifest wszystkich roczników (rok, liczba pozycji, źródło) |
| `raw/*.xlsx`, `raw/*.pdf` | pobrane pliki źródłowe (cache) |
| `raw/<rok>.html` | zapisana strona rocznika (żeby `--offline` znał adresy plików) |

Otwórz `site/index.html` w przeglądarce — działa też z dysku, bez serwera.

---

## Co jest na stronie

**Przełącznik roczników** — pigułki `2019 … 2026` w nagłówku, każda
z liczbą pozycji. Zmiana roku przebudowuje cały widok, zachowując wybrany
miesiąc, więc październik 2019 i październik 2026 porównuje się jednym
kliknięciem. Stan siedzi w adresie (`?y=2019`), więc link da się wysłać dalej.

**Przegląd roku** — macierz „rejestr × miesiąc” z liczbą pozycji. Kolor
komórki odpowiada liczbie wpisów, kliknięcie przenosi do konkretnego
miesiąca i rejestru. Pod spodem tabela z zakresem dat i linkami do
plików źródłowych oraz tabela **Roczniki** z porównaniem lat.

**Widok miesiąca** — dla wybranego miesiąca osobna tabela na każdy
rejestr, z numerem decyzji, wnioskodawcą, nieruchomością, adresem
i rozstrzygnięciem. Rozstrzygnięcia mają kolorowe znaczniki
(`ustalam` zielony, `odmawiam` czerwony, `umorzenie` szary,
`przeniesienie` niebieski).

**Dodatki** — wyszukiwanie po całym roku (ulica, wnioskodawca, numer
sprawy), eksport CSV per rejestr, widok do druku, obsługa klawiszy
← →, wersja mobilna.

**Parametry URL** — `?y=2025` wybiera rocznik, `?m=10` otwiera
październik, `?view=overview` przegląd, `?q=Bodycha` wyszukiwanie,
`?embed=1` ukrywa nagłówek (do osadzenia w iframe — przełącznik
roczników zostaje widoczny).

---

## Roczniki — co się różni

Urząd nie prowadzi rejestrów według jednego szablonu, a przez osiem lat
zmieniał zarówno format plików, jak i zestaw rejestrów.

| Rok | Format | Rejestrów | Pozycji | Uwagi |
|---|---|---|---|---|
| 2019 | PDF | 6 | 766 | brak rejestru wniosków LCP (zob. niżej) |
| 2020 | PDF | 7 | 614 | |
| 2021 | XLSX | 7 | 536 | |
| 2022 | XLSX | 7 | 611 | ostatni rok z rejestrem umów art. 16 |
| 2023 | XLSX | 6 | 563 | |
| 2024 | XLSX | 6 | 449 | rejestr decyzji WZ niekompletny w źródle (34 wpisy) |
| 2025 | XLSX | 7 | 549 | pierwszy rok z decyzjami LCP |
| 2026 | XLSX | 8 | 470 | pierwszy rok z decyzjami ZRID |
| **razem** | | | **4558** | |

Rejestry w konfiguracji `REGISTERS` (9 sztuk, w nawiasach lata, w których
występują):

| id | nazwa | lata |
|---|---|---|
| `dec_wz` | Decyzje o warunkach zabudowy | 2019–2026 |
| `dec_pnb` | Decyzje o pozwoleniu na budowę | 2019–2026 |
| `dec_lcp` | Decyzje o lokalizacji inwestycji celu publicznego | 2025–2026 |
| `dec_zrid` | Decyzje ZRID | 2026 |
| `wn_wz` | Wnioski o warunki zabudowy | 2019–2026 |
| `wn_pnb` | Wnioski o pozwolenie na budowę | 2019–2026 |
| `wn_lcp` | Wnioski o lokalizację inwestycji celu publicznego | 2020–2026 |
| `zgl` | Zgłoszenia robót budowlanych | 2019–2026 |
| `umowy16` | Umowy z art. 16 ustawy o drogach publicznych | 2019–2022 |

**Brakujący rejestr** w danym roczniku to nie błąd — po prostu nie ma go
na stronie urzędu i nie pojawia się na stronie.

**Nagłówek arkusza** nie jest zaszyty na sztywno — parser szuka pierwszego
wiersza, w którym kolumna A zawiera `Lp.`/`LP.`. To konieczne, bo np.
rejestr decyzji PnB ma nagłówek w wierszu 6 w latach 2024–2025, a w 7
w 2026. Numer w konfiguracji `REGISTERS` został jako wartość zapasowa.

### Dwie pułapki w danych źródłowych

**Rok 2019 — zły plik pod linkiem.** Urząd podpisał
`rejestr_wnioskow_lcp_2019.pdf` jako rejestr wniosków LCP, ale w środku
jest **rejestr zgłoszeń** (tytuł dokumentu: „REJESTR zgłoszeń”). Parser
sprawdza tytuł pierwszej tabeli (`pdf_title` w `REGISTERS`) i zamiast
opublikować cudze dane, pomija rejestr z ostrzeżeniem. Dzięki temu
zgłoszenia z 2019 nie są liczone dwa razy.

**Rok 2024 — niekompletny rejestr decyzji WZ.** Arkusz
`rejestr_dec_wz_2024.xlsx` ma 123 ponumerowane wiersze, ale wypełnionych
jest tylko 35 — w pozostałych latach ten sam plik ma ich ponad 110.
To stan źródła, nie parsera; strona pokazuje 34 pozycje, bo tyle jest
w pliku.

---

## Jak działa parser

Każdy rejestr ma inny układ — nagłówek w wierszu 2, 3, 4, 6, 7 albo 8,
a data bywa prawdziwą datą albo tekstem w rodzaju
`79/URS/WZ/2026/O z 21.10.2026`. Konfiguracja siedzi w tablicy
`REGISTERS` w `build.py`; wystarczy wskazać kolumnę z datą i tryb
(`date` / `text`).

Parser dat obsługuje:

- prawdziwe daty Excela i numery seryjne,
- `21.10.2026`, `6.05.2026`, `2026-01-02`,
- daty słowne: `23 lutego 2026`, `3 luty 2026 r.`,
- daty słowne bez spacji i wielkimi literami: `30 KWIETNIA2024R.`,
- literówki: `07.035.2026` → `2026-03-07`, `14.062019`, `15 .01 2020`.

Nazwy miesięcy są porównywane po usunięciu polskich znaków (`fold()`),
więc `września`, `wrzesnia` i `WRZEŚNIA` trafiają w ten sam klucz.

Wiersze-śmieci (`Kolumna 1 | Kolumna 2 | …`) i puste są odrzucane.
Odrzucane są też **wiersze-szkielety**: urząd numeruje wiersze i wpisuje
z góry nazwę organu, a resztę zostawia pustą — taki wiersz ma wypełnioną
tylko jedną kolumnę i nie tworzy pozycji (w rejestrze LCP 2025 było
14 takich wierszy).

Pozycje bez daty (`XX.07.2026`) trafiają do zakładki **bez daty** —
nie są ukrywane. Daty spoza rocznika (w rejestrze 2026 zdarza się
`11.02.2025`) są pokazywane z bursztynowym podkreśleniem i podpowiedzią,
bo to omyłka w pliku źródłowym, a nie w parserze.

Skuteczność na danych 2019–2026: **4518 z 4558 pozycji** ma datę
(99,1%); pozostałe 40 naprawdę nie ma jej w źródle.

### Roczniki PDF (2019–2020)

Dla 2019 i 2020 urząd publikował wyłącznie PDF-y (po 7 załączników).
Nie są to skany — tekst da się wyciągnąć, więc parser czyta je przez
`pdfplumber.extract_table()`. Reguły, które musiały dojść:

- pomijanie wiersza z numeracją kolumn (`1 2 3 4 5 6`),
- pomijanie wszystkiego przed pierwszym wierszem z poprawną datą ≥ 2000
  (tabele mają wielowierszowe nagłówki rozbite na kilka wierszy),
- wymóg co najmniej 2 wypełnionych komórek w konfiguracji,
- sklejanie `osobafizyczna` → `osoba fizyczna` (kolumna wnioskodawcy jest
  tak wąska, że wyrażenie się zlepia — 88 wystąpień w dwóch rocznikach).

Liczby z PDF-ów zostały niezależnie przeliczone skryptem kontrolnym
i zgadzają się co do wiersza.

---

## Automatyczna aktualizacja

### Wariant 1 — GitHub Actions (zalecany, darmowy)

Workflow `.github/workflows/update.yml` uruchamia się **1. i 15. dnia
miesiąca o 6:00 UTC**, pobiera świeże pliki dla wszystkich roczników,
przebudowuje stronę, commituje zmiany i publikuje na GitHub Pages.

```bash
git init && git add . && git commit -m "Wykazy Ursus"
git remote add origin https://github.com/UZYTKOWNIK/wykazy-ursus.git
git push -u origin main
```

Potem w repozytorium: **Settings → Pages → Source: GitHub Actions**.
Strona będzie pod `https://UZYTKOWNIK.github.io/wykazy-ursus/`.

Dwa przebiegi w miesiącu, bo urząd uzupełnia rejestry z opóźnieniem —
jeden przebieg mógłby trwale pomijać wpisy dodane po 1. dniu.
Częstotliwość zmienisz w linii `cron:`.

### Wariant 2 — Harmonogram zadań Windows

```powershell
.\update.ps1 -RegisterTask          # rejestruje zadanie (poniedziałki 6:00)
.\update.ps1                        # jednorazowa aktualizacja (wszystkie roczniki)
.\update.ps1 -Years '2024-2026'     # wybrane roczniki
.\update.ps1 -Deploy 'C:\hosting\wykazy'   # + kopia na serwer
```

Logi lądują w `logs/update-RRRR-MM.log`.

### Wariant 3 — cron na własnym serwerze

```cron
0 6 1,15 * * cd /var/www/wykazy-ursus && /usr/bin/python3 build.py --all >> logs/cron.log 2>&1
```

---

## Osadzenie na WordPressie

Pełna instrukcja: **`WORDPRESS.md`**. Skrót — trzy warianty, od najprostszego.

### A. GitHub Pages + iframe — polecane

Workflow publikuje stronę na GitHub Pages, a WordPress dostaje tylko
`<iframe>`. Aktualizacje dzieją się same, nic nie trzeba wgrywać na
hosting. Gotowy snippet: **`wordpress-embed.html`**.

### B. Plik na własnej domenie (FTP)

`site/index.html` ląduje w `public_html/wykazy/index.html` i jest
osadzany tą samą ramką. Biblioteka mediów WordPressa nie przyjmie
`.html`, dlatego zwykły katalog, a nie `wp-content/uploads`.

### C. Natywny shortcode

`wordpress-shortcode.php` daje `[wykazy_ursus]` (iframe) oraz
`[wykazy_ursus_tabela rok="2026"]` — tabele renderowane po stronie PHP
z plików `data/wykazy-*.json`. Treść indeksuje się w Google i dziedziczy
styl motywu, ale nie ma przełącznika roczników ani widoku miesięcznego.

### Uwaga o cache

Jeśli trzymasz plik na serwerze, ustaw krótki cache albo dodawaj
parametr wersji (`?v=2026-11`), inaczej przeglądarki i CDN pokażą
stare dane po aktualizacji.

---

## Dodanie kolejnego rocznika

Architektura jest na to gotowa — wystarczy rozszerzyć zakres lat.

1. Sprawdź, czy strona rocznika istnieje:
   `https://ursus.um.warszawa.pl/-/wykazy-za-rok-2027`.
2. `python build.py --years 2024-2027` — nowy rocznik dojdzie do
   `data/`, manifestu i przełącznika.
3. Jeśli w nowym roczniku pojawi się **nowy rejestr**, dopisz wpis do
   `REGISTERS` w `build.py` z fragmentem nazwy pliku w `match`.
4. Jeśli urząd zmieni **kolumny** w istniejącym rejestrze, popraw
   `cols` i `date` w `REGISTERS`.

W workflow i w `update.ps1` nie ma nic do zmiany — `--all` bierze
wszystko od 2019 do bieżącego roku.

**Adresy stron rocznikowych nie są jednolite.** 2024 i późniejsze
działają pod `/-/wykazy-za-rok-<rok>`, a 2019–2023 pod
`/wykazy-za-rok-<rok>` (bez `/-/`). `build.py` próbuje obu wariantów
i zapamiętuje ten, który odpowiedział.

---

## Struktura

```
wykazy-ursus/
├── build.py                  # pobieranie + parsowanie + render
├── update.ps1                # aktualizacja / zadanie w Harmonogramie
├── WORDPRESS.md              # instrukcja publikacji na zielonyursus.pl
├── wordpress-embed.html      # snippet z iframe
├── wordpress-shortcode.php   # shortcode [wykazy_ursus] / [wykazy_ursus_tabela]
├── templates/
│   ├── index.html            # szkielet strony
│   ├── style.css             # wygląd
│   ├── app.js                # logika widoku (roczniki, miesiące, szukanie)
│   └── logo-bizu.png         # logo BiZU (212×192, wbudowywane jako data URI)
├── data/
│   ├── wykazy-2019.json      # dane rocznika
│   ├── …
│   ├── wykazy-2026.json
│   └── index.json            # manifest roczników
├── raw/*.xlsx, raw/*.pdf     # pliki źródłowe (cache)
├── raw/<rok>.html            # zapisane strony roczników
├── site/index.html           # wynik — to publikujesz
└── .github/workflows/update.yml
```

---

## Rozwiązywanie problemów

**„Brak danych — przerywam.”** — żaden rocznik nie zwrócił danych.
Sprawdź, czy adresy roczników istnieją, i uruchom `--offline`, jeśli masz
pliki w `raw/`.

**HTTP 403 przy pobieraniu plików** — CDN m.st. Warszawy wymaga nagłówka
`Referer`. `fetch()` w `build.py` wysyła go zawsze; jeśli podmieniasz
pobieranie na własne, nie zapomnij o tym nagłówku.

**`ModuleNotFoundError: pdfplumber`** — brak zależności dla roczników
2019–2020. `python -m pip install pdfplumber`. Build bez niej nie pada,
tylko pomija te dwa lata.

**Puste tabele** — urząd zmienił układ arkusza. Popraw `date`
i numery kolumn w `REGISTERS` w `build.py`. Numer wiersza nagłówka
zwykle nie wymaga zmiany (jest wykrywany automatycznie).

**Nowy rejestr w źródle** — dodaj wpis do `REGISTERS` z pasującym
fragmentem nazwy pliku w `match`.

**Rejestr pojawia się w złym roczniku** — sprawdź `match`: musi być
unikalny i nie może pasować do plików z innych lat. Cache w `raw/`
jest filtrowany po roku w nazwie pliku.

**Rejestr PDF ma za mało pozycji** — sprawdź `pdf_title` w `REGISTERS`.
Jeśli tytuł pierwszej tabeli nie zgadza się z oczekiwanym, parser uznaje,
że urząd podlinkował niewłaściwy dokument, i pomija rejestr (tak jest
z wnioskami LCP w 2019).

**Strona nie odświeża się na WordPressie** — cache. Podmień plik
i dodaj `?v=RRRR-MM` do adresu w iframe.

**`update.ps1` nie startuje / dziwne znaki** — plik musi być zapisany
jako UTF-8 **z BOM**. PowerShell 5.1 czyta skrypty bez BOM jako ANSI
i polskie znaki rozsypują się, a czasem kończy się to błędem parsowania.
