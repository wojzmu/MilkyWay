# S1 — Magazyn danych i eksport do viewera
Wersja: v3 · Etap: 1 (magazyn gotowy na pełne pobranie DR3 13–16.11; viewer do etapu 2)

## Cel
Zastąpić CSV magazynem Parquet + DuckDB dla ~2·10⁸ wierszy (DR3/DR4, `parallax > 0.5`,
G < 19). Magazyn ma dawać szybkie wycinki nieba, tanie skany po kilku kolumnach,
ograniczone zużycie pamięci i jawny znacznik kompletności. Dla viewera: binarny
eksport ~1,5 mln punktów w kafelkach x/y/z, który zachowuje kontrast gęstości dysku.
Obecny viewer CSV nie przestaje działać.

## Zakres / poza zakresem
**W zakresie:**
- schemat kolumn (nazwy, typy, właściciele);
- układ na dysku: partycje, sortowanie, row-groupy;
- budowa partycji z surowych kafelków S3;
- wpięcie globalnej deduplikacji Hipparcosa;
- znacznik kompletności i manifest (sekcja `storage`);
- odczyt (pandas, DuckDB) i migracja CSV→Parquet;
- eksport CSV dla starego viewera;
- binarny eksport viewera i loader (jeden poziom szczegółowości);
- format artefaktów pomocniczych S2 (tablice σ_ϖ, ν_eff);
- warstwy dodatkowe (sidecar) dla kolumn S5.

**Poza zakresem:**
- pobieranie i plan kafelków (S3);
- obliczenia odległości, ZP i dopasowanie Hipparcos–Gaia (S2; S1 tylko wywołuje);
- cięcia jakości i selekcja traserów (S4/S5);
- pełny LOD (etap 3);
- FITS — tylko na żądanie dla zbiorów < 10⁶ wierszy.

## Wejścia i wyjścia
- **Od S3 v3:** `raw/<release>/tile_<id>.parquet` (kolumny archiwum 1:1 + `healpix`
  poz. 12, posortowane po `source_id`). Każdy kafelek mieści się w jednym pikselu
  poz. 3, więc także poz. 2. Kafelki pokrywają cały zakres `source_id` bez dziur.
  Do tego `manifest.json` (sekcje `dataset`, `fetch`; hashe kafelków
  `content_hash_ids`, `content_hash_values`) oraz zbiory pomocnicze
  `raw/<release>/aux/<nazwa>.parquet`:
  - „bliski”;
  - Hipparcos-2;
  - **`hip_best_neighbour`**: `hipparcos2_best_neighbour` JOIN `gaia_source`
    (`hip, source_id, parallax, phot_g_mean_mag, astrometric_params_solved`),
    **bez cięć selekcji**, ~10⁵ wierszy (koordynator, do dopisania w S3);
  - **`population`**: próbka 1% bez cięć (S3 v3 dec. 3).
- **Od S2 v3:** `corrected_parallax`, `estimate`, kolumny galaktocentryczne,
  dopasowanie Hipparcosa, tablice D12. Wszystkie przyjmują **tablice** jako argumenty,
  nie nazwy kolumn. S1 wywołuje je per kafelek przez adapter (dec. 8a).
- **Wyjście:**
  ```
  raw/<release>/…                       # własność S3, tylko do odczytu
  data/<dataset_id>/                    # niezmienny po statusie complete
    manifest.json                       # zapisywany jako ostatni (dec. 7)
    catalog/part_hpx=<k>/part-0.parquet # k = 0…12·4^P−1
    hip_match.parquet                   # wynik globalnej deduplikacji (dec. 6)
    aux/sigma_parallax.parquet, aux/nu_eff_bprp.parquet   # S2 D12, S1 tylko przechowuje
    layers/<nazwa>/part_hpx=<k>/…       # kolumny S5 (dec. 9)
    viewer/index.json, points.bin, details.bin, catalog.csv (opcjonalnie)
  ```

## Liczności i rozmiary (model weryfikatora, własne przeliczenie na poziomy 2/3)
Model jest skalibrowany na GCNS (331 312 gwiazd w 100 pc) i daje 64,2 mln przy
`parallax > 1, poe > 5` (El-Badry i in. 2021: 64,4 mln). Wiersze per piksel to bloki
modelu przeskalowane do pola HEALPix (poz. 2 = 214,9 deg², poz. 3 = 53,7 deg²).
Wszystko **do weryfikacji** próbką populacyjną S3 (2–3.11). Selekcja: `parallax > 0.5`.
Weryfikator przeliczył model na prawdziwych pikselach NESTED w ICRS (r2) i dostał
G < 19: P = 2 maks. 5,1 mln, P = 3 maks. 1,49 mln. Przy P = 3 żaden piksel nie
przekracza N_target = 2 mln, więc wychodzi 768 kafelków.

| Scenariusz | Wiersze | Katalog (~150 B/w) | Maks. partycja P=2 / P=3 | Mediana P=3 |
|---|---|---|---|---|
| G < 18 | 1,3·10⁸ | ~20 GB | 2,7 / 0,8 mln | 0,11 mln |
| **G < 19 (domyślny)** | 1,9·10⁸ (S3: 2,3·10⁸) | ~30–35 GB | 4,6 / 1,5 mln | 0,15 mln |
| bez limitu G | 4,8·10⁸ | ~75 GB | 24 / 11,5 mln | 0,27 mln |

