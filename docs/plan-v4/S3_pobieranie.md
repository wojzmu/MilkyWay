# S3 — Pobieranie danych i manifest
Wersja: v3 · Etap: 1 (DR3; pełne pobranie gotowe do 18.11) i 2 (DR4 od 3.12, etapy A/B/C z S4)

## Cel
`query.py` pobiera z TAP pełną objętość ~1,25 kpc w kafelkach po zakresach
`source_id`. Kafelki są wyrównane do HEALPix poz. 3, więc pasują do każdej
partycji S1 (P ∈ {2, 3}). ADQL zawiera wyłącznie jawną funkcję selekcji:
zakres `source_id`, próg paralaksy i limit G. Cięcia jakości liczy kod.
Każdy zbiór ma manifest, z którego da się go odtworzyć.

Dwa poziomy implementacji:
- **pobieracz uproszczony** — ścieżka główna dla DR3, gotowy ok. 6.11;
- **pełny klient** (wznawianie UWS, split, backoff, atrapa z SIGKILL) —
  wymagany dopiero dla DR4.

Wszystkie pobrania DR3 dla S2, S4 i S5 kończą się **do 18.11**, czyli
≥ 7 dni przed wyłączeniem ESA (25.11, 12:00 CET).

## Zakres / poza zakresem
**W zakresie:**
- szablony ADQL i lista kolumn;
- próbka populacyjna (liczności dla S1/S3 i modele σ_ϖ, ν_eff dla S2);
- planer kafelków;
- oba poziomy klienta, weryfikacja i atomowy zapis kafelków;
- konfiguracja serwisów TAP;
- manifest (`dataset`, `fetch`);
- zbiory pomocnicze: „bliski” 20 pc, Hipparcos, zbiory S4 sprzed 25.11.

**Poza zakresem:**
- odległości, ZP i modele populacyjne jako obliczenia (S2);
- partycje i wybór P (S1);
- progi jakości (S2/S4);
- funkcja selekcji traserów (S5).

## Wejścia i wyjścia
**Konfiguracja:**
- `gaia_release`, tabele, serwisy TAP;
- `parallax_min_mas` = 0,5, `g_max_mag` = 19,0;
- `tile_alignment_level` = 3 (stałe, niezależne od `partition_level` S1);
- `max_active_jobs` = 3, `max_queued_jobs` = 3.

**Wyjście 1 — surowe kafelki** `raw/<release>/tile_<id>.parquet`:
- kolumny archiwum 1:1 + `healpix` (int64, `source_id >> 35`);
- wiersze posortowane po `source_id`;
- każdy kafelek mieści się w jednym pikselu poz. 3, a więc i poz. 2.

**Wyjście 2:**
- `state.json`, `manifest.json`;
- zbiory pomocnicze w `raw/<release>/aux/<nazwa>.parquet`, każdy z własnym
  wpisem `fetch`.

**Kolumny głównego zbioru (`gaiadr3.gaia_source`, 36):**
- `source_id, ra, dec, ra_error, dec_error, l, b, ecl_lat`;
- `parallax, parallax_error, pmra, pmra_error, pmdec, pmdec_error`;
- `ruwe, astrometric_params_solved, astrometric_excess_noise,
  visibility_periods_used, ipd_frac_multi_peak, ipd_gof_harmonic_amplitude,
  duplicated_source`;
- `nu_eff_used_in_astrometry, pseudocolour`;
- `phot_g_mean_mag, phot_bp_mean_mag, phot_rp_mean_mag, bp_rp,
  phot_bp_rp_excess_factor`;
- `radial_velocity, radial_velocity_error`;
- `teff_gspphot, distance_gspphot, distance_gspphot_lower,
  distance_gspphot_upper, ag_gspphot, ebpminrp_gspphot`.

Lista zawiera wszystkie wejścia S2 v3: `source_id, ra, dec, l, b, parallax,
parallax_error, phot_g_mean_mag, bp_rp, nu_eff_used_in_astrometry,
pseudocolour, ecl_lat, astrometric_params_solved, ruwe`.

