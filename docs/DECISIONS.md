# Dziennik decyzji

Jeden wpis na decyzję, najnowsze na górze. Format:
`## D-NNN · RRRR-MM-DD · tytuł` + **Decyzja**, **Dlaczego**, **Źródło**
(rozmowa, PR, recenzja), opcjonalnie **Zastępuje**. Decyzji się nie
usuwa — nieaktualną oznacza się wpisem, który ją zastępuje.

Sesje Claude Code: jeśli zmieniasz zakres, próg, metodę albo kontrakt
kolumn, dopisz wpis w tym samym PR. Jeśli nie jesteś pewien, czy to
decyzja — dopisz.

---

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