Surowe kafelki zajmują dodatkowo ~100 B/w (S3, do pomiaru).

## Decyzje
1. **Poziom partycji P = 3 (768 partycji).** Reguła koordynatora: największa
   partycja mieści się w pamięci z zapasem.
   - Maszyna referencyjna ma 16 GB RAM (do potwierdzenia). Budżet na partycję to
     25% RAM, czyli 4 GB.
   - Pamięć: ~600 B/wiersz w pandas przy obliczeniach S2 (~60 kolumn, liczone w
     float64, plus kopie robocze; do pomiaru w zad. 3). Stąd limit n_max ≤ ~6,5 mln
     wierszy.
   - P = 3 przy G < 19, z ×2 na błąd modelu: 3 mln wierszy, ~1,8 GB. Zapas >2×.
   - P = 2 w tym samym wariancie: 9,2 mln wierszy, ~5,5 GB. Nie mieści się.
   - P = 3 przy G < 18: 1,6 mln wierszy, zapas 4×.
   - Bez limitu G nie mieści się żaden poziom (P = 3: 23 mln). Dlatego budowa
     zbioru zawsze idzie strumieniowo (dec. 4), a reguła dotyczy tylko odbiorców,
     którzy wczytują całą partycję.
   - Koszt: małe pliki (mediana ~25 MB, minimum ~8 MB, maksimum ~225 MB). DuckDB
     zaleca 100 MB–10 GB na plik. Przy 768 plikach na lokalnym SSD narzut stopek to
     szacunkowo < 1 s na pełny skan, wobec ~30 GB danych (do zmierzenia w zad. 7).
   - Zgodność z S3 v3: przy P = 3 każdy piksel to 1 kafelek (maksimum 1,5 mln
     < N_target 2 mln), razem 768 kafelków. Mieści się w budżecie czasu S3.
   - **Reguła ostateczna (3–4.11, po próbce populacyjnej S3):** P = 2 tylko wtedy, gdy
     zmierzone maksimum poz. 2 ≤ 3 mln wierszy. W przeciwnym razie P = 3. Wartość
     trafia do manifestu. Kafelki S3 v3 są wyrównane do poz. 3, więc decyzja nie
     blokuje planu kafelków. Model daje 5,1 mln, więc praktycznie P = 3.
   - *Odrzucone:* stałe P = 2 (rozsadza budżet przy błędzie ×2); poz. ≥ 4 (3072+
     plików, mediana < 7 MB); partycje adaptacyjne HATS (dodatkowa zależność;
     wracamy w etapie 3).
2. **Klucz partycji `part_hpx = healpix >> 2·(12−P)` dla wszystkich wierszy**
   (koordynator pkt 3).
   - Kolumna `healpix` (NESTED, poz. 12, `int64`, niepusta):
     - wiersze Gai: `source_id >> 35`;
     - wiersze Hipparcos-only: liczona przez S2 z (ra, dec) na `gaia_ref_epoch`.
   - `part_hpx` żyje tylko w ścieżce Hive.
   - Odczyt w DuckDB: `hive_partitioning = true`, `hive_types = {'part_hpx': INTEGER}`.
3. **Sortowanie w pliku po (`healpix`, `source_id` NULLS LAST).**
   - Dla wierszy Gai to to samo co sortowanie po `source_id`, bo indeks HEALPix
     jest prefiksem w schemacie NESTED.
   - Wiersze Hipparcos-only wchodzą w porządek po `healpix`, a nie na koniec pliku.
   - Statystyki row-group na `healpix` i `source_id` są ciasne.
   - *Odrzucone:* sortowanie po `r_med_pc`/`z_pc` (psuje przycinanie po niebie;
     S5 i tak czyta kilka kolumn z całości).
4. **Budowa strumieniowa: jednostką przetwarzania jest kafelek S3, a nie partycja.**
   - Dla partycji k bierzemy kafelki z `lo >> sP == k`, rosnąco po `lo`. Każdy
     kafelek (≤ N_target = 2 mln wierszy, ~1,2 GB w pandas) przechodzi kolejno:
     zmianę nazw i typów, dołączenie wierszy Hipparcos-only o `healpix` w
     [lo>>35, hi>>35] i adnotację `hip` z `hip_match`, potem S2 i `classify`,
     na końcu sortowanie.
   - Wynik idzie do `pyarrow.parquet.ParquetWriter` (`part-0.parquet.tmp`).
     Reszta wierszy poniżej pełnego row-group przechodzi do następnego kafelka,
     więc wszystkie row-groupy poza ostatnim mają równą liczność.
   - Kafelki są rozłączne i posortowane, więc ich sklejenie jest posortowane.
     Nie trzeba sortowania w pamięci całej partycji.
   - Na końcu: fsync → `rename` na `part-0.parquet`. Glob `*.parquet` nie widzi
     plików `.tmp`.
   - **Równoległość ograniczona pamięcią:** proces = jedna partycja naraz.
     Liczba procesów `n_proc = max(1, floor(4 GB / M_tile))`, gdzie M_tile to
     zmierzony szczyt na kafelek 2 mln wierszy (zad. 3; szacunek ~1,2 GB → 3
     procesy). Partycje rozdzielane od najcięższych.
   - *Odrzucone:* `pyarrow.dataset.write_dataset` i DuckDB `COPY … PARTITION_BY`.
     Nie dają kontroli nad atomowością, porządkiem i strumieniem z S2.
     (Ich limity: pyarrow `max_partitions` 1024, DuckDB `partitioned_write_max_open_files`
     100.)