## Decyzje
1. **Kafelki = przedziały `source_id`, zawsze wyrównane do poz. 3.**
   - `hp12 = source_id >> 35` (dokumentacja DR3); piksel poz. k to
     `source_id >> (35 + 2·(12−k))`.
   - Scalanie pikseli poz. 5 (przesunięcie 49) resetuje się co 16 pikseli,
     czyli na każdej granicy poz. 3 (przesunięcie 51).
   - Zagnieżdżenie: z `lo >> 51 == hi >> 51` wynika `lo >> 55 == hi >> 55`,
     więc plan pasuje do P = 2 i P = 3 i nie zależy od terminu decyzji S1.
   - Podział: na pół po granicy poz. 5, a pojedynczy piksel poz. 5 na 16
     pikseli poz. 7 (przesunięcie 45). Pola kafelka: `level, hp_first, hp_last`.
   - Uwaga: krzywa Z ma skoki na granicach bloków, więc kafelek to wycinek
     nieba, niekoniecznie spójny.
   - *Odrzucone:* `GAIA_HEALPIX_INDEX(...) = x` w `WHERE`; przedziały
     `random_index`; wyrównanie do P z S1 (zależność od cudzej decyzji, a
     zysk to tylko ~3× mniej kafelków).
   - Skutek: średnio ~3·10⁵ wierszy na piksel poz. 3 (2,3·10⁸ / 768), więc
     ~768 kafelków i podział tylko w gęstych pikselach płaszczyzny (gdy
     > `N_target` = 2·10⁶). Każdy job przegląda ~2,4·10⁶ wierszy tabeli
     (1/768). Narzut kolejki/UWS może dominować, więc mierzy go pilot.
2. **Funkcja selekcji: `parallax > 0.5 AND phot_g_mean_mag < 19`** (bez zmian
   względem v2).
   ```sql
   SELECT <36 kolumn> FROM gaiadr3.gaia_source
   WHERE source_id BETWEEN :lo AND :hi
     AND parallax > :parallax_min AND phot_g_mean_mag < :g_max
   ```
   **G < 19:**
   - bez limitu model daje ~8·10⁸ wierszy przy 0,5 mas, z limitem ~2,3·10⁸;
   - RC (G ≲ 16 nawet przy A_G ~ 5) i walec S4 T5 (d ≤ 1275 pc, M_G < 6 →
     G ≤ 16,5 + A_G) mają ≥ 2 mag zapasu;
   - viewer traci dalekie karły M o bezużytecznej σϖ;
   - 20 pc dostaje zbiór „bliski” bez limitu G.

   **Próg 0,5 mas — zapas deterministyczny.** S5 tnie na ϖ_c ≥ 0,8 mas,
   a S4 T5 na ϖ_c ≥ 0,784. Surowa ϖ = ϖ_c + zp, a zp_DR3 ∈ ~[−0,10; +0,05]
   (do sprawdzenia na danych, zad. 9). Każda gwiazda przyjęta przez S4/S5 ma
   więc ϖ ≥ 0,68 > 0,5. Próg wstępny nie zmienia ich próbek, a zapas 0,18 mas
   pokrywa nieznany zp DR4.
   - *Odrzucone:* `parallax_error < σ_max`, bo σϖ zależy od pokrycia
     skanowaniem, co daje selekcję zależną od kierunku.
   - Reguła awaryjna przy przekroczeniu budżetu czasu: najpierw G < 18,5,
     potem próg 0,6.
