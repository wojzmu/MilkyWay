# Dziennik decyzji

Jeden wpis na decyzję, najnowsze na górze. Format:
`## D-NNN · RRRR-MM-DD · tytuł` + **Decyzja**, **Dlaczego**, **Źródło**
(rozmowa, PR, recenzja), opcjonalnie **Zastępuje**. Decyzji się nie
usuwa — nieaktualną oznacza się wpisem, który ją zastępuje.

Sesje Claude Code: jeśli zmieniasz zakres, próg, metodę albo kontrakt
kolumn, dopisz wpis w tym samym PR. Jeśli nie jesteś pewien, czy to
decyzja — dopisz.

---

## D-024 · 2026-10-31 · Pył z mapy Edenhofer 2024 (M5, schemat v3)
**Decyzja:**
- Mapa: `mean_and_std_healpix.fits` (Zenodo 8187943, 3,25 GB, MD5
  10c823a5…), tylko średnia. Plik czytamy sami (`milkyway/dust.py`), nie
  przez `dustmaps.edenhofer2023` (D-003): dustmaps wymaga healpy, a healpy
  nie ma kół na Windows. Interpolacja HEALPix: `astropy-healpix`
  (dwuliniowa, 4 piksele). E sumujemy na **granicach** powłok i bierzemy
  liniowo w odległości (dokładne przy stałej gęstości w powłoce); dustmaps
  liczy na środkach powłok, w log E. Bliżej niż 68,6 pc: E(68,6)·d/68,6
  (`dust_flag = inner`), dalej niż 1248,1 pc: E z brzegu (`beyond_map`).
  Plik opisuje całkę wewnętrzną jako „within 68.8 pc” (środek pierwszej
  powłoki), a pierwsza granica to 68,62 pc; traktujemy ją jako E(68,62).
- Jednostki: E Zhang, Green & Rix 2023, A_λ = E·R(λ); krzywa
  `extinction_curve.txt` (Zenodo 7811871), poniżej 392 nm przedłużona
  liniowo. A_G, A_BP, A_RP z tabeli (Teff, E): pasma EDR3 (SVO
  GAIA3.G/Gbp/Grp) × Planck(Teff) × λ, z nieliniowością w E. Teff
  z `teff_from_bprp(bp_rp0)`, iteracja do 1e-4 mag; bez koloru 5800 K.
  Dane wejściowe w `milkyway/dust_data/`.
- Schemat v3: `dust_e`, `a_g`, `e_bp_rp`, `bp_rp0`, `abs_g0`,
  `dust_flag`. `rgb_*`/`teff_color` w katalogu zostają z koloru
  obserwowanego; eksport viewera barwi wg `bp_rp0`, a `--abs-mag-max`
  tnie po `abs_g0` (D-023: mapa tracers 913 280 → 1 269 275 gwiazd).
  `--build` wymaga mapy albo `--no-dust`.
**Dlaczego:** pył zmienia kolory i M_G, a „promienie” w widoku z góry
okazały się cieniami obłoków: przy l = 20–40° (Szczelina Orła) jest
o połowę mniej gwiazd 600–1200 pc niż przy l = 0–10°, przy medianie
A_G 1,2 wobec 0,6. Kontrola: A_G/A_V = 0,86 i A_G/E(BP−RP) = 1,85 dla
5800 K; na 1,82 mln gwiazd z `ag_gspphot` mediana 0,172 (nasza) wobec
0,173 (Gaia), korelacja 0,81. W 1,25 kpc mediana A_G = 0,18 mag, 5,1%
gwiazd ma A_G > 1. Szczegóły: `docs/JAK_LICZYMY_PYL.md`.
**Źródło:** sesja Claude Code (M5), 31.10.2026.

## D-023 · 2026-10-31 · Mapa „disc tracers” (M_G ≤ 2), format v2, hosting
**Decyzja:**
- Drugi eksport viewera: wszystkie gwiazdy w 1,25 kpc z M_G ≤ 2
  (913 280, bez przerzedzania; `--abs-mag-max 2 --viewer-target 0`).
- `points.bin` w wersji 2: pozycje int16 w jednostkach
  `position_scale_pc` = 1250/32767 ≈ 0,038 pc (11 B/gwiazdę zamiast 17;
  pełna mapa 25,6 → 16,6 MB). Viewer czyta v1 i v2.
