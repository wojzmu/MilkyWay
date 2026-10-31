# Plan zmian v4 — mapa 3D Drogi Mlecznej (indeks)

Wersja 4 (31.10.2026). Zastępuje plan v3. Plan jest podzielony na pięć
segmentów. Każdy przeszedł pętlę: agent planujący pisał wersję, niezależny
agent weryfikujący ją recenzował (fakty sprawdzał w sieci, liczby własnymi
rachunkami), maksymalnie trzy rundy. Ten dokument to indeks: cele, status
segmentów, **wiążące uzgodnienia między segmentami** (nadrzędne wobec tekstu
segmentów), harmonogram zbiorczy i dziennik weryfikacji.

---

## 1. Etapy

| Etap | Cel | Dane | Kiedy |
|---|---|---|---|
| 1 | Pipeline gotowy do skali galaktycznej, sprawdzony na DR3 | Gaia DR3 | teraz → 1.12 |
| 2 | Pomiar spłaszczenia dysku w ~1,25 kpc wokół Słońca | Gaia DR4 + mapa pyłu Edenhofer 2024 | 2.12 → ~koniec grudnia |
| 3 | Większa skala, inne źródła danych | DR4 + inne katalogi | po etapie 2 (backlog, §6) |

**Kryterium sukcesu etapu 2 (zmienione w v4, patrz U1):** fit odtwarza na
mockach wartości wejściowe (h ±2–3%, z☉ ±2 pc), a na danych wysokość skali
w jednoskładnikowej mierze h_1 mieści się w obwiedni modeli literaturowych
(265–395 pc). Wartości h_thin i z☉ na danych są raportowane z budżetem
systematyki; przedział testowy h_thin zostaje przeliczony tą samą procedurą
co h_1.

## 2. Segmenty

| ID | Plik | Zakres | Status |
|---|---|---|---|
| S1 | `S1_magazyn_i_viewer.md` | Parquet + DuckDB, partycje HEALPix poz. 3, manifest, format binarny viewera | v3, zaakceptowany |
| S2 | `S2_odleglosci.md` | korekta zero-pointu, estymatory odległości, funkcje dla fitu w paralaksach, współrzędne, Hipparcos | v3, zaakceptowany |
| S3 | `S3_pobieranie.md` | kafelkowanie zapytań, funkcja selekcji, pobieracz DR3/DR4, próbka populacyjna | v3, zaakceptowany |
| S4 | `S4_walidacja_i_DR4.md` | testy regresji, próba generalna T5, bramki go/no-go, przejście na DR4 | v3, uwaga istotna zamknięta w U8 |
| S5 | `S5_pomiar_dysku.md` | pył, selekcja red clump, fit w przestrzeni paralaks, kryteria naukowe | v3, uwagi istotne zamknięte w U1 |

W repozytorium pliki segmentów leżą w `docs/plan-v4/` (w projekcie claude.ai: `claude/plan_v4/`). Sekcje
segmentów „Odpowiedź na recenzję" dokumentują, skąd wzięły się decyzje.

## 3. Najważniejsze zmiany względem planu v3

1. **Fit dysku w przestrzeni paralaks (forward modelling).** Izotropowy prior
   odległości (EDSD) zawyżał wysokość skali — w symulacji do 342 pc przy
   prawdziwych 300 pc. Wszystkie cięcia zależne od odległości są przedziałami
   skorygowanej paralaksy ϖ_c. Estymator odległości zostaje do viewera i
   statystyk opisowych (S2, S5).
2. **Funkcja selekcji: `parallax > 0.5 AND phot_g_mean_mag < 19`.** Bez limitu
   jasności ~73% wierszy to dalekie słabe gwiazdy, które przeszły próg tylko
   przez szum paralaksy. Z limitem: ~1,9·10⁸ wierszy (model, potwierdzi próbka
   populacyjna 2–3.11). Red clump w tej objętości ma G ≈ 9–14 (S3, S1).
3. **Magazyn: HEALPix poziomu 3 (768 partycji)**, największa ~1,5 mln wierszy;
   budowa kafelkami S3, manifest zapisywany jako ostatni ze statusem
   `complete` (S1). Plan v3 błędnie podawał 48–192 partycje dla poz. 2–3.
