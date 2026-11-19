# Aktualizacja wykazów Ursus — instrukcja dla agenta Vibe CLI

Ten plik jest przeznaczony dla **instancji Vibe CLI na serwerze lokalnym**, która
ma co dwa tygodnie odświeżać dane i publikować zmiany na GitHubie.

Wszystko, czego agent potrzebuje, jest w tym pliku plus w `PROMPT-aktualizacja.txt`
(gotowy prompt do wklejenia) i `update.sh` (skrypt, który robi całą robotę).

---

## 1. Co robi aktualizacja

```
ursus.um.warszawa.pl  →  raw/*.pdf, raw/*.xlsx  →  data/*.json  →  site/index.html  →  git push
     (pobranie)              (parsowanie)          (render)         (GitHub Pages)
```

| Krok | Odpowiada za to | Czas |
|---|---|---|
| Pobranie PDF/XLSX ze strony dzielnicy | `build.py --all` | ~2 min |
| Parsowanie tabel do JSON | `build.py --all` | ~1,5 min |
| Render `site/index.html` | `build.py --all` | ~10 s |
| Commit + push | `update.sh` | ~5 s |

Pełny przebieg: **około 4 minuty**. Katalog `raw/` (9 MB PDF-ów) jest w
`.gitignore` — pobiera się od nowa przy każdym przebiegu.

---

## 2. Wymagania na serwerze

```bash
# Python 3.10+ i biblioteki
python3 -m pip install openpyxl pdfplumber

# git + tożsamość (bez tego commit się nie uda)
git config --global user.name  "Rejestry Ursus Bot"
git config --global user.email "bot@example.com"

# Vibe CLI
uv tool install mistral-vibe
```

**Klucz API** — w `~/.vibe/.env` musi być linia `MISTRAL_API_KEY=...`.
Nie czytaj i nie wypisuj tego pliku, tylko sprawdź, czy istnieje.

**Dostęp do GitHuba** — jedno z dwóch:

- *PAT (prostsze)*: fine-grained token z uprawnieniem **Contents: Read and write**
  na repo `kadece/rejestry-ursus`, zapisany przez
  `git config --global credential.helper store` i jednorazowy `git push`.
- *Klucz SSH*: `ssh-keygen -t ed25519`, klucz publiczny dodany jako **Deploy key**
  z prawem zapisu w Settings → Deploy keys, remote ustawiony na `git@github.com:...`.

**Ważne:** serwer musi mieć dostęp do `ursus.um.warszawa.pl`. Jeśli ta strona
blokuje adresy z centrów danych (tak robią runnery GitHub Actions — patrz
`build.log`), build padnie także tutaj. Sprawdź to raz ręcznie:

```bash
curl -sI https://ursus.um.warszawa.pl/wykazy-za-rok-2026 | head -1
# oczekiwane: HTTP/2 200
```

---

## 3. Pierwsze uruchomienie (jednorazowo)

```bash
git clone https://github.com/kadece/rejestry-ursus.git /srv/rejestry-ursus
cd /srv/rejestry-ursus
chmod +x update.sh

# próba na sucho — pobiera, buduje, pokazuje diff, ale NIE commituje
./update.sh --dry-run
```

Oczekiwany koniec wyjścia:

```
   pozycji: 4558 w 8 rocznikach
== --dry-run: zmiany przygotowane, ale nie commitowane ==
```

Jeśli `pozycji:` jest mniejsze niż 4500 albo roczników mniej niż 8 — **nie
commituj**, tylko czytaj `build.log`.

---

## 4. Ręczna aktualizacja

```bash
cd /srv/rejestry-ursus
./update.sh
```

Kody wyjścia:

| Kod | Znaczenie | Co robić |
|---|---|---|
| `0` | sukces albo „bez zmian” | nic |
| `1` | build padł całkowicie | czytaj `build.log` |
| `2` | wynik poniżej progu jakości | czytaj `build.log`, sprawdź, który rocznik |

---

## 5. Harmonogram co dwa tygodnie

### Wariant A — cron systemowy + `vibe -p` (zalecany na serwer)

`vibe -p` to tryb jednorazowy: uruchamia się, wykonuje zadanie, kończy. Nie
zostawia otwartej sesji, więc przeżyje restart maszyny.

```bash
crontab -e
```

```cron
SHELL=/bin/bash
PATH=/usr/local/bin:/usr/bin:/bin:/home/vibe/.local/bin

# 1. i 15. dnia miesiąca o 6:00
0 6 1,15 * * cd /srv/rejestry-ursus && vibe -p "$(cat PROMPT-aktualizacja.txt)" --auto-approve --trust --max-turns 40 --max-price 2 >> /var/log/rejestry-ursus.log 2>&1
```

Dlaczego te flagi:

| Flaga | Po co |
|---|---|
| `-p "$(cat ...)"` | tryb jednorazowy z promptem z pliku |
| `--auto-approve` | w `-p` każde wywołanie wymagające zgody jest **odrzucane**; bez tego agent nie uruchomi `update.sh` |
| `--trust` | `-p` nie pyta o zaufanie do katalogu; bez tego nie wczyta `.vibe/` |
| `--max-turns 40` | bezpiecznik — zadanie potrzebuje ~10 tur |
| `--max-price 2` | bezpiecznik kosztowy, 2 USD na przebieg |

`--auto-approve` daje agentowi pełne prawo do komend. Uruchamiaj to na
dedykowanym koncie serwerowym, nie na swoim głównym.

**Alternatywa bez `--auto-approve`** — w `~/.vibe/config.toml`:

```toml
[tools.bash]
allowlist = ["git", "python3", "cat", "awk", "date", "tee", "grep"]
```

Wtedy tylko te komendy przechodzą bez pytania. `./update.sh` jako skrypt
wymagałby dopisania `bash` do listy, co psuje sens ograniczenia — dlatego
prościej zostawić `--auto-approve` i pilnować konta.

### Wariant B — `/loop` w otwartej sesji Vibe

Dobre, gdy trzymasz sesję Vibe w `tmux`/`screen` na serwerze. Wpisz w sesji:

```
/loop 0 6 1,15 * * Odśwież wykazy Ursus: uruchom ./update.sh, sprawdź liczbę pozycji w build.log, zacommituj i wypchnij na GitHub. Zakończ zwięzłym raportem po polsku.
```

Ograniczenie: pętla działa **tylko gdy sesja jest otwarta i bezczynna**.
Zamknięcie terminala = brak aktualizacji. Dlatego wariant A jest pewniejszy.

### Wariant C — Windows Task Scheduler

Jeśli serwer to Windows:

```powershell
$action  = New-ScheduledTaskAction -Execute 'vibe.exe' `
  -Argument '-p (Get-Content PROMPT-aktualizacja.txt -Raw) --auto-approve --trust --max-turns 40 --max-price 2' `
  -WorkingDirectory 'C:\rejestry-ursus'
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At 6am
Register-ScheduledTask -TaskName 'Rejestry Ursus' -Action $action -Trigger $trigger
```

(`-Weekly` co tydzień; dla „co dwa tygodnie” dodaj drugi trigger z przesunięciem
albo użyj `-DaysInterval 14` w `New-ScheduledTaskTrigger -Once`.)

---

## 6. Gotowy prompt

Pełna treść jest w `PROMPT-aktualizacja.txt`. Możesz ją też wkleić ręcznie do
sesji Vibe CLI:

```
Jesteś opiekunem projektu rejestry-ursus — generatora strony z wykazami decyzji
architektonicznych dla dzielnicy Ursus w Warszawie. Pracujesz w katalogu tego
projektu (sprawdź `pwd`).

ZADANIE: odśwież dane wykazów i opublikuj zmiany na GitHubie.

KROKI:

1. Uruchom `./update.sh` i przeczytaj jego wyjście.

2. Zinterpretuj kod wyjścia:
   - 0  → sukces, przejdź do punktu 3.
   - 2  → wynik poniżej progu jakości. NIE commituj. Zajrzyj do `build.log`,
          ustal który rocznik się posypał i zgłoś to w raporcie. Koniec.
   - 1  → build padł całkowicie. Zajrzyj do `build.log`, opisz błąd. Koniec.

3. Sprawdź, czy dane faktycznie się odświeżyły. Jeśli build poszedł w tryb
   --render-only, napisz to wyraźnie w raporcie jako ostrzeżenie — strona
   została przebudowana, ale dane są stare.

4. Sprawdź `git log --oneline -3` i `git status --short`. Jeśli update.sh
   wypchnął commit, potwierdź, że jest na origin/main.

5. Raport końcowy (zwięzły, po polsku):
   - liczba pozycji w każdym roczniku (z `data/index.json`),
   - czy dane są świeże, czy z cache,
   - hash i temat wypchniętego commita (albo "bez zmian"),
   - wszystko, co wygląda podejrzanie.

ZASADY:

- Nie zmieniaj kodu parserów w `build.py`, jeśli nie musisz. Jeśli musisz,
  opisz dokładnie co i dlaczego.
- Nie usuwaj plików z `data/` — brakującego rocznika nie traktuj jako sprzątania.
- Nie rób `git push --force`.
- Jeśli źródło (ursus.um.warszawa.pl) nie odpowiada, NIE próbuj go obejść przez
  VPN czy proxy — zgłoś problem i zakończ.
- Nie edytuj `site/index.html` ręcznie — generuje go `build.py`.
```

---

## 7. Co sprawdzić po przebiegu

```bash
cd /srv/rejestry-ursus
git log --oneline -3          # czy jest nowy commit
git status --short            # powinno być pusto
tail -20 build.log            # linia "RAZEM: ..."
```