- Wpis w `datasets.json` może mieć pełny URL (inny host). Kandydat na
  hosting: repozytorium dataset na Hugging Face (sprawdzone 31.10: CORS
  i Range 206 przez przekierowanie na CDN). Odrzucone: GitHub Releases
  (brak CORS, sprawdzone), Git LFS na Pages (Pages nie serwuje LFS),
  Google Drive (zwykłe linki bez CORS; Drive API wymaga klucza w kodzie
  strony i ma limity pobrań). Konto i wgranie: użytkownik.
**Dlaczego:** w pełnej mapie gęstość wyznacza limit G < 15 (przy Słońcu
19× gęściej niż przy 1–1,25 kpc), co przykrywa kształt dysku. Gwiazdy
z M_G ≤ 2 są widoczne w całej objętości (μ = 10,5 przy 1250 pc, zapas na
pył), więc ich rozkład pokazuje dysk: w walcu R < 800 pc liczba na 100 pc
wysokości spada z 15 771 do 917 do |z| = 800 pc.
**Źródło:** rozmowa w sesji Claude Code, 31.10.2026.

## D-022 · 2026-10-31 · ESA i AIP zwracają te same dane (M2 T6)
**Decyzja:** kafelki z AIP traktujemy jako równoważne archiwum ESA; ESA
pozostaje zapasem bez potrzeby osobnego pobrania (OP-1: punkt „zgodność
wyniku” zamknięty dla DR3).
**Dlaczego:** kafelki 111 i 109 (30 055 + 30 068 wierszy) pobrane z ESA
(sync, VOTable binarny) mają te same `source_id` i identyczne bity we
wszystkich 35 pozostałych kolumnach co nasze pliki z AIP. 31.10 ESA rano
zwracało 503, po południu działało (~80 s na zapytanie).
**Źródło:** porównanie w sesji Claude Code, 31.10.2026.

## D-021 · 2026-10-31 · Eksport binarny dla viewera (M4)
**Decyzja:**
- `milkyway/viewer_export.py`, `--dataset ID --export-viewer DIR`: jeden plik
  bez sześcianów 250 pc (plan 1.0 §2): `points.bin` (nagłówek `MWPT` 16 B,
  SoA: xyz float32, RGBU uint8, **kod klasy uint8** — dodatek wobec S1
  dec. 11, żeby viewer zachował kolory i filtr kategorii; 17 B/gwiazdę),
  `details.bin` (`MWDT`, rekordy 24 B jak w S1: id, r_lo, r_hi, G, BP−RP;
  viewer czyta jeden rekord przez HTTP Range), `index.json`.
- Cięcie `dist_pc ≤ 1250`, przerzedzenie `splitmix64(id) < f·2⁶⁴`, jedno f
  wszędzie (S1 dec. 12), cel 1,5 mln; gwiazdy z G < 6 zawsze (6 743) i na
  początku pliku, reszta po haszu, więc każdy prefiks to próba losowa.
  Wynik: 1 505 769 z 17 198 645 gwiazd (f = 0,0872); 25,6 + 36,1 MB.
- Pliki eksportu są generowane i git-ignorowane (`web/public/map_*/`);
  wdrożenie na GitHub Pages wymaga osobnej decyzji (rozmiar w repo).
**Dlaczego:** viewer z obiektem JS na gwiazdę i CSV nie udźwignie 1,5 mln
punktów; filtrowanie w shaderze (uniformy) nie przebudowuje geometrii.
**Źródło:** plan M4 w sesji Claude Code, 31.10.2026.

## D-020 · 2026-10-31 · Odległości i katalog M3 (schemat v2)
**Decyzja:**
- **Zero-point:** `lindegren2021_clamped` wg v4 S2 D5 (pakiet
  `gaiadr3-zeropoint` 0.1.0, przycięcie do wnętrza zakresu z flagą,
  fallback −0,017 mas). ϖ_c = ϖ − zp; `parallax_mas` zostaje surowa.
- **Odległość:** inwersja ϖ_c dla **wszystkich** wierszy; `dist_pc` =
  1000/ϖ_c (mediana), `r_lo_pc`/`r_hi_pc` = 1000/(ϖ_c ± σ) (kwantyle
  15,87/84,13 %, `r_hi_pc` puste, gdy ϖ_c − σ ≤ 0). ϖ_c/σ ≤ 5 →
  `dist_flag = low_snr`, wiersz zostaje. EDSD (v4 S2 D3) odkładamy;
  odstępstwo od v4 D4 (tam f > 0,1 → `inversion_invalid`).