5. **Row-group 131 072 wiersze (2¹⁷), zstd poz. 3, statystyki włączone.**
   - Jeden row-group to ~20 MB.
   - Największa partycja ma ~12–23 row-groupy, typowa 1–2. Razem ~1500 row-group,
     znacznie więcej niż wątków.
   - Mieści się w zaleceniu DuckDB (100 k–1 M wierszy/row-group). Domyślne pyarrow
     (1024·1024) zbyt zgrubne dla wycinków poz. 5–6.
   - `BYTE_STREAM_SPLIT` dla float włączamy tylko przy zysku > 10% (zad. 4).
6. **Hipparcos: globalna deduplikacja przed podziałem, z odpowiednikami spoza
   selekcji** (koordynator, rundy 1 i 2).
   - Wejście pre-passu:
     - cały Hipparcos-2;
     - `aux/hip_best_neighbour`, czyli para HIP–Gaia **bez cięć selekcji**;
     - kandydaci Gai z `raw/` o `g_mag < 13,5`, tylko do dopasowania pozycyjnego
       S2 D10 dla HIP spoza `best_neighbour`.
   - Na tym `match_hipparcos` (S2 D10) zwraca `hip_match.parquet` (`hip`,
     `source_id` lub null, `healpix`, `decision`). Wartości `decision`:
     - `gaia_in_catalog`: odpowiednik 5p/6p w selekcji. Wiersz Gai zostaje,
       dostaje `hip`;
     - **`excluded_by_selection`**: odpowiednik 5p/6p istnieje, ale nie spełnia
       `parallax > 0.5 AND G < 19`. Do katalogu **nie** wchodzi nic. Wiersz zostaje
       w `hip_match` z wartościami ϖ i G odpowiednika, do raportu;
     - `hip_only_no_match`: brak odpowiednika (jasne, G ≲ 3);
     - `hip_only_2p`: odpowiednik 2p, bez paralaksy;
     - `ambiguous`: kilku kandydatów lub |ΔG| ≥ 1. Zostaje wiersz Gai (jeśli jest
       w selekcji), a przypadek trafia do raportu (S2 D10).
   - Do katalogu jako wiersze Hipparcos-only wchodzą **tylko** `hip_only_*`.
     Hipparcos z odległością < 1,25 kpc nadal przechodzi, a reguła jest jawna.
   - Rozmiar `hip_match` to ~1,2·10⁵ wierszy. Budowa partycji (dec. 4) czyta
     tylko z niego.
   - Liczności decyzji trafiają do manifestu (`storage.hip_match`). Liczba
     `excluded_by_selection` jest **do policzenia** na `hip_best_neighbour`.
   - Zbiór oficjalny powstaje po komplecie kafelków. Szacunek czasu budowy:
     ~2·10⁸ wierszy przy 10⁶ w/min/rdzeń S2 i 3 procesach (dec. 4) to ~65–70 min
     (do zmierzenia).
   - Budowy próbne na częściowych danych są dozwolone ze statusem `trial`.
7. **Kompletność i niezmienność.**
   - `manifest.json` (sekcja `storage`) zapisywany atomowo **jako ostatni**:
     `status: complete`, `row_counts` i `content_hash` (= `canonical_hash`) per partycja, hashe
     artefaktów `aux/`.
   - `open_catalog()` odmawia zbioru bez `status: complete` (wyjątek:
     `allow_incomplete=True` z ostrzeżeniem). Sprawdza też, że lista plików
     równa się liście z manifestu, a liczby wierszy ze stopek równają się
     `row_counts`. To tani test, czyta tylko stopki.
   - Na początku budowy usuwamy osierocone `*.tmp`.
   - **Jedna funkcja `canonical_hash(table)` w `storage.py`** (koordynator).
     Używają jej S1 i S4 T7, a S3 może wywołać ją dla `content_hash_values`.
     Definicja (zgodna z S4 v3 T7, uzupełniona o porządek i typy):
     1. Porządek wierszy według `sort_key` zbioru, w S1 (`healpix`, `source_id`
        NULLS LAST, `hip`). Jest całkowity także przy null `source_id`.
     2. Typy z jawnego schematu (dec. 8). `category` i słowniki dekodowane do
        string.
     3. Każda kolumna osobno: SHA-256 z (a) bufora wartości little-endian bez
        wyrównania, z NaN zamienionym na jeden kanoniczny wzorzec bitów i
        wartościami pod nullem wyzerowanymi; (b) bitmapy nulli (1 bit na wiersz,
        LSB first); (c) dla string: offsetów int64 i bajtów UTF-8.
     4. Hash tabeli = SHA-256 z listy (nazwa, typ, hash kolumny), kolumny w
        kolejności nazw, plus liczba wierszy.
     - Nie zależy od podziału na batche, od row-groupów ani od wersji Arrow i
       Parquetu, bo nie hashuje bajtów IPC.
     - Hash partycji: `canonical_hash` treści pliku, liczony w locie
       (przyrostowo per kolumna, w kolejności zapisu, która jest kanoniczna).
     - Hash zbioru: SHA-256 z listy (k, hash partycji) rosnąco po k.
   - Nazwy pól: `content_hash` w manifeście S1 = `canonical_hash`. S3 zostaje przy
     `content_hash_ids` i `content_hash_values` (S3 v3). Koordynator nazwał pole
     S3 `ids_hash`, ale zaakceptowany S3 v3 używa `content_hash_ids`, więc S1 się
     do niego odwołuje. Ujednolicenie zostaje przy składaniu planu.
   - Ponowna budowa (inne S2, inne P) tworzy nowy `dataset_id`.
     *Odrzucone:* nadpisywanie w miejscu.