3. **Próbka populacyjna zamiast osobnego zapytania liczącego.**
   - Pobieramy `random_index < 18117098` (⌈N/100⌉, N = 1 811 709 771)
     **bez cięć ϖ i G**, czyli ~1,81·10⁷ wierszy.
   - Kolumny: `source_id, random_index, l, b, parallax, parallax_error,
     phot_g_mean_mag, bp_rp, astrometric_params_solved,
     nu_eff_used_in_astrometry, pseudocolour, ecl_lat`.
   - Rozmiar ~1,5–2 GB VOTable, poniżej 20 GB.
   - Dzielimy na 10 jobów po `random_index BETWEEN` (po ~1,8·10⁶ wierszy).
     Zapytanie jest proste i nie wymaga `GROUP BY` w ADQL.

   Co z niej wynika lokalnie, jednym kodem:
   - **S1/S3:** liczności po selekcji (ϖ > 0,5, G < 19) na pikselach
     poz. 5/3/2 i siatka próg × G × σ do protokołu. Skalowanie
     N / 18 117 098 = 99,99999.
     - Na piksel poz. 3 przypada średnio ~3000 wierszy próbki, czyli ±2%
       (Poisson); dla planu to wystarcza.
   - **S2 D12:** σ_ϖ(G, HEALPix 3) i ν_eff(BP−RP) **bez obciążenia
     selekcją S3** i w pełnym zakresie G 6–21.
     - Średnio ~390 gwiazd na komórkę (60 przedziałów G × 768 pikseli).
     - Jasne komórki (G < 10) są rzadkie, więc działa reguła zastępcza S2
       (G, |β|).
     - Jeśli S2 potrzebuje gęstszej siatki dla jasnych gwiazd, to dodatkowo
       `phot_g_mean_mag < 12` bez `random_index` (~3·10⁶ wierszy, do
       weryfikacji) jako drugi zbiór pomocniczy.
   - *Odrzucone:* zapytanie `GROUP BY` z v2. Ma ryzyko parsera (`GROUP BY 1,2`
     poza ADQL 2.0), nie daje S2 rozkładów i i tak wymagało próbnego przebiegu.
   - Indeks `random_index` w ESA **do weryfikacji**. Najpierw próbny job
     `random_index < 10000` z pomiarem czasu. Jeśli wygląda na pełny skan,
     pobieramy z AIP (indeks potwierdzony), bo identyczny DR3 to te same dane.
4. **Selekcja ≠ jakość — biała lista per szablon.**
   - `main`: `source_id, parallax, phot_g_mean_mag`.
   - `population`: `random_index`.
   - `cylinder_t5` (S4 etap B DR4): dodatkowo `b`, z warunkiem
     `parallax > 1000·COS(RADIANS(b))/R_max − 0.2`. Margines 0,2 mas działa jak
     zapas ZP z dec. 2.
   - `near`: `parallax`. `aux_*` (S4): biała lista zapisana w szablonie.

   Test parsuje każdy szablon. Kolumny jakości i `parallax_over_error` nigdy
   nie przechodzą.
5. **Limity ESA** (strona kwot „Collaborate” i komunikat z 14.10.2026):
   - konto zalogowane: async 120 min, wiersze bez limitu, 20 GB na wyniki,
     1 GB na tabele;
   - joby: **5 w wykonaniu + 50 w kolejce**, nadmiarowe są odrzucane;
   - konto anonimowe: 1 min i 50 000 wierszy, więc odpada.

   `max_active_jobs = 3` zostawia 2 sloty dla S4. Po pobraniu i weryfikacji
   każdy job jest usuwany (`deletejobs`).
6. **Budżet czasu z pomiaru.**
   - Warunek: `N_tiles · t_p90 / 3 ≤ 72 h`, czyli przy ~800 kafelkach
     t_p90 ≤ 16 min.
   - **Pilot: 10 kafelków**: 3 z |b| < 5° (w tym centrum Galaktyki),
     3 z 5–30°, 4 z wysokich |b|. Do przebiegu próbnego warunek liczymy
     z `t_max(pilot) × 1,5` zamiast t_p90.
   - Przebieg próbny (pierwsze ~40 kafelków pełnego pobrania) daje empiryczny
     t_p90 i ponowne sprawdzenie warunku.
   - Szacunek wstępny: przy t ≈ 3–10 min to ~13–44 h zegarowo. Transfer
     ~60–100 GB.
   - Jeśli warunek nie przechodzi: scalanie i tak jest ograniczone przez
     poz. 3, więc mniejszą liczbę jobów da tylko reguła awaryjna z dec. 2.
     Alternatywa to `max_active_jobs = 4` na czas, gdy S4 nie ma jobów.
7. **Pobieracz uproszczony = ścieżka główna DR3.**
   - Plan kafelków, pula 3 wątków, w każdym: zlecenie async → czekanie →
     pobranie → **ta sama funkcja weryfikacji co w pełnym kliencie**
     (dec. 10) → atomowy zapis → `deletejobs`.
   - Stan to tylko lista `verified` w `state.json`, wyprowadzana z plików na
     dysku i ich `content_hash`.
   - Po przerwaniu wszystko, co nie jest `verified`, jest zlecane od nowa.
     Joby osierocone na koncie usuwa krok sprzątania (`jobs/async` list +
     `deletejobs`).
   - Prosty backoff: 5xx i zerwanie → 3 próby co 1/5/15 min.
     Timeout/`OVERFLOW` → kafelek do listy ręcznej, a podział robi
     operator. Jawny `MAXREC`.
   - Ten sam pobieracz obsługuje zbiory pomocnicze (`kind = whole_query`).
   - *Odrzucone:* czekanie z danymi DR3 na pełny klient. Ten ma 4,5 d pracy
     i nie zmieści się przed 9.11 obok S1/S2/S4 (uwaga 1 recenzji r2).