- **Schemat v2:** dochodzą `parallax_error`, `parallax_zp_mas`, `zp_origin`,
  `ruwe`, `r_lo_pc`, `r_hi_pc`, `dist_origin`, `dist_flag`,
  `xgc/ygc/zgc_pc` (preset `v4.0`). `r_med_pc` nie jest osobną kolumną —
  `dist_pc` jest medianą (zastępuje zapowiedź aliasu z D-015). `abs_g` z ϖ_c.
- **Zasięg:** katalog trzyma cały pobrany zbiór (23 373 946 wierszy);
  cięcie do 1,25 kpc robi eksport (M4). Cięć jakości nie stosujemy.
- **Hipparcos:** wiersz HIP wchodzi tylko bez odpowiednika 5p/6p. Najpierw
  `hipparcos2_best_neighbour` (97 984 gwiazd → Gaia), potem dla 19 247
  pozostałych (test G < 15 na V, gdy B−V nie daje G) propagacja epoki i
  dopasowanie do wszystkich kafelków: < 0,5″ zawsze; < **2″** (nie 1″ jak
  v4 D10) przy |ΔG| < 1 mag; < 3″ przy paralaksie zgodnej w 3σ i
  |ΔG| < 2,5 (składnik układu podwójnego). 17 158 dopasowanych (41 tylko
  przez paralaksę), 2 089 zostaje (1 009 z `low_snr`, 117 z G < 3, 47 bez G). Wiersze Gai dostają `hip` z
  `best_neighbour` albo z dopasowania pozycyjnego (113 635; numer używany
  raz). Katalog HIP to `public.hipparcos` (ESA 1997),
  jak w starym pipeline'ie, nie Hipparcos-2.
**Dlaczego:** pomiar na pobranych danych 31.10: ϖ/σ > 5 dla 99,2%
wierszy, więc EDSD zmienia obraz tylko dla ~0,8%. Samo `best_neighbour`
dałoby ~17 tys. zdublowanych gwiazd. Próbka 40 zachowanych HIP (G ≥ 6,
stożki w AIP): 36 ma w Gai tylko rozwiązanie 2p (Hipparcos jest jedynym
źródłem paralaksy), 2 miały odpowiednik 5p w 1,17–1,26″ (stąd 2″), 1 to
gwiazda Gai z ϖ = 0,28 mas spoza selekcji — takich duplikatów (~2,5%)
offline nie wykryjemy. Próg 0,5″ bez warunku na G, bo przeliczenie V → G
zawodzi dla czerwonych karłów (Proxima weszłaby podwójnie). Test 60 pc
(D-013, `tests/test_reference.py`): te same 58 931 gwiazd Gai z paralaksą
bit w bit, z 2 585 HIP brak 10 układów podwójnych, które stary katalog miał
podwójnie, i są 2 gwiazdy, które stary kod zgubił; odległości różnią
się tylko o zero-point (4,0% poza 3 połówkami przedziału, każda z
|zp|/σ > 2,99). T6 (ESA vs AIP) odłożone: ESA 31.10 zwracało 503. Skutek korekty: mediana ϖ rośnie o 3,2%, w
1,25 kpc jest 17,20 mln gwiazd zamiast 16,44 mln przy surowej ϖ.
Progi 3″/3σ/2,5 mag i test G na V dodane po przeglądzie kodu (Opus):
bez nich ginęło 59 gwiazd HIP bez B−V, a układy podwójne wchodziły dwa razy.
**Źródło:** plan M3, odpowiedzi użytkownika i przegląd kodu w sesji Claude
Code, 31.10.2026.

## D-019 · 2026-10-31 · Kształt pobrania M2
**Decyzja:**
- Kafelek = piksel HEALPix poz. 2 (`source_id` od `k << 55` do
  `((k+1) << 55) − 1`), 192 kafelki; wynik z AIP wprost w Parquet,
  36 kolumn 1:1 z archiwum (`milkyway/raw.py`, w tym wejścia ZP).
- Kafelek jest zapisywany tylko po weryfikacji; najsilniejsza kontrola to
  liczba wierszy = COUNT z D-011. Manifest pobrania powstaje dopiero, gdy
  są wszystkie kafelki. Zbiór w schemacie katalogu buduje M3.