8. **Schemat:** jeden `pyarrow.Schema` z mapą nazw z archiwum, `schema_version = 2`
   w manifeście i w metadanych pliku. Pełna tabela niżej. Zasady:
   - `float64` dla `ra`, `dec`, `l`, `b`, `parallax_mas` (geometria, wejście S2);
     reszta liczb `float32`;
   - teksty i enumy jako `string` (Parquet koduje je słownikowo); `category`
     dopiero w pandas przy odczycie (potwierdzenie dla S2: `dist_flag`,
     `zp_origin`). Enumy walidowane przy zapisie;
   - `rgb_*` to `uint8` **nullable** (Arrow ma nulle; w pandas `UInt8`), bo
     `color` zwraca NaN poza zakresem. Nie robimy `astype("uint8")` jak w szkicu;
   - nazwy: kolumny obecnego katalogu zachowują dzisiejsze nazwy (`parallax` →
     `parallax_mas`, `phot_g_mean_mag` → `g_mag`), pozostałe kolumny archiwum
     zostają 1:1;
   - `dist_pc` nie jest zapisywany. To alias `r_med_pc` w widoku DuckDB `catalog`
     i w `read_catalogue()`, więc bitowa równość (S4 T1) zachodzi z konstrukcji.
8a. **Jeden adapter nazw w pipelinie** (koordynator). Funkcje S2 dostają tablice
    (`corrected_parallax(parallax=…, parallax_error=…, g=…, nu_eff=…, …)`), a nie
    ramkę z nazwami.
    - Moduł `pipeline` ma jedną tabelę „argument S2 ↔ kolumna katalogu”
      (`parallax` ↔ `parallax_mas`, `phot_g_mean_mag` ↔ `g_mag`, reszta 1:1)
      i jedną funkcję, która z niej buduje wywołania.
    - Test: każdy argument wymagany przez sygnatury S2 ma wpis w tabeli, a każda
      kolumna z tabeli istnieje w schemacie. Brak wpisu wychodzi w teście, a nie
      jako `KeyError` w przebiegu.
9. **Kolumny późniejszych segmentów jako warstwy (sidecar).**
   - S5 (`a0_mag`, …, `ext_origin`, `tracer`) zapisuje
     `layers/extinction/part_hpx=k/` z tym samym P, porządkiem i kluczem `star_id`.
   - Złączenie w DuckDB per partycja. Nie przepisujemy 30 GB dla kilku kolumn.
10. **Migracja CSV bez psucia viewera (bez zmian wobec v1).**
    - Krok A: Parquet jest źródłem prawdy, `catalog.csv` to jego eksport (te same
      kolumny i format), tylko dla zbiorów < 5·10⁵ wierszy.
    - Krok B: loader binarny za flagą `?format=bin`.
    - Krok C: po teście zgodności binarny staje się domyślny.
    - `source_id` czytany z CSV jako `Int64`.