4. **Archiwum ESA jest wyłączone 25.11 12:00 → 2.12 12:00 CET** (komunikat
   ESA z 8.10.2026). Wszystkie dane DR3 pobieramy przed 25.11; analizy idą
   offline. Limit: 5 jobów wykonywanych równolegle + kolejka 50 (14.10.2026).
5. **Zero-point paralaksy we wszystkich gałęziach** na surowej paralaksie,
   z przycięciem do zakresu pakietu (`lindegren2021_clamped`); dla DR4 nigdy
   model DR3 — oficjalna recepta albo kwazary (S2, S4).
6. **Mapa pyłu Edenhofer 2024 w etapie 2** (`dustmaps.edenhofer2023`,
   69–1250 pc); średnia mapy w ścieżce głównej, 12 próbek posterioru jako
   systematyka (S5).
7. **Próba generalna T5 na DR3** (karły G/K w walcu R < 250 pc) jako niezależny
   punkt odniesienia dla S5 (S4).

## 4. Uzgodnienia między segmentami (wiążące)

Tam, gdzie tekst segmentu mówi inaczej, obowiązuje ten punkt.

**U1. Kryteria naukowe S5 (zamyka uwagi istotne 1–2 z recenzji S5 r3).**
- h_1 ∈ [265; 395] pc pozostaje testem pipeline'u (obwiednia tabeli modeli).
- Przedział testowy h_thin (D10) **przeliczyć tą samą procedurą co h_1**
  (fit M2-exp z priorem h_thick na mockach wszystkich modeli z tabeli).
  Weryfikator dla modeli zgodnych z h_1 uzyskał h_thin 220–242 pc, więc
  dotychczasowe [250; 350] obleje poprawny pipeline. Wstępnie ~205–320 pc;
  wartość ostateczna z tabeli, przed fitem na danych.
- **z☉: test pipeline'u tylko na mocku (±2 pc).** Na danych z☉ raportowane
  bez progu (asymetria N/S Bennett & Bovy 2019 ma maksimum ~0,2 kpc, wewnątrz
  rdzenia), plus wariant z szablonem asymetrii A(z) z Bennett & Bovy, żeby
  porównać z 20,8 pc w tej samej konwencji.
- Kryterium mocka Khanny: maksimum profilu przy węźle h_thick = 500 pc.
- Przedziały asymetrii a_k definiowane względem z_ref (jak okna fitu), nie
  względem z_obs + z☉.
- Koszt normalizacji: systematyka przy N_side 64 to ~200 h·rdzeń; `numba`
  od początku (Z8).

**U2. Funkcja selekcji.** `parallax > 0.5 AND phot_g_mean_mag < 19` (S3).
Nieaktualne: „0,4 mas" w S2 D12 i starsze wzmianki w S4. Progi wszystkie
segmenty biorą z konfiguracji S3 (`parallax_min_mas`, `g_max_mag`).

**U3. Jedna funkcja hash.** `storage.canonical_hash` (S1 dec. 7) to jedyna
definicja hasha treści. S3 liczy nią `content_hash_values`
(`content_hash_ids` bez zmian), S4 T7 też jej używa.

**U4. Hipparcos.**
- S3 dopisuje do pobrań przed 25.11 zbiór `hip_best_neighbour`
  (`hipparcos2_best_neighbour` ⋈ `gaia_source`, bez cięć selekcji).
- Gwiazda HIP z odpowiednikiem 5p/6p, który odpadł na selekcji, dostaje
  `excluded_by_selection` i nie wchodzi do katalogu (S1).
- Dla ~1,8·10⁴ gwiazd HIP spoza tabeli archiwum (Brandt 2021) dodatkowe
  dopasowanie pozycyjne (propagacja epoki do `gaia_ref_epoch`) do zbioru bez
  cięcia paralaksy. Wiersze Hipparcosa są wyłączone z fitu S5.

**U5. Mnożnik błędów paralaksy k.** Skalar albo tablica `{G_edges, k}`
(S4 Zmiany 3), stosowana identycznie w `corrected_parallax` i
`sigma_parallax_model` (S2).