- 2 zapytania naraz w AIP (serwis anonimowy); joby usuwane po pobraniu.
- Hipparcos w 1.0: tak, jako zbiór pomocniczy (katalog + `best_neighbour`
  z kolumnami odpowiednika w Gai); scalenie w M3 (do katalogu tylko HIP bez
  odpowiednika 5p/6p).
- FLAME (`mass_flame`, `age_flame`): pomijamy w 1.0 (puste kolumny).
- Nazwy SIMBAD: w M4, tylko dla jasnych gwiazd.
- Pobieranie uruchamia użytkownik; Claude czyta tylko podsumowanie (koszt).
**Dlaczego:** pilot 31.10 — najgęstszy kafelek (462 780 wierszy) w 88 s,
82,6 MB, 178 B/wiersz; całość ~4,2 GB i ~1–1,5 h. Limit AIP to 5·10⁶
wierszy na job, ~10× powyżej największego kafelka.
**Źródło:** plan M2 zatwierdzony w sesji Claude Code, 31.10.2026.

## D-018 · 2026-10-31 · Twardsze kontrole magazynu po przeglądzie M1
**Decyzja:**
- `open_catalog` odmawia zbioru o innej `schema_version` albo liście
  kolumn niż kod, z obcym plikiem w `catalog/` i z plikiem o innym
  schemacie; czytelnicy (DuckDB, pyarrow) czytają tylko listę plików z
  manifestu, nigdy glob.
- `write_dataset(expected_partitions=…)`: brak lub nadmiar partycji
  blokuje zapis manifestu; lista trafia do manifestu. M2 podaje 192
  piksele z `docs/data/dr3_g15_hpx2_counts.csv`.
- `hip` unikalny w całym zbiorze (kontrola między kafelkami).
- `validate` odrzuca ±inf, `healpix` spoza [0, 12·4¹²) i `healpix`
  wiersza Hipparcosa niezgodny z (ra, dec).
- `dataset_id`: tylko `[A-Za-z0-9._-]`, bez `.`, `..` i `reference`;
  eksport CSV ograniczony do 5·10⁵ wierszy (S1 dec. 10).
**Dlaczego:** przegląd gałęzi `m1-magazyn` odtworzył m.in. zdublowane
gwiazdy przy obcym pliku w `catalog/`, ciche nulle po zmianie schematu i
kasowanie `*.tmp` poza zbiorem przy `--dataset-id ..`.
**Źródło:** przegląd kodu (subagent) i poprawki, 31.10.2026.

## D-017 · 2026-10-31 · HATS (LSDB) jako zapas pobierania, nie główne źródło
**Decyzja:** M2 pobiera przez TAP z AIP (D-012). Kopia Gaia DR3 w formacie
HATS (`https://linea.data.lsdb.io/hats/gaia_dr3`, Parquet w pikselach
HEALPix, 153 kolumny, 1,81·10⁹ wierszy) jest trzecim, niezależnym od
serwisów TAP źródłem awaryjnym.
**Dlaczego:** pliki HATS są posortowane po `source_id`, więc statystyki
row-group nie odcinają G < 15; nasze 21 kolumn to ~107 B/wiersz, czyli
~190 GB transferu wobec ~2,5 GB z TAP (filtr po stronie serwera). Zaleta:
statyczne pliki HTTP, bez kolejek i awarii TAP, wznawialne. Kopie na
Hugging Face sprawdzone 31.10: `astro-legacy-archive/gaia-dr3-source` w
trakcie wgrywania, `MultimodalUniverse/gaia` to okrojony podzbiór.
**Źródło:** pomiar stopki partycji HATS w sesji Claude Code, 31.10.2026.

## D-016 · 2026-10-31 · Uproszczona integralność magazynu w 1.0
**Decyzja:** manifest trzyma `row_counts` i SHA-256 bajtów każdego pliku
Parquet; pełny `canonical_hash` (S1 dec. 7, niezależny od wersji Arrow)
odkładamy do przejścia na DR4.
**Dlaczego:** w 1.0 budujemy i czytamy na jednej maszynie; hash plików
wykrywa podmianę i niekompletność za ułamek kosztu (~15 min zamiast ~0,5 d).
Kosztem jest to, że hash zmieni się po aktualizacji pyarrow.
**Źródło:** rozmowa w sesji Claude Code (plan M1), 31.10.2026.

