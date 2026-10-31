# Plan „Mapa 1.0" — mapa 3D okolicy Słońca w ~1,25 kpc

Wersja 1 (31.10.2026). Plan dla jednej osoby pracującej z Claude Code.
Przycięty z planu v4 (`docs/plan-v4/`). Wszystko, co tu pominięto, zostaje
w planie v4 jako praca na później (§5).

## 1. Cel

Interaktywna mapa 3D gwiazd w promieniu ~1,25 kpc wokół Słońca, w której
po obróceniu kamery na widok z boku widać spłaszczenie dysku. Do tego
orientacyjna wysokość skali dysku z prostego fitu, wyraźnie opisana jako
szacunek, nie pomiar.

**Gotowe, gdy:**
- viewer płynnie pokazuje ~1–1,5 mln gwiazd z kolorami i widokiem z boku;
- katalog odtwarza się jednym poleceniem z manifestu;
- katalog referencyjny (domyślne `MAX_DIST_PC` = 60 pc) z nowego pipeline'u zgadza się ze starym (te same gwiazdy,
  odległości w granicach niepewności);
- orientacyjna wysokość skali mieści się w 200–450 pc (szeroki przedział, bo
  bez korekt z planu v4).

## 2. Co bierzemy z planu v4 (tanie, a dużo daje)

| Element | Źródło w v4 | Uproszczenie w 1.0 |
|---|---|---|
| Parquet + DuckDB, manifest zapisywany jako ostatni | S1 | Partycje HEALPix poz. 2; bez warstw `layers/` i `details.bin` |
| Funkcja selekcji `parallax > 0.5 AND phot_g_mean_mag < g_max` | S3, U2 | `g_max = 15` na start (parametr); G < 19 później |
| Pobieracz uproszczony: kafelki po `source_id`, joby async, pomijanie gotowych plików | S3 | Bez pełnego klienta UWS, bez atrapy TAP |
| Korekta zero-pointu (`gaiadr3-zeropoint`, przycięcie do zakresu z flagą) | S2 | Bez wariantów systematyki |
| Odległość: inwersja z korektą dla ϖ/σ > 5, `dist_origin`, `r_lo/r_med/r_hi` | S2 | EDSD opcjonalnie, tylko do viewera |
| Współrzędne galaktocentryczne, preset astropy `v4.0` | S2, U11 | Bez zmian |
| Mapa pyłu Edenhofer 2024 (średnia) do odczerwienienia koloru | S5 | Bez próbek posterioru |
| Eksport binarny dla viewera, przerzedzenie, przezroczystość wg niepewności | S1 | Jeden plik, bez kafelków x/y/z na start |

**Dlaczego `g_max = 15` na start:** zbiór jest o rząd–dwa wielkości mniejszy
niż przy G < 19 (dokładną liczbę daje jedno zapytanie COUNT), mieści się
wygodnie na laptopie, a jasne gwiazdy mają dobre paralaksy, więc proste
odległości wystarczą. Kosztem jest to, że daleko widać tylko jaśniejsze
gwiazdy. Dla mapy to akceptowalne, bo selekcja jest sferyczna i spłaszczenie
dysku pozostaje widoczne.

## 3. Kamienie milowe

Szacunki w sesjach pracy z Claude Code (wieczór lub pół dnia weekendu).

| # | Kamień milowy | Sesje | Termin |
|---|---|---|---|
| M1 | Magazyn: CSV → Parquet + DuckDB, manifest, test zgodności z katalogiem referencyjnym 60 pc | 2–3 | do ~9.11 |
| M2 | Pobieracz uproszczony + pobranie DR3 (`g_max = 15`, 1,25 kpc) | 2–3 | **przed 25.11** |
| M3 | Zero-point, odległości, współrzędne galaktocentryczne | 2–3 | do ~1.12 |
| M4 | Eksport binarny, viewer z ~1,5 mln punktów, widok z boku | 3–4 | grudzień |
| M5 | Pył (Edenhofer) dla kolorów, orientacyjny fit wysokości skali | 2–3 | grudzień |
| M6 | Przejście na DR4 (zmiana konfiguracji + test katalogu referencyjnego) | 1–2 | styczeń |

Jedyny twardy termin to **M2 przed wyłączeniem archiwum ESA 25.11 12:00 CET**
(do 2.12). DR3 jest też w AIP (`gaia.aip.de`, pełna
`gaiadr3.gaia_source`, dostępne także w czasie wyłączenia ESA; domyślna
kolejka 30 s, trzeba wybrać kolejkę 2 h). Przegapienie terminu oznacza więc
zmianę serwisu, a nie koniec projektu.

## 4. Orientacyjna wysokość skali (M5) — świadome uproszczenia

Prosty fit: walec R < 250 pc, karły G/K z oknem w CMD, histogram |z|,
profil wykładniczy na 150–450 pc. **Znane obciążenia, których 1.0 nie
koryguje** (opisane w v4, S4 T5 i S5):
- odległości z inwersji paralaksy, nie fit w przestrzeni paralaks;
- brak mocków i budżetu systematyki;
- z☉ zależy od założenia symetrii północ–południe;
- składnik cienki i gruby nie są rozdzielane.

Wynik raportujemy jako „h_1 ≈ X pc (orientacyjnie)". Literatura dla
porównania: Jurić+2008 ~300 pc (cienki dysk), Bennett & Bovy 2019 z☉ = 20,8 pc.

## 5. Na później (plan v4, bez zmian)

Wszystko poniżej zostaje w `docs/plan-v4/` i w indeksie `00_PLAN_ZMIAN_v4.md`
wraz z uzgodnieniami U1–U12. Wraca, gdy 1.0 będzie gotowe i zechcesz
naukowego pomiaru albo większej skali.

- **Pełny zbiór G < 19** (~1,9·10⁸ wierszy), partycje poz. 3, budowa
  kafelkami — S1, S3.
- **Pełny klient pobierania** (stan UWS, backoff, split, atrapa TAP) — S3.
- **Fit w przestrzeni paralaks**, funkcje populacyjne zp i σ_ϖ, generator
  mocków D11 — S2.
- **Walidacja**: testy T1–T8, próba generalna T5, bramki G1–G3, raport T6d
  dla DR4 — S4.
- **Pomiar naukowy**: red clump, Wesenheit, normalizacja, profile h_thin,
  budżet systematyki z 12 próbkami mapy — S5 (z poprawkami U1).
- **Hipparcos**: `hip_best_neighbour`, `excluded_by_selection` — U4.
- **Etap 3**: inne katalogi, mapy pyłu poza 1,25 kpc, masy, świece
  standardowe, warp i flara — indeks v4 §6.

## 6. Jak pracujemy (repo jako źródło prawdy)

- **Ustalenia żyją w repozytorium** (`docs/`), bo Claude Code czyta je
  automatycznie przez `CLAUDE.md`, a historia jest w gicie.
- **`docs/DECISIONS.md`** — dziennik decyzji: każda zmiana zakresu, progu
  albo metody to nowy wpis (data, decyzja, powód, skąd).
- **Projekt w claude.ai** czyta te same pliki przez integrację GitHub
  (synchronizacja przyciskiem „Sync now”). Ręczne kopie w projekcie
  zastępujemy plikami z repo.
- **Sesje Claude Code** dopisują do `DECISIONS.md` w tym samym PR, w którym
  zmieniają kod, jeśli decyzja wychodzi poza zadanie.