8. **Pełny klient — wymagany przed etapem C DR4 (10.12).**
   - Stany `pending → submitted → completed_remote → downloaded → verified`
     oraz `failed_retryable / failed_permanent / split`.
   - Wznawianie przez odpytanie UWS (`job_url`), bez ponownych zleceń.
   - Full jitter `U[0, min(30 min, 30 s·2^n)]` z `Retry-After`, ≤ 6 prób.
   - Timeout i `OVERFLOW` → automatyczny `split` (dec. 1). 400 →
     `failed_permanent`. 401 → ponowne logowanie. Kwota → pauza.
   - `fetch_key` (wydanie, tabela, szablon, kolumny, progi,
     `tile_alignment_level`, plan) blokuje mieszanie konfiguracji.
   - Atrapę TAP/UWS da się testować bez archiwum, więc ten kod może powstawać
     także w przerwie 25.11–1.12.
9. **Harmonogram do 25.11** (dni robocze; S3 dzieli tydzień z S1/S2/S4):

   | Data | S3 | Joby (sloty) |
   |---|---|---|
   | pn 2.11 | job próbny `random_index < 10000`; konto, logowanie | 1 |
   | pn–wt 2–3.11 | próbka populacyjna (10 jobów) → liczności, plan | 3 |
   | wt 3.11 | pilot 10 kafelków (tymczasowy skrypt) → t_max, B/wiersz | 3 |
   | śr–pt 4–6.11 | pobieracz uproszczony: szablony, planer, weryfikacja, manifest (3,5 d prac → dociążenie, patrz ryzyka) | — |
   | czw–pt 5–6.11 | **joby S4 (lista S4 v2, 2–5) + „bliski” + Hipparcos**, przez pobieracz lub skrypt z tą samą weryfikacją | 2 (S4) |
   | pn–pt 9–13.11 | **pełne pobranie DR3 1,25 kpc**; partycje od najcięższych; S1 przetwarza przyrostowo | 3 |
   | pn 9.11 | T4 S4: JOIN z `external.gaiaedr3_distance` na 2–3 kafelkach z planu | 2 (S4) |
   | pn–śr 16–18.11 | dobieranie nieudanych kafelków, kontrola krzyżowa ESA/AIP, sprzątanie konta | ≤ 3 |
   | **śr 18.11** | **wszystkie zbiory DR3 `verified`** → bufor 7 dni | — |
   | 18–24.11 | bufor; pełny klient + atrapa (zad. 5, 8) | rezerwa |

   Joby S4 sprzed 25.11 (z S4 v2, „Lista pobrań DR3”), wszystkie jako
   zbiory pomocnicze z wpisem w manifeście:
   1. kwazary `gaiadr3.agn_cross_id` JOIN `gaia_source` z 5 wejściami L21,
      bez limitu G (~1,6·10⁶, jeden job);
   2. próbka LMC (stożek ~3°, `random_index`) z wejściami L21;
   3. JOIN z `external.gaiaedr3_distance` + `distance_gspphot*` dla 2–3
      kafelków planu (po 6.11);
   4. `gaiadr3.hipparcos2_best_neighbour` dla 20 pc;
   5. zachowane surowe VOTable: „bliski” i 2 kafelki (T7).

   Najpóźniejszy start pełnego pobrania przy zachowaniu bufora 7 dni:
   18.11 − T_full. Dla T_full = 67 h (800 kafelków × 15 min / 3) to
   **pt 13.11** — 4 dni rezerwy względem planowanego 9.11.