11. **Eksport viewera: sześciany 250 pc w x/y/z (helio).**
    - Sfera 1,25 kpc przecina **720** z 1000 sześcianów siatki [−1250, 1250)³.
    - `points.bin`:
      - nagłówek 16 B: magic `MWPT`, `uint16` wersja, `uint16` flagi, `uint32` N,
        `uint32` zarezerwowane;
      - kafelki po kolei, każdy w układzie SoA: `n×3 float32` (x, y, z w pc) i
        `n×4 uint8` (R, G, B, U). Blok kafelka zajmuje 16·n B, więc kafelek
        zaczyna się w `16 + 16·first`;
      - 16 B/punkt, little-endian, wyrównanie 4 B;
      - **U = kod niepewności względnej** f = (r_hi−r_lo)/(2·r_med), w skali
        logarytmicznej: U = round(254·(log₁₀ f + 3)/(log₁₀ 0,5 + 3)), obcięte do
        [0, 254]. f ≤ 0,001 → 0, f ≥ 0,5 → 254, 255 = brak `r_hi`/`r_lo`;
      - bajt niesie daną, a nie przezroczystość. Mapowanie f → krycie robi shader,
        z suwakiem f_max (domyślnie 0,2), więc nie trzeba eksportu od nowa;
      - brak koloru (null `rgb_*`) → szary (128, 128, 128).
    - `details.bin`, ten sam porządek punktów:
      - nagłówek 16 B: magic `MWDT`, `uint16` wersja, `uint16` rozmiar rekordu
        (24), `uint32` N (musi równać się N z `points.bin`), `uint32` zarezerwowane;
      - rekordy AoS po 24 B: `int64 id` (`source_id`; dla Hipparcos-only −`hip`),
        `float32 r_lo_pc, r_hi_pc, g_mag, bp_rp`. Rekord ma 24 B, więc `int64`
        jest wyrównany do 8 B: 16 + 24·i ≡ 0 mod 8;
      - `index.json` trzyma dla kafelka **`first`** (indeks pierwszego punktu
        globalnie) i `n`. Bajty liczy viewer:
        - SoA w `points.bin`: xyz kafelka zaczyna się w `16 + 16·first`, a RGBU w
          `16 + 16·first + 12·n`;
        - `details.bin`: `16 + 24·first`, długość `24·n`;
      - wzory nie zależą od pozycji kafelka w pliku. Nagłówki mają stały rozmiar
        16 B, a zmiana formatu podnosi wersję;
      - viewer pobiera tylko kafelek klikniętego punktu przez HTTP Range
        (≤ ~0,5 MB).
      - Przy braku obsługi Range przez serwer: cały plik (~36 MB).
      - `id` przez `BigInt64Array`, wyświetlane jako tekst.
    - Odcinek r_lo–r_hi: `pos·r_lo/r_med`, `pos·r_hi/r_med`.
    - `index.json`: wersja formatu, `dataset_id`, hash manifestu, rozmiar kafelka,
      `(ix, iy, iz, first, n)`, f próbkowania, zapytanie selekcji, parametry U.
    - *Odrzucone:* plik na kafelek, układ przeplatany, Parquet w przeglądarce.
12. **Przerzedzenie (bez zmian):** punkt zostaje, gdy `splitmix64(id) < f·2⁶⁴`.
    - f = target/N, target domyślnie 1,5 mln.
    - W kafelku sortowanie po haszu, więc każdy prefiks jest próbą losową
      (LOD w etapie 3 przez `drawRange`).
    - Jedno f wszędzie zachowuje kontrast dysku.
    - Selekcję eksportu (np. jakość, objętość) podają S4/S5. S1 ją wykonuje i
      zapisuje.

### Schemat v2 (właściciel → kolumny: typ)
- **S1/S3 identyfikacja:**
  - `star_id`: string, niepusty, unikalny (`gdr3:<source_id>` / `hip:<hip>`;
    format starego CSV do sprawdzenia, zad. 2);
  - `source_id`: int64 null;
  - `hip`: int32 null;
  - `healpix`: int64;
  - `source_catalogue`: enum {Gaia, Hipparcos}.
- **S3 astrometria:**
  - float64: `ra, dec, l, b, parallax_mas`;
  - float32: `ra_error, dec_error, ecl_lat, parallax_error, pmra, pmra_error,
    pmdec, pmdec_error`.
- **S3 jakość / wejścia ZP:**
  - float32: `ruwe, astrometric_excess_noise, ipd_gof_harmonic_amplitude,
    nu_eff_used_in_astrometry, pseudocolour`;
  - int16: `astrometric_params_solved, visibility_periods_used, ipd_frac_multi_peak`;
  - bool: `duplicated_source`.
- **S3 fotometria i RV:**
  - `g_mag` (←`phot_g_mean_mag`), `phot_bp_mean_mag, phot_rp_mean_mag, bp_rp,
    phot_bp_rp_excess_factor, radial_velocity, radial_velocity_error`: float32;
  - GSP-Phot: `teff_gspphot, distance_gspphot, distance_gspphot_lower,
    distance_gspphot_upper, ag_gspphot, ebpminrp_gspphot`: float32.
- **S2:**
  - `parallax_zp_mas`: float32;
  - `zp_origin`: enum (7 wartości S2 v3);
  - `r_lo_pc, r_med_pc, r_hi_pc`: float32;
  - `dist_origin`: enum {parallax_inversion, edsd_prior, gspphot};
  - `dist_flag`: enum {ok, inversion_invalid, no_solution, no_parallax};
  - `x_pc, y_pc, z_pc, xgc_pc, ygc_pc, zgc_pc`: float32 (ulp przy 8,1 kpc
    ≈ 0,001 pc);
  - `dist_pc`: widok, nie kolumna.
- **Pozostałe moduły:**
  - float32: `v_mag, abs_g, teff_color`, `U, V, W` (nullable; MC w etapie 3);
  - `phot_origin`: enum; `star_class`: enum (wartości z `classify`, zad. 2);
  - `spurious_parallax`: bool;
  - `rgb_r/g/b`: uint8 null; `rgb_hex`: string null;
  - `simbad_main_id, proper_name, sp_type`: string null.

Pamięć Arrow: ~270 B/wiersz.

### Artefakty S2 D12 (format ustala S1, buduje S2)
- **Źródło:** próbka populacyjna `raw/<release>/aux/population` (1%, bez cięć ϖ i G;
  S3 v3 dec. 3), a **nie** `catalog/` (koordynator). S1 nie liczy tych tablic, tylko
  je przechowuje i weryfikuje.