**U6. Tablica σ_ϖ (S2 D12).**
- Źródło: 1% próbka populacyjna S3 (`aux/population`), bez cięć selekcji,
  ale z cięciami jakościowymi fitu (RUWE, `astrometric_params_solved` z S5).
- Zapisuje kwantyle 10/50/90% w komórce; mock losuje σ_true z rozkładu,
  nie z mediany.
- Jasny koniec (G ≲ 14, przy biegunach ≲ 16) idzie przez fallback (G, |β|);
  raportować frakcję traserów na fallbacku.
- ν_eff(BP−RP): na DR3 porównać relację empiryczną ze wzorem z Lindegren
  i in. 2021 (kontrola).

**U7. Generator mocka S2 D11** — termin 10.11. Wymagania S4: dysk
dwuskładnikowy obowiązkowo, `tracer_model` wymienny (karły: S4, red clump:
S5), `extinction_model = none`. Dodać wariant z halo (S4 r3 uw. 4).

**U8. S4 — poprawki z recenzji r3 (zamknięte przez koordynatora).**
- Kontrola kinematyczna okna koloru: okno Toomre'a
  70 < |V_tot − V_LSR| < 180 km/s, próg ≥ 95%; frakcja |V| > 200 km/s (halo)
  raportowana osobno.
- Górna krawędź okna koloru: locus [Fe/H] = +0,3 przesunięty o −0,75 mag
  w M_G (nierozdzielone podwójne zostają); podolbrzymy odcina M_G > 4,5.
  Wariant „krawędź bez binarek" w T5c.
- Okno fitu T5c do |z + z☉| ≤ 1200 pc (albo próbka |z_pc| < 1300).
- h_thick i f_thick z T5 tylko informacyjnie.
- `zp_systematic_variant_mas = max(0,015; |T6d − Δ_qso| + 2σ_med)`; dla
  G < 10,8 ostrzeżenie T6d tylko przy różnicy > 10 µas względem obu
  odniesień (L21 i `zinn2021_bright`); T6d z próbki 20 pc wstępny, wiążący
  z walca (etap B).
- Frakcja f > 0,15 dla |z| > 800 pc: test dwumianowy (p > 0,01) zamiast ±50%.
- Margines w T5 wobec progu 0,5 mas: ≈ 0,18 mas (przy zp = −0,10), nie 0,28.

**U9. S3 — uzupełnienia.**
- Do pobrań 5–6.11 dopisać pozycję 8 z S4: próbka 100 pc z
  `radial_velocity` (potrzebna przed 7.11 do `tracer_model`).
- Etap B DR4: jedna definicja zapytania — szablon `cylinder_t5` z S3 z
  marginesem 0,2 mas na zero-point DR4 i jawnym dolnym progiem paralaksy
  (≈ 0,58 mas); `parallax > 0.7` z S4 v3 nieaktualne.
- Sprzątanie konta: pobieracz oznacza swoje joby i usuwa tylko je (nie
  joby S4).
- Manifest odtwarzalny po fakcie z `state.json` i plików (zapas, gdyby
  pobieracz uproszczony nie był gotowy 6.11).

**U10. Harmonogram DR3: daty S3 są nadrzędne.** Pełne pobranie 9–13.11,
weryfikacja do 18.11. Zadania 9–10 w S4 przesunięte: **G1a docelowo 18.11**,
24.11 to twardy termin awaryjny (po 25.11 brakujące części tylko z AIP).

**U11. Stałe w manifeście.** Preset astropy `Galactocentric` w wersji `v4.0`
(8,122 kpc; 20,8 pc), `z_ref = 20,8 pc` dla okien w z, poziom partycji P,
poziom wyrównania kafelków 3.

**U12. Plan v3.** Sekcje 1.1–1.7 i 2.1–2.5 są zastąpione segmentami.
Szkic `crossmatch_gaia_distances.sql` do usunięcia (S3 zad. 3).
`mass_provenance.py` czeka na etap 3.

## 5. Harmonogram zbiorczy