10. **Weryfikacja kafelka i hashe.**
    (a) `QUERY_STATUS = OK`, liczba sparsowanych wierszy = `nrows`.
    (b) `source_id ∈ [lo, hi]` i unikalne.
    (c) Każdy wiersz spełnia funkcję selekcji.
    (d) Liczność w `expected ± max(5√expected, 10%)` — rozbieżność to
        ostrzeżenie.

    Potem sortowanie → `.tmp` → fsync → rename.
    - **`content_hash_ids`**: SHA-256 posortowanych `source_id` (int64 LE)
      + liczba wierszy.
    - **`content_hash_values`**: SHA-256 kanonicznej tabeli, jak w S4 T7:
      - jawny schemat Arrow (typy z archiwum ESA, np. double → float64);
      - NaN → NULL, porządek po `source_id`;
      - Arrow IPC bez metadanych.
    - `sha256_file` sprawdza tylko integralność pliku.
    - Kafelek `whole_query`: bez kontroli zakresu; unikalność po kluczu
      zbioru (`hip`, `source_id`); liczność = `COUNT(*)` z serwera.
11. **Serwisy TAP i dostępność DR3 po 2.12.**

    | Serwis | Endpoint | Rola |
    |---|---|---|
    | ESA | `gea.esac.esa.int/tap-server/tap` | podstawowy; offline 25.11 12:00 → 2.12 12:00 |
    | AIP | `gaia.aip.de/tap` | zapas: pełna `gaiadr3.gaia_source` (153 kol., N wierszy jak ESA, indeksy na `source_id`, `parallax`, `random_index`); token; jawnie kolejka „2h”; 10 GB |
    | ARI | `gaia.ari.uni-heidelberg.de/tap` | do weryfikacji (kolumny; ograniczona dostępność po ataku 01.2026) |

    - Mieszanie serwisów po kafelkach jest dozwolone po kontroli `TOP 0`
      (typy po normalizacji do Arrow).
    - Kontrola krzyżowa: `content_hash_ids` równe. Wartości porównujemy
      z tolerancją: float64 względnie 10⁻¹², float32 10⁻⁶, NULL = NULL.
    - Czy DR3 zostaje w ESA po 2.12 — **do weryfikacji** (oczekiwane, bo ESA
      trzyma wszystkie wydania). Zapasem jest AIP.
    - Przekroczenie 25.11 nie niszczy więc danych. Przesuwa analizy offline
      z S4 G1b, bo brakujące kafelki wtedy pobieramy z AIP.
12. **Manifest — sekcje S3.**
    - `dataset`: `schema_version, dataset_id, created_utc, gaia_release`,
      commit + `dirty`, wersje pakietów.
    - `fetch`:
      - szablon dosłownie, kolumny z typami Arrow;
      - **funkcja selekcji** (`parallax_min_mas`, `g_max_mag`, wykluczone 2p
        i brak G);
      - kodowanie `source_id`, `tile_alignment_level = 3`, `partition_level`
        (kopia z S1);
      - `fetch_key`, hash próbki populacyjnej, N_target, t_p90 zmierzony;
      - `client` (`simple` / `full`);
      - kafelki `{tile_id, level, hp_first, hp_last, lo, hi, service, job_id,
        query_utc, rows, sha256_file, content_hash_ids, content_hash_values}`;
      - suma wierszy, liczba nieudanych (w zbiorze kompletnym 0).
    - Zbiory pomocnicze: osobne wpisy `fetch` (`population`, `near`,
      `hipparcos`, `s4_qso`, `s4_lmc`, `s4_bj`, `s4_hip_bn`).

## Zadania
1. **Próbka populacyjna (0,5 d, 2–3.11):** job próbny, 10 jobów, liczności
   na pikselach i siatka; oddanie do S2 D12 (σ_ϖ, ν_eff) i S1.
2. **Pilot 10 kafelków (0,5 d, 3.11):** t_max, B/wiersz VOTable i Parquet,
   `MAXREC`, `deletejobs`, czas zlecenia vs wykonania.
3. **Szablony + biała lista + test (0,5 d).** Do tego usunięcie szkicu
   `/mnt/attach/outputs/crossmatch_gaia_distances.sql`.
4. **Planer z wyrównaniem do poz. 3 (1 d).**
5. **Pełny klient: stan UWS, split, backoff (2 d, 16–24.11).**
6. **Weryfikacja, sortowanie, atomowy zapis, oba hashe (1 d).**
7. **Pobieracz uproszczony + manifest (1 d).**
8. **Atrapa TAP/UWS i test odporności pełnego klienta (1,5 d, do 1.12).**
9. **Pełne pobranie DR3 + raport (9–18.11):** rozkład zp na danych,
   kontrola krzyżowa ESA/AIP, sprzątanie konta.