- `aux/sigma_parallax.parquet`: `g_lo` float32 (co 0,25 mag, 6–21), `hpx3` int16,
  `sigma_med_mas` float32, `n` int32, `origin` {cell, beta_fallback}.
- `aux/nu_eff_bprp.parquet`: `bp_rp_lo` float32 (co 0,05), `nu_eff_med` float32,
  `n` int32.
- Metadane pliku (klucz-wartość Parquet, powtórzone w manifeście):
  - `source_dataset` = hash próbki populacyjnej z manifestu S3;
  - `g_min`, `g_max` (zakres pokryty; dzięki próbce 6–21). Funkcja
    `sigma_parallax_model` (S2) poza zakresem rzuca błąd, a nie ekstrapoluje;
  - `parallax_error_inflation`.
- S1 kopiuje pliki do `data/<dataset_id>/aux/`, liczy `canonical_hash` i wpisuje
  go do `storage.aux` przed zapisem manifestu.

## Zadania
Część „magazyn” do 12.11; część „viewer” dopuszczalna po 2.12.
1. **Decyzja P (0,5 d, 3–4.11).** Liczności poz. 2/3 z próbki populacyjnej S3
   (po selekcji, ×99,99999) → reguła z dec. 1 → wpis w konfiguracji.
2. **Schemat (1 d).**
   - `pyarrow.Schema`, mapa nazw, enumy;
   - sprawdzenie w repozytorium formatu `star_id` i wartości `star_class`;
   - test zgodności z listą kolumn S3 v3;
   - adapter nazw (dec. 8a) i jego test na sygnaturach S2 v3.
3. **Budowa strumieniowa (2 d).** Dec. 4–5, 7: ParquetWriter, przenoszenie reszty
   row-groupów, `.tmp` + rename, manifest jako ostatni, `open_catalog`. Pomiar
   M_tile na kafelek 2 mln wierszy, z niego `n_proc`.
3a. **`canonical_hash` (0,5 d).** Funkcja z dec. 7 + testy:
   - niezmienniczość wobec podziału na batche i row-groupy;
   - różne NaN dają ten sam hash;
   - wiersz null `source_id` nie zmienia porządku;
   - przekazanie S4 dla T7.
4. **Migracja i pomiar (1 d).**
   - CSV 20 pc → Parquet → CSV;
   - B/wiersz (zstd ± BYTE_STREAM_SPLIT) na pilocie S3 (3 kafelki, 3–4.11).
5. **Hipparcos pre-pass + zbiory małe (1 d).** Dec. 6 z `hip_best_neighbour`,
   raport `excluded_by_selection`; „bliski” i Hipparcos jako
   zbiory jednoplikowe.
6. **Zapytania DuckDB (1 d).**
   - parametryzowane: wycinek nieba (zakres `healpix` dowolnego poziomu, zawsze z
     filtrem `part_hpx`), objętość, histogram;
   - widok `catalog` z `dist_pc`;
   - liczba przeczytanych row-group z `EXPLAIN ANALYZE` (format do weryfikacji;
     zapasowo pomiar bajtów).
7. **Test skali (1 d)** na 2·10⁸ syntetycznych wierszy (mock S2 D11, jeśli gotowy)
   z rozkładem pikseli z modelu. Benchmarki z kryterium 4.
8. **Eksport CSV dla starego viewera + `plots` z Parquetu (0,5 d)** — krok A.
9. **Artefakty `aux/` (0,25 d):** przyjęcie tablic S2 (zad. 5 S2), metadane,
   hash.
10. *(po 2.12 dopuszczalne)* **Eksporter binarny (1,5 d).**
11. *(po 2.12)* **Loader w viewerze z Range i kodem U (2 d).**
12. *(po 2.12)* **Wydajność viewera 0,5–3 mln punktów i test zgodności
    CSV/bin (1,5 d).**

Razem: ~9,75 d przed 12.11, ~5 d po 2.12.

## Kryteria akceptacji
1. **Round-trip CSV→Parquet→CSV (20 pc):**
   - ten sam zbiór `star_id`;
   - kolumny float64, int i tekstowe identyczne;
   - float32 z różnicą względną ≤ 1,2·10⁻⁷;
   - `source_id` > 2⁵³ bit w bit;
   - NaN w `rgb_*` → null → pusty w CSV.
2. **Zbiór partycjonowany:**
   - `count(*)` = Σ wierszy kafelków + liczba wierszy Hipparcos-only;
   - 0 duplikatów `star_id`, `source_id` i `hip`;
   - **0 wierszy Hipparcos-only, których `hip` ma w `hip_best_neighbour`
     odpowiednik 5p/6p**. Każdy taki HIP ma w `hip_match` decyzję
     `gaia_in_catalog`, `excluded_by_selection` albo `ambiguous`;
   - dla każdego wiersza `part_hpx = healpix >> 2·(12−P)`, a dla wierszy Gai
     `healpix = source_id >> 35`;
   - w pliku (`healpix`, `source_id`) niemalejące;
   - row-groupy po 131 072 wiersze poza ostatnim;
   - identyczny schemat we wszystkich plikach.