| Termin | Co | Segment |
|---|---|---|
| 2–3.11 | Próbka populacyjna 1% (liczności, σ_ϖ, ν_eff); pilot 10 kafelków | S3 |
| 3–4.11 | Zamrożona referencja 20 pc, szkielet raportu, `canonical_hash` | S4, S1 |
| 5–6.11 | Joby S4 (w tym próbka 100 pc z RV), `hip_best_neighbour`; pobieracz uproszczony gotowy 6.11 | S3, S4 |
| do 10.11 | Generator mocka D11 | S2 |
| 7–11.11 | `tracer_model` karłów, mock T5 | S4 |
| 9–13.11 | **Pełne pobranie DR3 (1,25 kpc)** | S3 |
| do 12.11 | Część magazynowa gotowa | S1 |
| 13–16.11 | Budowa katalogu Parquet z kafelków DR3 | S1 |
| 12–19.11 | Kod T5, test metody na mocku | S4 |
| do 18.11 | **G1a**: dane DR3 zweryfikowane (twardo 24.11) | S4 |
| 16.11–1.12 | Pełny klient pobierania (dla DR4) | S3 |
| 25.11–2.12 | Archiwum wyłączone. Offline: T2–T5, T8 na DR3; kod S5 i testy na mocku | S4, S5 |
| 1.12 | **G1b**: walidacja DR3 zaliczona | S4 |
| 2–9.12 | DR4 etap A, lista kontrolna DR4 | S4 |
| 10.12 | **G2** | S4 |
| 10–15.12 | DR4 etap B (walec T5) → **G3a** | S4 |
| 10–22.12 | DR4 etap C (pełne 1,25 kpc) → **G3b** | S3, S4 |
| 18.12 / 22.12 | Twarde terminy wycofania: fit główny na DR3, DR4 w styczniu | S4 |
| po G3b | Fit główny S5 na DR4 (Z13) | S5 |
| po 2.12 | Viewer: format binarny, kafelki x/y/z (~5 dni) | S1 |

### 5a. Obciążenie pracą — ryzyko, którego nie widzi żaden pojedynczy segment

Każdy segment ma realny harmonogram sam w sobie, ale wszystkie zakładają
„jedną osobę" równolegle. Suma szacunków z segmentów na listopad
(2.11–1.12, ~22 dni robocze):

| Segment | Praca do 1.12 |
|---|---|
| S1 | ~9,75 d (magazyn) |
| S2 | ~13,5 d |
| S3 | ~8 d (4,5 d do DR3 + 3,5 d pełny klient) |
| S4 | ~12–15 d (zad. 1–11) |
| S5 | ~15 d (Z1–Z10, zadania po ≤ 2 d) |
| **Razem** | **~60 dni pracy**, czyli ~3 osoby na pełen etat |

Dla jednej osoby harmonogram z §5 jest niewykonalny. Jedyny **zewnętrzny**
twardy termin to wyłączenie archiwum 25.11 — i dotyczy on tylko
**pobierania danych**, nie kodu. Ścieżka minimalna:

1. **Do 13.11 tylko to, co wymaga archiwum:** ścieżka DR3 z S3 (4,5 d:
   próbka populacyjna, pilot, pobieracz uproszczony, pełne pobranie), joby
   S4 (w tym próbka 100 pc z RV), `hip_best_neighbour`. Walec T5 mieści
   się w pełnym pobraniu (próg 0,5 mas sięga do ~2 kpc).
   Kafelki S3 są już posortowanymi plikami Parquet, więc reszta pracy może
   na nich ruszyć później.
2. **Mapa Edenhofer** pobierana spoza ESA (S5 Z1) — bez terminu archiwum.
3. **Potem w kolejności zależności:** S2 warstwa paralaksy → S1 magazyn →
   S4 T1 i T5 → S5.
4. **Bramki DR4 przesuwają się:** G1b, G2 i G3 realnie na styczeń; DR4
   pobierać dopiero po zaliczeniu G1b. Viewer po etapie 2.

Decyzja do podjęcia na starcie: ile osób pracuje nad projektem. Od tego
zależy, czy obowiązuje harmonogram z §5, czy ścieżka minimalna.