Ścieżka do DR3: zad. 1–4, 6, 7 = **4,5 d** w oknie 2–6.11 (5 dni
roboczych, w tym czekanie na joby z zad. 1–2). Ścieżka do DR4: zad. 5, 8
= **3,5 d** w oknie 16.11–1.12.

## Kryteria akceptacji
- **Planer:** każdy kafelek spełnia `lo >> 51 == hi >> 51`. Test sprawdza
  też P = 2 (`>> 55`). Pokrycie `[0, 12·4¹²·2³⁵ − 1]` bez dziur i nakładek.
  Granice to wielokrotności 2⁴⁹, a po podziale 2⁴⁵.
- **Szablony:** każdy `WHERE` używa tylko kolumn z białej listy swojego
  szablonu.
- **Kolumny:** test porównuje listę z wejściami S2 v3.
- **DR3 (pobieracz uproszczony), do 18.11:**
  - wszystkie kafelki i zbiory pomocnicze `verified`, 0 duplikatów
    `source_id` globalnie;
  - suma wierszy = szacunek z próbki ×99,99999 ±1%, 0 jobów na koncie;
  - **test przerwania** (S4 G1a): zabicie procesu w trakcie pobierania i
    restart dają ten sam zbiór `content_hash_ids/values`, bez `.tmp`;
  - warunek czasu z dec. 6 sprawdzony na zmierzonym t_p90.
- **Kontrola krzyżowa** (przed 25.11): 3 kafelki z `COUNT(*)` serwera
  równym liczbie wierszy w pliku; 1 kafelek ESA vs AIP: równe
  `content_hash_ids`, wartości zgodne w tolerancji.
- **Pełny klient (przed 10.12):** atrapa z 30% błędów 500, zerwaniami,
  timeoutem, `OVERFLOW`, SIGKILL w trakcie zapisu i odpytywania. Po ≤ 3
  restartach hashe są równe przebiegowi wzorcowemu, a istniejące joby nie
  są zlecane ponownie. Aktywnych ≤ 3, w kolejce ≤ 3. `OVERFLOW` i timeout
  nigdy nie kończą się stanem `verified`.
- **Manifest** przechodzi walidację i wystarcza do powtórzenia pobrania.

## Ryzyka i otwarte pytania
- **Termin DR3.** Na ścieżce krytycznej jest 4,5 d prac S3 w oknie 2–6.11,
  obok zadań S1/S2/S4.
  - Rezerwa: pełne pobranie może ruszyć najpóźniej w pt 13.11 i nadal
    skończyć się przed 18.11 (dec. 9).
  - Zbiory S4 i populacyjny idą wcześniej, ręcznymi skryptami z tą samą
    weryfikacją.
  - Gdyby nie zdążyć do 25.11: AIP (dec. 11). Skutkiem jest opóźnienie
    G1b, nie utrata danych.
- **Liczność 2,3·10⁸ to model.** Rozstrzyga ją próbka populacyjna 3.11,
  zanim powstanie planer. Reguła awaryjna jest w dec. 2.
- **Indeks `random_index` w ESA** — do weryfikacji jobem próbnym. Zapas: AIP.
- **Narzut per job** przy ~800 małych kafelkach może dominować nad czasem
  wykonania — mierzy pilot. Najgorszy rozsądny przypadek: 15 min → 67 h,
  co mieści się w budżecie.
- **DR3 w ESA po 2.12** — do weryfikacji. AIP potwierdzony jako pełny zapas.
- **zp DR3 ∈ [−0,10; +0,05]** — sprawdzić na danych (zad. 9). Zapas
  0,18 mas jest duży w porównaniu z typowym |zp| ~0,03.
- **DR4:** kodowanie `source_id` i dostępność u partnerów do weryfikacji
  (S4, lista kontrolna 4 i 9). Plan B S4: kafelki po `ra/dec`.

## Zmiany w kontrakcie
1. **Manifest:** jeden `manifest.json` z sekcjami na segment (bez zmian).
   Nowe pola S3: `tile_alignment_level`, `client`, `content_hash_ids`,
   `content_hash_values`.
2. **Kafelki S3 → S1:** wyrównane do poz. 3 (spełniają P = 2 i P = 3), kolumny
   1:1 + `healpix`, posortowane po `source_id`.