3. **Kompletność i hash:**
   - `canonical_hash` tej samej treści jest identyczny przy row-group 2¹⁷ i 2¹⁵ oraz
     przy innej wersji pyarrow (CI z dwiema wersjami);
   - SIGKILL w trakcie zapisu partycji nie zostawia `*.parquet` z częściowymi
     danymi;
   - SIGKILL po 100 z 768 partycji: `open_catalog` odmawia (brak `complete`);
   - plik usunięty lub podmieniony po zapisie: `open_catalog` wykrywa niezgodność
     listy lub `row_counts`.
4. **Wydajność** (2·10⁸ wierszy; laptop 8 rdzeni, 16 GB, SSD — do potwierdzenia):
   - wycinek piksela poz. 5 czyta 1 plik i ≤ ⌈n/131 072⌉ + 1 row-groupów;
   - histogram `z_pc` dla `r_med_pc < 1250` < 60 s;
   - odczyt partycji do pandas ≤ 3 s na 10⁶ wierszy;
   - szczyt RAM budowy ≤ 4 GB łącznie (wszystkie `n_proc` procesy; pomiar RSS);
   - budowa pełnego zbioru ≤ 2 h.
5. **Stary viewer** działa bez zmian na `catalog.csv` z Parquetu (ta sama liczba
   gwiazd, papaparse bez błędów).
6. **Eksport binarny:**
   - `points.bin` = 16 + 16·N B;
   - `details.bin` = 16 + 24·N B, N w obu nagłówkach równe;
   - dla każdego kafelka rekord z `details.bin` na `16 + 24·first` ma id pierwszego
     punktu kafelka (test na 20 kafelkach);
   - na 20 pc bez przerzedzenia: ta sama liczba punktów, pozycje ≤ 1 ulp float32;
   - kod U odtwarza f z błędem ≤ 1,5% (log).
7. **Przerzedzenie zachowuje gęstość:** test χ² stosunku eksport/pełny katalog w
   przedziałach |z| co 50 pc, p > 10⁻³.
8. **Viewer:** 1,5 mln punktów ładuje się < 5 s lokalnie i daje ≥ 30 fps
   (maszyna referencyjna z zad. 12).

## Ryzyka i otwarte pytania
- **Liczności z modelu:** do weryfikacji próbką populacyjną 2–3.11. Mapa modelu ma rozdzielczość ~2°,
  więc lokalne maksima (okna w zgrubieniu) mogą być wyższe. Budowa strumieniowa
  (dec. 4) czyni to ryzykiem dla czasu i plików, a nie dla pamięci.
- **Narzut 768 małych plików** w DuckDB: do zmierzenia (zad. 7). Gdy > 10% czasu
  skanu, rozważyć P = 2 przy zmierzonych licznościach albo kompakcję.
- **Hipparcos poza `best_neighbour`:** HIP bez wpisu w tej tabeli, ale z
  odpowiednikiem w Gai spoza selekcji (np. błąd dopasowania ESA) nadal może wejść
  jako `hip_only_no_match`. Kontrola: każdy `hip_only_*` z Hp > 4 trafia do raportu
  do ręcznego przeglądu (spodziewane: pojedyncze przypadki).
- **DR4:** kodowanie `source_id` do weryfikacji (S3 test na 1000 wierszach). Jeśli
  się zmieni, `healpix` z (ra, dec), a reszta bez zmian, bo klucz to już `healpix`.
- **Obsługa HTTP Range** przez serwer deweloperski viewera — do weryfikacji
  (fallback jest).
- **Maszyna referencyjna** (RAM, GPU) — do ustalenia z użytkownikiem.

## Zmiany w kontrakcie
1. **P = 3 domyślnie** (192 / 768 partycji dla P = 2 / 3; plan v3 podaje
   „48–192”). Ostateczne P z reguły dec. 1, wpisane przed zamrożeniem planu S3.
2. **`part_hpx = healpix >> 2·(12−P)`** dla wszystkich wierszy. `healpix` to NESTED
   poz. 12, int64, niepusty; dla Hipparcos-only liczony na `gaia_ref_epoch`
   (S2 v3, Zmiana 7).
3. **Klucz sortowania (`healpix`, `source_id`).** Klucz łączenia warstw: `star_id`.
4. **Jednostka budowy = kafelek S3.** S1 korzysta z gwarancji S3 v3: kafelek ⊂ piksel
   poz. 3, posortowany, pokrycie bez dziur.
5. **Nazwy:** w katalogu `parallax_mas`, `g_mag` (zamiast `parallax`,
   `phot_g_mean_mag`); reszta archiwum 1:1. Funkcje S2 przyjmują tablice, a
   mapowanie robi jeden adapter w `pipeline` (dec. 8a). S2 v3 nie wymaga zmian.
   Zapytania S5 do DuckDB używają nazw katalogu (`g_mag`).
6. **Enumy w Parquecie jako `string`, `category` w pandas** (dotyczy `dist_flag`,
   `zp_origin` z S2 v3 i `ext_origin`, `tracer` z S5).
