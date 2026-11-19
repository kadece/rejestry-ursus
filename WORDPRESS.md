# Publikacja na zielonyursus.pl

Strona jest gotowym plikiem `site/index.html` (~1,1 MB, wszystko w środku:
HTML, CSS, JS, dane ośmiu roczników i logo jako data URI). Nie potrzebuje
bazy danych, PHP ani żadnych zależności — wystarczy ją gdzieś położyć
i wstawić na WordPressie ramkę.

Serwis `zielonyursus.pl` to WordPress 7.1.5 z Elementorem i Yoast SEO,
więc każde z poniższych rozwiązań wpina się w niego bez ruszania motywu.

---

## Co wybrać

| | Wariant A — GitHub Pages | Wariant B — FTP na własną domenę | Wariant C — shortcode + JSON |
|---|---|---|---|
| Praca na serwerze | żadna | wgranie 1 pliku | wgranie 8 plików JSON + 1 plik PHP |
| Aktualizacje | automatyczne (2× w miesiącu) | ręczne albo `update.ps1 -Deploy` | ręczne |
| Adres | `…github.io/wykazy-ursus/` | `zielonyursus.pl/wykazy/` | `zielonyursus.pl/wykazy-i-rejestry/` |
| Indeksowanie w Google | nie (iframe) | nie (iframe) | tak |
| Wygląd | własny, spójny | własny, spójny | odziedziczony po motywie |
| Wysiłek | ~15 min, raz | ~10 min + FTP | ~1 h |

**Rekomendacja: A.** Zero pracy przy każdej aktualizacji — workflow
w GitHub Actions przebudowuje stronę 1. i 15. dnia miesiąca i sam ją
publikuje. WordPress dostaje tylko `<iframe>`, który się nie zmienia.

Jeśli pozycjonowanie w Google na frazy typu „decyzje o warunkach zabudowy
Ursus” jest ważne — idź w C. Iframe nie jest indeksowany jako treść
strony, tylko jako osobny adres.

---

## Wariant A — GitHub Pages + iframe

### 1. Repozytorium

```bash
cd wykazy-ursus
git init
git add .
git commit -m "Wykazy Ursus 2019-2026"
git remote add origin https://github.com/UZYTKOWNIK/wykazy-ursus.git
git push -u origin main
```

### 2. Włącz Pages

W repozytorium: **Settings → Pages → Source: GitHub Actions**.
Workflow `.github/workflows/update.yml` sam zbuduje i opublikuje stronę
(przy pierwszym pushu i potem 1. oraz 15. dnia miesiąca o 6:00 UTC).

Po chwili strona działa pod:

```
https://UZYTKOWNIK.github.io/wykazy-ursus/
```

### 3. Wstaw na WordPressie

1. **Strony → Dodaj nową**, tytuł np. „Wykazy i rejestry”, slug
   `wykazy-i-rejestry` (pasuje do `ursus-mapa-inwestycji`).
2. **Edytuj Elementorem** → widget **HTML** → wklej:

```html
<div class="wykazy-ursus-embed">
  <iframe
    id="wykazyUrsusFrame"
    src="https://UZYTKOWNIK.github.io/wykazy-ursus/index.html?embed=1"
    title="Wykazy i rejestry — Dzielnica Ursus"
    loading="lazy"
    style="width:100%; height:1400px; border:0; display:block; border-radius:16px; background:#f4f6f9;"
  ></iframe>
</div>

<script>
(function () {
  var frame = document.getElementById('wykazyUrsusFrame');
  if (!frame) return;
  window.addEventListener('message', function (e) {
    if (!e.data || e.data.type !== 'wykazy-ursus-height') return;
    var h = parseInt(e.data.height, 10);
    if (h > 200) frame.style.height = h + 'px';
  });
})();
</script>
```

3. Podmień `UZYTKOWNIK` na swoją nazwę konta GitHub.
4. Opublikuj. Ramka sama dopasowuje wysokość, więc nie ma wewnętrznego
   paska przewijania.