3. **Funkcja selekcji `parallax > 0.5 AND phot_g_mean_mag < 19`** — do
   aktualizacji w innych segmentach:
   - **S1 v1:** dopisać G < 19 do opisu wejścia (l. 42–47; liczność 2–4·10⁸
     wynika teraz z limitu G, nie z samego progu) i do `dataset_id`
     (`gdr3_p0.5_g19_<data>`);
   - **S2 v3:** D12 l. 272 („próg S3 0,4 mas”) → 0,5;
   - **S4 v2:** l. 35 i T5 („ϖ > 0,4”) → 0,5. Zgodność T5 jest teraz
     deterministyczna: ϖ_c ≥ 0,784 ⇒ ϖ ≥ 0,68;
   - **S5:** G < 19 w funkcji selekcji (dla RC nieaktywne).
4. **Próbka populacyjna dla S2 D12** (`aux/population`, 1% `random_index` bez
   cięć ϖ i G). S2 buduje z niej σ_ϖ(G, HEALPix 3) i ν_eff(BP−RP), a nie
   z głównego zbioru. Do uzgodnienia z S2.
5. **Szablon `cylinder_t5`** dla S4 etap B DR4 z `b` na białej liście
   (przyjęte z S4 v2, Zmiany 3).
6. **Pełny klient wymagany dopiero dla DR4.** S4 G1a sprawdza na DR3 test
   przerwania pobieracza uproszczonego.

## Odpowiedź na recenzję (runda 2)
1. **[ISTOTNA] Termin zależny od pełnego klienta — przyjęte** (decyzja
   koordynatora).
   - (a) Pobieracz uproszczony jest ścieżką główną DR3, gotowy 6.11, a pełne
     pobranie rusza 9.11. Pełny klient powstaje 16.11–1.12 i jest wymagany
     przed etapem C DR4.
   - (b) Termin „wszystko `verified`” przesunięty na 18.11, czyli bufor
     7 dni.
   - (c) Liczby dni ujednolicone: 4,5 d do DR3 w oknie 5 dni roboczych,
     3,5 d do DR4. Najpóźniejszy start 13.11.
   - (d) Skutki niezdążenia: dane z AIP, opóźnienie G1b. DR3 w ESA po 2.12
     do weryfikacji.
2. **[DROBNA] Zależność od P — przyjęte.** Wyrównanie zawsze do poz. 3 i pole
   `tile_alignment_level = 3`. Test obejmuje oba P.
3. **[DROBNA] GROUP BY i `random_index` — przyjęte w innej formie.** Zapytanie
   liczące zastępuje pobranie próbki populacyjnej bez `GROUP BY`, a liczności
   liczymy lokalnie. Przed nim job próbny `random_index < 10000` sprawdza
   czas. Zapas to AIP z indeksem; tam dzielenie ani `GAIA_HEALPIX_INDEX` nie
   są potrzebne, bo `hp` liczymy lokalnie.
4. **[DROBNA] t_p90 z 3 kafelków — przyjęte.** Pilot ma 10 kafelków, w tym
   3 z płaszczyzny. Do przebiegu próbnego warunek liczymy z t_max × 1,5.
5. **[DROBNA] Obciążony model σ_ϖ — przyjęte.** Próbka populacyjna 1% bez
   cięć, z kolumnami S2, pobrana 2–3.11. Opcjonalnie jasne G < 12. Zmiana
   kontraktu 4 do uzgodnienia z S2.
6. **[DROBNA] content_hash bez wartości — przyjęte.** Osobne
   `content_hash_ids` i `content_hash_values` (kanoniczne Arrow IPC jak
   w S4 T7). Kontrola ESA/AIP porównuje wartości z tolerancją.
7. **[DROBNA] Wątek S1/S2 — przyjęte.** Odwołania poprawione na S2 v3.
   Konkretne linie do zmiany w S1, S2, S4 i S5 są w „Zmiany w kontrakcie” 3.
   Zgodność liczności S1 była przypadkowa — zapisane.
8. **[DROBNA] Joby S4 — przyjęte.** Lista 5 jobów S4 jest w dec. 9
   (5–6.11 oraz 9.11 dla JOIN-a z BJ), w 2 slotach poza S3, jako zbiory
   pomocnicze w manifeście.