## 6. Etap 3 — backlog (bez zmian względem v3, z dopiskami)

- Bailer-Jones i StarHorse w wersjach dla DR4 (nie mieszać z EDR3 bez tabeli
  przejścia ID); sprawdzić jednostki StarHorse (kpc).
- Mapy pyłu poza 1,25 kpc z pokryciem całego nieba; strefy przejścia między
  mapami, `ext_origin`, test ciągłości.
- Masy (`mass_provenance.py`): RUWE we wszystkich gałęziach, Mann tylko blisko,
  weryfikacja współczynników, brakujące JOIN-y (2MASS, `astrophysical_parameters`).
  Najpierw rozstrzygnąć, czy masy są potrzebne celowi mapy.
- Świece standardowe, masery VLBI, przeglądy podczerwone; warp i flara dysku.
- UVW i współrzędne cylindryczne przez Monte Carlo; pełny LOD viewera.

## 7. Otwarte do weryfikacji

- Liczba wierszy przy funkcji selekcji (model ~1,9·10⁸) — próbka populacyjna 2–3.11.
- Czy `random_index` ma indeks w archiwum ESA — job próbny 2.11.
- Czy DR3 pozostanie w archiwum ESA po 2.12 (zapas: AIP, pełna `gaiadr3.gaia_source`).
- Nazwy kolumn i model danych DR4, oficjalna recepta zero-pointu DR4,
  kodowanie HEALPix w `source_id` DR4 — lista kontrolna od 2.12.
- Pliki mapy Edenhofer w `dustmaps`, RAM dla 12 próbek, czas siatki — S5 Z1.
- Tablice Fitzpatrick 2019 dla red clump (λ Wesenheita).

Proxy w sesji planowania blokował archiwa TAP i część stron, więc część liczb
pochodzi z modeli skalibrowanych na literaturze; segmenty oznaczają je
„do weryfikacji".

## 8. Dziennik weryfikacji

Liczby uwag: krytyczne / istotne / drobne.

| Segment | Runda 1 | Runda 2 | Runda 3 | Wynik |
|---|---|---|---|---|
| S1 | 1 / 5 / 5 | 0 / 2 / 4 | 0 / 0 / 2 | zaakceptowany |
| S2 | 1 / 5 / 4 | 0 / 2 / 4 | 0 / 0 / 4 | zaakceptowany |
| S3 | 1 / 3 / 7 | 0 / 1 / 7 | 0 / 0 / 4 | zaakceptowany |
| S4 | 1 / 9 / 6 | 0 / 6 / 6 | 0 / 1 / 5 | zamknięty przez koordynatora (U8) |
| S5 | 1 / 6 / 6 | 0 / 4 / 5 | 0 / 2 / 3 | zamknięty przez koordynatora (U1) |

Uwagi krytyczne z rundy 1, które zmieniły plan:
- **S1:** liczba wierszy zaniżona ~2×, a partycje nie mieściły się w pamięci → limit G < 19, poziom 3.
- **S2:** izotropowy prior EDSD obciąża wysokość skali → fit w przestrzeni paralaks.
- **S3:** kafelki zapytań przekraczały granice partycji magazynu → wyrównanie do poziomu 3.
- **S4:** próba generalna nie mierzyła z☉, choć z☉ było kryterium → osobny pomiar, stałe okno fitu.
- **S5:** mapa pyłu nie zwraca odchylenia w trybie całkowanym → średnia + próbki posterioru jako systematyka.

Decyzje koordynatora w trakcie pętli: fit w paralaksach (po S2 r1), limit
jasności (po S1 r1), dane DR3 przed 25.11 i analizy offline (po S4 r1),
uproszczony pobieracz dla DR3 (po S3 r2), porównanie DR4−DR3 dla jasnych
gwiazd tylko jako raport i systematyka, nie korekta (po S4 r2).

---

*Plan prac pipeline'u mapy 3D Drogi Mlecznej. Stan wiedzy: 31.10.2026, Gaia
DR3; DR4 zapowiedziana na 2.12.2026.*