## D-015 · 2026-10-31 · Schemat magazynu 1.0 (wersja 1)
**Decyzja:** `milkyway/schema.py` to podzbiór schematu v2 z S1: obecne
kolumny katalogu plus `source_id` (int64), `hip` (int32), `healpix`
(int64, NESTED poz. 12). Odstępstwa od v4: `star_id` zostaje w formacie
pipeline'u (`Gaia DR3 <id>` / `HIP <n>`, nie `gdr3:<id>`); `dist_pc` jest
zapisywaną kolumną do M3 (potem alias `r_med_pc`); partycje poz. 2 (D-011).
Kolumny M2/M3 dochodzą z podbiciem `SCHEMA_VERSION`.
**Dlaczego:** viewer i stare CSV używają obecnego `star_id`; zmiana formatu
nic nie daje w 1.0, a psuje porównanie z katalogiem referencyjnym.
**Źródło:** zadanie T1 planu M1, 31.10.2026.

## D-014 · 2026-10-31 · Fit wysokości skali w 1.0 tylko dla M_G ≤ 6
**Decyzja:** okno CMD orientacyjnego fitu (M5) to karły ciągu głównego
z M_G ≤ 6 (G i wczesne K), nie całe G/K.
**Dlaczego:** przy `g_max = 15` próbka w walcu R < 250 pc, |z| ≤ 450 pc
(odległość do ~515 pc, μ = 8,56, A_G ≲ 0,3) jest kompletna tylko do
M_G ≈ 6,1. Słabsze karły K ubywałyby z |z| przez limit jasności i
zaniżałyby h.
**Źródło:** przegląd planu po pomiarze liczności (D-011), 31.10.2026.

## D-013 · 2026-10-31 · Test zgodności 60 pc przy cięciach starego pipeline'u
**Decyzja:** porównanie z katalogiem referencyjnym robimy z nowym
pipeline'em bez limitu G i z cięciami starego (`parallax_over_error > 10`,
`ruwe < 1.4`, `parallax > 1000/60`); `g_max` musi więc dać się wyłączyć.
Wzorcem jest zamrożona kopia `nearby_stars_60.0pc.csv` w `data/reference/`
(SHA-256 507cd00f717edb4a52e57d231e5d922750de6b9e428bb8a70daf6174cb429c15, 61 516 wierszy; kopia z 31.10.2026).
**Dlaczego:** stary katalog zawiera słabe karły M z G > 15 i stosuje cięcia
jakości, których selekcja 1.0 (D-008) nie ma; bez wyrównania test różniłby
się z konstrukcji.
**Źródło:** przegląd `milkyway/query.py` i planu, 31.10.2026.

## D-012 · 2026-10-31 · AIP głównym serwisem pobierania DR3
**Decyzja:** pobieracz M2 celuje w `gaia.aip.de/tap` (async, `QUEUE=2h`),
ESA jest zapasem. Termin 25.11 przestaje być twardy.
**Dlaczego:** 31.10 AIP przyjęło anonimowo kolejkę 2 h i policzyło całą
selekcję w 5,5 min; tabela ma wszystkie 153 kolumny `gaia_source`. ESA tego
dnia dwa razy zawiodło (HTTP 500, timeout). AIP działa też w czasie
wyłączenia ESA 25.11–2.12.
**Źródło:** zapytania testowe w sesji Claude Code, 31.10.2026.

## D-011 · 2026-10-31 · Zmierzona liczność selekcji 1.0; P = 2
**Decyzja:** `parallax > 0.5 AND phot_g_mean_mag < 15` w DR3 to
**23 371 857** wierszy w 192 pikselach poz. 2 (maks. 462 780, mediana
83 738; `docs/data/dr3_g15_hpx2_counts.csv`). Partycje i kafelki pobierania
na poziomie 2.
**Dlaczego:** maksimum jest ~6,5× poniżej progu 3 mln z S1 dec. 1. Plan v1
zakładał zbiór „o rząd–dwa wielkości” mniejszy niż G < 19; faktycznie ~8×.
Skutki (czas pobrania w godzinach, przerzedzenie ~6% w viewerze, kolumny ZP
w pobraniu) opisuje `PLAN_MAPA_1.0.md` §2.
**Źródło:** COUNT … GROUP BY piksel poz. 2 w AIP, 31.10.2026.