> Elementor czasem wycina `<script>` z widgetu HTML, jeśli wtyczka
> bezpieczeństwa filtruje treść. Jeśli tak się stanie, wklej sam
> `<iframe>` w widgecie HTML, a skrypt dodaj przez **Code Snippets**
> (hak `wp_footer`) albo w motywie potomnym.

---

## Wariant B — plik na własnej domenie (FTP)

Biblioteka mediów WordPressa **nie przyjmie pliku `.html`** (domyślnie
zablokowane rozszerzenie), dlatego plik kładziemy obok WordPressa,
w zwykłym katalogu na hostingu.

1. Zbuduj stronę lokalnie: `python build.py --all`.
2. Połącz się z hostingiem (FileZilla, Total Commander, menedżer plików
   w panelu — DirectAdmin / cPanel).
3. Wgraj `site/index.html` jako:

```
public_html/wykazy/index.html
```

4. Sprawdź w przeglądarce: `https://zielonyursus.pl/wykazy/index.html`.
5. Wstaw na WordPressie ten sam snippet co w wariancie A, tylko ze
   `src="https://zielonyursus.pl/wykazy/index.html?embed=1"`.

### Aktualizacja

Ręcznie: przebuduj i wgraj plik ponownie. Albo zamontuj katalog hostingu
jako dysk sieciowy i użyj:

```powershell
.\update.ps1 -Deploy 'Z:\public_html\wykazy'
```

### Cache

Po podmianie pliku przeglądarki i CDN mogą pokazywać stare dane. Dodaj
do adresu w iframe parametr wersji i podbijaj go przy każdej aktualizacji:

```
https://zielonyursus.pl/wykazy/index.html?embed=1&v=2026-11
```

---

## Wariant C — shortcode + JSON (natywnie, indeksuje się)

Treść jest wtedy częścią strony WordPressa: indeksuje się, dziedziczy
typografię motywu i nie wymaga iframe.

1. Wgraj pliki `data/wykazy-2019.json` … `data/wykazy-2026.json` do:

```
wp-content/uploads/wykazy/
```

2. Wgraj `wordpress-shortcode.php` do `wp-content/mu-plugins/`
   (utwórz katalog, jeśli nie istnieje) albo wklej jego treść do wtyczki
   **Code Snippets**.
3. W treści strony:

```
[wykazy_ursus_tabela rok="2026"]
[wykazy_ursus_tabela rok="2026" rejestr="dec_wz" limit="20"]
```

4. Jeśli wolisz iframe, ale chcesz mieć go jako shortcode:

```
[wykazy_ursus src="https://zielonyursus.pl/wykazy/index.html"]
```

**Czego ten wariant nie ma:** przełącznika roczników, widoku miesięcznego,
wyszukiwarki i eksportu CSV. To wszystko jest w `site/index.html`.
Shortcode daje surowe tabele — dobre do SEO i do szybkiego podglądu,
słabsze jako interfejs.

---

## Aktualizacja danych — co się dzieje po stronie WordPressa

| Wariant | Co robisz przy aktualizacji |
|---|---|
| A | nic — workflow sam publikuje nową wersję |
| B | wgrywasz `site/index.html` ponownie (albo `update.ps1 -Deploy`) |
| C | wgrywasz zmienione pliki `data/wykazy-*.json` |

W żadnym wariancie nie ruszasz treści strony w WordPressie — snippet
z iframe zostaje ten sam.

---

## Checklist przed publikacją

- [ ] `python build.py --all` kończy się bez błędów i wypisuje
      `RAZEM: 4558 pozycji w 8 rocznikach`.
- [ ] `site/index.html` otwiera się z dysku i przełącza roczniki.
- [ ] Logo BiZU jest w prawym górnym rogu, w jednej linii z nagłówkiem.
- [ ] W trybie `?embed=1` logo ma ciemną plakietkę (na jasnym tle
      białe logo byłoby niewidoczne).
- [ ] Adres w `src` iframe prowadzi do opublikowanego pliku, nie do
      `twojadomena.pl`.
- [ ] Strona w WordPressie ma ustawiony tytuł i opis w Yoast SEO.