7. **`dist_pc` jako widok**, a nie zapisana kolumna.
8. **Kolumny S5 w warstwie `layers/`**, a nie w głównym katalogu.
9. **Manifest `storage`:**
   - `schema_version`, `partition_level`, `row_group_size`, `compression`, `sort_key`;
   - `status`, `row_counts`, `content_hash` per partycja;
   - `aux` (`canonical_hash`, `g_min/g_max`, źródło), `hip_match` (hash, liczności
     decyzji).
10. **`details.bin`:** nagłówek 16 B `MWDT`, rekord 24 B, id = `source_id` albo
    −`hip`. Adresowanie przez `first` z `index.json`.
11. **`canonical_hash`** (dec. 7) to jedyna definicja hasha treści dla S1 i S4 T7.
    S3 v3 `content_hash_values` powinien jej używać (do ujednolicenia przy składaniu
    planu; `content_hash_ids` bez zmian).
12. **S3: nowy zbiór pomocniczy `hip_best_neighbour`** bez cięć (koordynator).
    **Próbka `population`** to źródło tablic D12 (S3 v3, Zmiana 4). S1 tylko je
    przechowuje.
13. **Hipparcos:** decyzja `excluded_by_selection` — HIP z odpowiednikiem 5p/6p spoza
    selekcji nie wchodzi do katalogu. Uzupełnienie S2 v3 D10 („Priorytet”).

## Odpowiedź na recenzję
**Runda 1:** wszystkie 11 uwag zamknięte w v2 (potwierdzone w r2). Uwaga 4 była
otwarta częściowo i zamyka ją uwaga 1 rundy 2.

**Runda 2:**
1. **[ISTOTNA] Duplikaty Hipparcosa spoza selekcji — przyjęte** (koordynator pkt 1).
   - Pre-pass korzysta z `aux/hip_best_neighbour` (JOIN z `gaia_source` bez cięć,
     pobierany przez S3).
   - Nowa decyzja `excluded_by_selection`: taki HIP nie wchodzi do katalogu, zostaje
     tylko w `hip_match` i w raporcie (dec. 6).
   - Hipparcos-only to tylko `hip_only_no_match` / `hip_only_2p`.
   - Kryterium 2 rozszerzone o „0 Hipparcos-only z odpowiednikiem 5p/6p”.
   - Ryzyko przeniesione z „do S2” na resztkowy przypadek spoza `best_neighbour`.
2. **[ISTOTNA] Trzy definicje `content_hash` — przyjęte** (koordynator pkt 2).
   - Jedna funkcja `canonical_hash` w `storage.py` (dec. 7): hash per kolumna z
     kanonicznym NaN i nullami, porządek wg `sort_key` całkowity także przy null
     `source_id`, niezależna od batchy i wersji Arrow.
   - Hash zbioru = hash listy hashy partycji. S4 T7 i S3 `content_hash_values`
     odwołują się do niej (Zmiany 11).
   - Nazewnictwo: zaakceptowany S3 v3 ma `content_hash_ids` (a nie `ids_hash`, jak w
     wiadomości koordynatora). S1 używa nazwy z S3 v3, a ujednolicenie zostawia
     składaniu planu.
3. **[DROBNA] RAM a rdzenie — przyjęte.** `n_proc = floor(4 GB / M_tile)` z pomiaru
   (szacunkowo 3). Kryterium: ≤ 4 GB łącznie, budowa ≤ 2 h. Szacunek czasu
   ~65–70 min.
4. **[DROBNA] Nazwy wejść S2 — przyjęte w wariancie koordynatora (pkt 3).** S2
   przyjmuje tablice, a jeden adapter w `pipeline` z tabelą mapowania i testem na
   sygnaturach (dec. 8a). S2 v3 bez zmian, katalog przy nazwach S1.
5. **[DROBNA] Offset Range — przyjęte.** `first` w `index.json`, offsety
   `16 + 16·first` i `16 + 24·first`, nagłówek `details.bin` (`MWDT`, wersja,
   rozmiar rekordu, N). Wyrównanie int64 sprawdzone. Dwa nowe kryteria.
6. **[DROBNA] Zasięg tablicy σ_ϖ — przyjęte, rozwiązanie u źródła** (koordynator
   pkt 4). Tablice D12 buduje S2 z próbki populacyjnej 1% bez cięć (G 6–21), a nie z
   `catalog/`. S1 tylko je przechowuje. `g_min/g_max` są w metadanych, a
   `sigma_parallax_model` poza zakresem zwraca błąd.

---
Źródła:
- DuckDB 2.0: Parquet tips (`ROW_GROUP_SIZE` 122 880, pushdown po metadanych
  row-group), file formats (100 k–1 M wierszy/RG, 100 MB–10 GB/plik), Hive
  partitioning (pushdown kluczy, `hive_types`), partitioned writes
  (`partitioned_write_max_open_files` 100, ≥ 100 MB/partycja);
- pyarrow `write_dataset` (`max_rows_per_group` 1024·1024, `max_partitions` 1024);
- Gaia DR3 `gaia_source` (HEALPix poz. 12 = `source_id / 2³⁵`);
- El-Badry i in. 2021 (arXiv:2101.05282);
- GCNS (arXiv:2012.02061);
- model liczności: recenzje S1 r1/r2 (piksele ICRS) + przeliczenie na poz. 2/3
  (`scratchpad/s1/pix.py`).