## D-010 · 2026-10-31 · Katalog referencyjny to 60 pc, nie 20 pc
**Decyzja:** testy zgodności „nowy pipeline vs stary" robimy na domyślnym
katalogu `MAX_DIST_PC` = 60 pc. Wzmianki o „katalogu 20 pc" w planie v4
(`docs/plan-v4/`, zwłaszcza S2 i S4 T1) czytamy jako katalog referencyjny.
**Dlaczego:** plan powstał na podstawie `Dataset.md`, który opisuje próbkę
20 pc; `CLAUDE.md` i kod mają domyślnie 60 pc.
**Źródło:** przegląd `CLAUDE.md` przy dodawaniu planu do repo, 31.10.2026.

## D-009 · 2026-10-31 · Zakres: najpierw „Mapa 1.0"
**Decyzja:** realizujemy `docs/PLAN_MAPA_1.0.md` (mapa 3D w ~1,25 kpc,
orientacyjna wysokość skali). Plan v4 (`docs/plan-v4/`) zostaje bez zmian
jako praca na później.
**Dlaczego:** plan v4 to ~60 dni pracy (poziom publikacji), za dużo dla
jednej osoby; sprzęt nie jest ograniczeniem.
**Źródło:** rozmowa w projekcie claude.ai „MilkyWay", 31.10.2026.

## D-008 · 2026-10-31 · Funkcja selekcji z parametrem jasności
**Decyzja:** `parallax > 0.5 AND phot_g_mean_mag < g_max`; w 1.0
`g_max = 15`, w pełnym zbiorze `g_max = 19`. Próg i `g_max` są w
manifeście.
**Dlaczego:** bez limitu jasności ~73% wierszy to dalekie słabe gwiazdy,
które przeszły próg paralaksy przez szum.
**Źródło:** plan v4, recenzja S1 r1, U2.

## D-007 · 2026-10-31 · Repozytorium jest źródłem prawdy dla ustaleń
**Decyzja:** plan i decyzje żyją w `docs/` repozytorium; projekt claude.ai
czyta je przez integrację GitHub.
**Dlaczego:** Claude Code czyta `CLAUDE.md` i importowane pliki
automatycznie; jedna kopia nie rozjedzie się z drugą.
**Źródło:** rozmowa w projekcie claude.ai, 31.10.2026.

## D-006 · 2026-10-30 · Fit dysku w przestrzeni paralaks (pomiar naukowy)
**Decyzja:** do pomiaru wysokości skali model dopasowujemy do paralaks, nie
do odległości z priora. Estymator odległości służy viewerowi i statystyce
opisowej.
**Dlaczego:** izotropowy prior EDSD zawyżał h (symulacja: 342 pc przy
prawdziwych 300 pc).
**Źródło:** plan v4, recenzja S2 r1. W 1.0 nieużywane (orientacyjny fit).

## D-005 · 2026-10-30 · Korekta zero-pointu we wszystkich gałęziach
**Decyzja:** na surowej paralaksie, `gaiadr3-zeropoint` z przycięciem do
wnętrza zakresu (`lindegren2021_clamped`); dla DR4 nigdy model DR3.
**Źródło:** plan v4, S2.

## D-004 · 2026-10-30 · Magazyn Parquet + DuckDB
**Decyzja:** Parquet (zstd) jako źródło prawdy, DuckDB do zapytań, FITS
tylko jako eksport, manifest zapisywany na końcu ze statusem `complete`.
Partycje HEALPix z `source_id` (1.0: poziom 2; pełny zbiór: poziom 3).
**Źródło:** plan v4, S1.

## D-003 · 2026-10-30 · Mapa pyłu Edenhofer 2024
**Decyzja:** `dustmaps.edenhofer2023` (69–1250 pc), średnia mapy w ścieżce
głównej; objętość etapu 2 dopasowana do zasięgu mapy (1,25 kpc).
**Źródło:** plan v3/v4, S5.

## D-002 · 2026-10-30 · Jedno wydanie Gai naraz
**Decyzja:** nie mieszamy katalogów kluczowanych po `source_id` z różnych
wydań; przejście DR3 → DR4 to zmiana konfiguracji plus ponowna walidacja.
**Dlaczego:** identyfikatory źródeł nie są gwarantowane między wydaniami.
**Źródło:** review planu v2.

## D-001 · 2026-10-30 · Współrzędne i stałe
**Decyzja:** preset astropy `Galactocentric` `v4.0` (8,122 kpc; 20,8 pc),
pozycje w pc (`x_pc…`, `xgc_pc…`), `z_ref = 20,8 pc`.
**Źródło:** plan v4, S2, U11.