W przeglądarce:

- **Strona**: https://kadece.github.io/rejestry-ursus/
- **Actions**: https://github.com/kadece/rejestry-ursus/actions
- **Commity**: https://github.com/kadece/rejestry-ursus/commits/main

Liczby kontrolne (stan z 2026-11-19) — spadek o więcej niż ~5% oznacza problem
ze źródłem, nie z parserem:

| Rocznik | Pozycji | Rejestrów |
|---|---|---|
| 2019 | 766 | 6 |
| 2020 | 614 | 7 |
| 2021 | 536 | 7 |
| 2022 | 611 | 7 |
| 2023 | 563 | 6 |
| 2024 | 449 | 6 |
| 2025 | 549 | 7 |
| 2026 | 470 | 8 |
| **razem** | **4558** | |

---

## 8. Gdy coś się zepsuje

| Objaw | Przyczyna | Naprawa |
|---|---|---|
| `Brak danych — przerywam.` | żaden rocznik się nie pobrał | sprawdź `curl -sI` na stronę źródłową; jeśli 403 — źródło blokuje IP serwera |
| Liczba pozycji spadła o kilkadziesiąt | zmiana układu tabeli na stronie | porównaj `raw/` z poprzednim przebiegiem, popraw parser w `build.py` |
| `Brak openpyxl` | brak biblioteki | `python3 -m pip install openpyxl pdfplumber` |
| `git push` → 403 | wygasł token / brak prawa zapisu | nowy PAT albo deploy key |
| `git commit` → `Author identity unknown` | brak `user.name`/`user.email` | `git config --global user.name ...` |
| Strona się nie zmieniła, commit jest | Pages nie odbudowało | Actions → ostatni run → sprawdź krok `deploy` |

**Fallback bez sieci**: `python3 build.py --all --render-only` przebudowuje
`site/index.html` z istniejących `data/*.json` w kilka sekund. `update.sh`
robi to automatycznie, gdy pobranie padnie.

---

## 9. Mapa repozytorium

```
rejestry-ursus/
├── build.py                  # pobieranie + parsowanie + render (jedyne źródło prawdy)
├── update.sh                 # opakowanie: build → kontrola jakości → commit → push
├── PROMPT-aktualizacja.txt   # prompt dla agenta (ten sam co w sekcji 6)
├── AKTUALIZACJA.md           # ten plik
├── data/
│   ├── index.json            # spis roczników: liczby, źródła, daty generowania
│   └── wykazy-2019..2026.json
├── site/
│   └── index.html            # gotowa strona (generowana — nie edytuj ręcznie)
├── templates/                # index.html, style.css, app.js, logo-bizu.b64
├── raw/                      # pobrane PDF/XLSX (w .gitignore)
├── build.log                 # log ostatniego przebiegu (commitowany)
├── WORDPRESS.md              # osadzenie strony na WordPressie
└── .github/workflows/update.yml  # to samo zadanie po stronie GitHuba
```

---

## 10. Publikacja na GitHub Pages

Jednorazowa konfiguracja — **wymaga jednego kliknięcia w przeglądarce**, nie da
się jej zrobić z agenta ani z workflow (sprawdzone: `GITHUB_TOKEN` dostaje
`Resource not accessible by integration` przy próbie utworzenia strony Pages):

1. https://github.com/kadece/rejestry-ursus/settings/pages
2. **Source**: `GitHub Actions` (nie „Deploy from a branch”)
3. Actions → **Aktualizacja wykazów** → **Run workflow**

Adres po pierwszym udanym deployu: **https://kadece.github.io/rejestry-ursus/**

### Potwierdzony stan rzeczy (2026-11-19)

Workflow na runnerze GitHuba **nie pobiera świeżych danych**. Przebieg
`44532448993` zapisał do `build.log`:

```
=== DIAGNOSTYKA ŹRÓDŁA ===
status=403 type=text/html size=3205 ip=34.248.138.138
--- pierwsze 400 znaków odpowiedzi ---
<title>Strona nie może zostać wyświetlona - Portal Informacyjny Urzędu m.st. Warszawy</title>
```

Czyli: **HTTP 403**. Serwer dzielnicy blokuje adresy z centrów danych (ten
runner wyszedł z AWS `eu-west-1`). To nie jest zmiana układu strony ani błąd
parsera — z domowego/ biurowego IP te same adresy zwracają 200.

Skutek: workflow działa jako **deploy**, nie jako **fetch**. Publikuje
`site/index.html` przebudowany z `data/*.json` zapisanych w repozytorium
(tryb `--render-only`). To jest poprawne zachowanie — strona nigdy nie zostaje
zepsuta — ale dane się nie odświeżają.

**Dlatego `update.sh` na własnym serwerze jest głównym źródłem świeżych danych.**
Serwer pobiera dane, commituje i wypycha; workflow publikuje to, co przyjdzie.

