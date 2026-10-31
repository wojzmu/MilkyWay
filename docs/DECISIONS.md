# Dziennik decyzji

Jeden wpis na decyzję, najnowsze na górze. Format:
`## D-NNN · RRRR-MM-DD · tytuł` + **Decyzja**, **Dlaczego**, **Źródło**
(rozmowa, PR, recenzja), opcjonalnie **Zastępuje**. Decyzji się nie
usuwa — nieaktualną oznacza się wpisem, który ją zastępuje.

Sesje Claude Code: jeśli zmieniasz zakres, próg, metodę albo kontrakt
kolumn, dopisz wpis w tym samym PR. Jeśli nie jesteś pewien, czy to
decyzja — dopisz.

---

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
(SHA-256 dopisany przy jej utworzeniu).
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
