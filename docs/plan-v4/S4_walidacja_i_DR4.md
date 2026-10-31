# S4 — Walidacja i przejście na DR4
Wersja: v3 · Etap: 1–2 (sekcje 1.7, 2.1, 2.2 planu v3)

## Cel

Pokazać liczbami, że pipeline z S1–S3 daje na DR3 poprawne katalogi i
prosty pomiar dysku zgodny z literaturą. Potem przejść na DR4 według stałej
procedury i powtórzyć testy. S4 jest **bramką przed fitem S5 na DR4**.

Zasada harmonogramu (decyzja koordynatora): wyłączenie archiwum ESA
(25.11, 12:00 → 2.12, 12:00 CET) blokuje tylko **pobieranie**. Wszystko, co
S4 i S5 potrzebują z archiwum DR3, musi być pobrane do 25.11. Analizy biegną
offline w trakcie przerwy i po niej.

## Zakres / poza zakresem

**W zakresie:**
- katalog referencyjny 20 pc;
- testy T1–T8 z progami;
- próba generalna T5, prosta i niezależna od S5, **wraz z własnym mockiem
  karłów G/K**;
- lista pobrań DR3 przed 25.11;
- raport walidacji i bramki;
- lista kontrolna DR4;
- etapowe pobieranie DR4, przełączenie i wycofanie.

**Poza zakresem:**
- estymatory, warstwa paralaksy i generator mocka (S2);
- pobieranie (S3) i magazyn (S1);
- metoda S5 (pył, red clump, V_eff, fit w przestrzeni paralaks) i mock red
  clump (S5). Przebieg S5 na DR3 to nieblokujący kamień milowy S5.

## Wejścia i wyjścia

**Wejścia:**
- obecny katalog CSV, jego ADQL, wywołanie CLI i tag git;
- z S3 (v2/v3), Parquet + manifest:
  - funkcja selekcji produktu głównego: `parallax_min_mas` i `g_max_mag` z
    konfiguracji S3, dziś 0,5 mas i 19,0. S4 nie wpisuje tych liczb na stałe;
  - zbiór „bliski” (`parallax > 45`, bez limitu G) dla T1/T6;
  - zbiory pomocnicze S4 sprzed 25.11;
- z S2 (v3):
  - funkcje `corrected_parallax()`, `parallax_loglike()`,
    `sigma_parallax_model()`, `prob_parallax_in_window()`,
    `mock_parallaxes(disc_model, tracer_model, extinction_model, …)`;
  - kolumny `parallax_zp_mas`, `zp_origin`, `r_lo/med/hi_pc` (kwantyle
    0,1587 / 0,5 / 0,8413), `dist_origin`, `dist_flag`;
  - parametr `parallax_error_inflation`.

**Wyjścia:**
- `validation/reference/`: zamrożony katalog, ADQL, flagi CLI, tag;
- `validation/<wydanie>/<data>/report.json` i `report.md`; manifest wskazuje
  raport;
- `validation/mock_t5/`: `tracer_model` karłów i konfiguracja mocka T5;
- `config/gaiadr4.toml`;
- wypełniona lista kontrolna DR4;
- k (skalar lub tablica k(G)) dla DR3 i DR4 z uzasadnieniem, przekazane do
  S2;
- raport różnic ϖ₄ − ϖ_c,3 w przedziałach G (diagnostyka zero-pointu DR4).

## Decyzje

1. **„Te same gwiazdy” = różnica symetryczna, w której każda pozycja ma
   wyjaśnienie.** Porównanie po `source_id` (DR3) i HIP, na zbiorze
   „bliskim”. Zamknięta lista przyczyn:
   - (a) granica 20 pc (|r − 20| < 3σ_r);
   - (b) obcięcie przez `TOP N`;
   - (c) deduplikacja Hipparcosa;
   - (d) flagi CLI referencji (np. `--min-mass`; pełna lista z zadania 1);
   - (f) brak fotometrii G.

   Przyczyny (e) „limit G” w T1 **nie ma**, bo zbiór „bliski” nie ma limitu
   G. Gwiazda wycięta przez G oznacza, że T1 działa na złym zbiorze, i jest
   błędem. Limit G < 19 dotyczy tylko produktu głównego i viewera. W 20 pc
   wycina karły L/T i białe karły (M_G ≈ 18 → G ≈ 19,5). Odnotowane w
   manifeście, bez testu.

   *Odrzucone:* porównanie liczności i wymóg identyczności zbiorów.
2. **Test 20 pc nie sprawdza zero-pointu.** Sprawdzają go T3 i diagnostyka
   T6. T1 kontroluje arytmetykę: r = 1000/(ϖ − `parallax_zp_mas`).
3. **T5: prosta próba niezależna od S5.**
   - Karły G/K w walcu R < 250 pc, bez korekty pyłu i bez cięcia |b|.
   - Odległość 1000/ϖ_c, fit na liczbach gwiazd.
   - **Bez cięcia f** (uzasadnienie przy T5).
   - Inny traser, inna metoda i inne odległości niż w S5, więc zgodność T5 i
     S5 to prawdziwa kontrola.
4. **z☉ mierzone osobno, ze szczytu n(z) (T5a).** Fity T5b i T5c dostają z☉
   jako stałą. Asymetria N/S jest tylko informacyjna.
5. **Bramka T5 to dwie miary:**
   - T5b: jeden wykładnik na 150–450 pc;
   - T5c: h_thin z fitu dwuskładnikowego, z wariantami czułości;

   do tego szara strefa: diagnoza zamiast automatycznego „nie”.
6. **Zero-point DR4: korekta tylko z jednego produktu Gai DR4** (decyzja
   koordynatora 1). Kolejność jak w S2:
   - `dr4_official`;
   - inaczej `qso_global_offset` z mediany `gaia_crf4`.

   Nigdy `gaiadr3-zeropoint` na DR4 (biała lista S2). Różnica ϖ₄ − ϖ_c,3
   dla wspólnych gwiazd **nie** jest korektą. To raport diagnostyczny i
   źródło niepewności systematycznej (T6d).
   - Dlaczego nie korekta: dziedziczy systematykę L21 (Zinn+2021 dla
     G ≲ 10,8) i wnosi dane DR3 do produktu DR4, wbrew decyzji 8.
   - Wariant systematyczny dla S5: domyślnie ±15 µas. Rośnie do zmierzonej
     wartości, jeśli T3-DR4 (LMC) albo T6d pokaże więcej.
7. **DR4 nie nadpisuje DR3.** Osobna konfiguracja, katalog i manifest. Pełny
   DR3 1,25 kpc zostaje planem awaryjnym S5.
8. **`dr3_neighbourhood` służy tylko walidacji i diagnostyce (T6),** nigdy
   łączeniu danych w produkcie.
9. **DR4 pobierane etapami A → B → C.** Bramki G2 i G3a zależą tylko od
   małych pobrań.
10. **Mock T5 należy do S4** (decyzja koordynatora 2). Budowa:
    - generator S2 D11;
    - `tracer_model` karłów dostarczony przez S4;
    - `extinction_model = none`;
    - obowiązkowo dwuskładnikowy dysk.

    *Odrzucone:* mock red clump z S5. Inny traser i z pyłem, więc nie testuje
    T5.

## Testy i progi

Próg oznaczony „wstępny” można zmienić po pierwszym przebiegu, ale tylko z
wpisem do raportu: wartość stara, nowa i powód.

**T1 — regresja 20 pc (DR3, zbiór „bliski”).** Do zbioru „bliskiego” z
`r_med_pc < 20` stosujemy w kodzie stare cięcia (`parallax_over_error > 10`,
`ruwe < 1.4`) i flagi CLI referencji.
- Różnica symetryczna: każda pozycja ma przyczynę (a)–(d) lub (f).
  **Niewyjaśnionych: 0.**
- Gwiazdy dodane przez zniesienie cięcia na poe trafiają na osobną listę do
  przeglądu.
- Inwersja: |r_med − 1000/(ϖ − zp)| / r_med < 10⁻⁶.
- Surowa ϖ identyczna ze starą dla wierszy Gai.
- `edsd_prior` przy f < 0,01: |r_med − 1000/ϖ_c| / r_med < 10⁻³.
- Hipparcos: zbiór HIP zgodny z dokładnością do przyczyn z listy.
- `dist_pc ≡ r_med_pc`, bitowo.

**T2 — estymatory i wiarygodność na symulacji.**
- **T2a, kalibracja kodu.**
  - Prawda losowana z tego samego nieobciętego priora EDSD, σϖ z
    `sigma_parallax_model`, 10⁵ gwiazd, bez selekcji.
  - Frakcje r_true < r_lo, r_true < r_med, r_true > r_hi: 15,87 / 50,0 /
    15,87% ± 0,5 pp.
- **T2b, wariant realistyczny.**
  - Mock S2 D11 (dysk dwuskładnikowy, `tracer_model` karłów z T5 albo RC z
    S5), selekcja S3 z konfiguracji (`parallax_min_mas`, `g_max_mag`), potem
    selekcja po **obserwowanym** f.
  - Dla f < 0,1: |mediana(r_med/r_true − 1)| < 1% dla obu estymatorów.
  - Powyżej f = 0,1 tylko raport, w funkcji b.
- **T2c, wiarygodność dla S5. Liczona na wszystkich wygenerowanych gwiazdach
  przed selekcją.**
  - Reszty (ϖ_c − 1000/r_true)/σ_c: średnia 0 ± 0,01, odchylenie
    standardowe 1 ± 0,01.
  - Wariant Δzp: średnia przesuwa się o Δzp/σ ± 0,01. Wariant k ≠ 1:
    odchylenie = k ± 0,01.
- **T2d, funkcja selekcji.**
  - W 20 przedziałach r (do 1,6 kpc) porównujemy frakcję gwiazd przyjętych
    przez selekcję S3 z sumą `prob_parallax_in_window` po gwiazdach mocka.
  - Zgodność w granicach Poissona: χ² na 20 przedziałach, p > 0,01.
  - To sprawdza funkcję, której S5 naprawdę używa.

**T3 — implementacja zero-pointu (DR3), kontrola zero-pointu (DR4).**
- **DR3.** Kwazary `gaiadr3.agn_cross_id` (1 612 202 wiersze) z wejściami
  L21, w jednym jobie.
  - Surowa mediana ≈ −17 µas; po korekcie |mediana| < 5 µas.
  - To **test kodu** (znak, jednostki, kolumny).
- **DR3, LMC.** Stożek ~3°, cięcie na ruchu własnym. Mediana ϖ_c w
  przedziałach G 13–15 / 15–17 / 17–19 vs 0,0202 mas. To odległość
  49,59 ± 0,54 kpc (Pietrzyński+2019); systematyka odległości daje ~0,2 µas,
  czyli bez znaczenia. Raport bez progu, jako referencja.
- **DR4.**
  - Jeśli `qso_global_offset`: offset z całej próbki `gaia_crf4`, a test
    kodu na niej: |mediana ϖ_c| < 1 µas.
  - Jednorodność (raport + ostrzeżenie): różnice median między półkulami
    galaktycznymi, przedziałami |β| (0–30°, 30–60°, 60–90°) i przedziałami G
    (< 19, 19–20, > 20). Ostrzeżenie w G2, gdy jakakolwiek różnica przekracza
    10 µas; wtedy wariant systematyczny rośnie do zmierzonej różnicy.
  - LMC jak dla DR3. Różnica od 0,0202 mas > 15 µas w którymkolwiek
    przedziale podnosi wariant systematyczny.

**T4 — zgodność z Bailerem-Jonesem (tylko DR3).** `edsd_prior` vs
`r_med_geo` z `external.gaiaedr3_distance`, na 2–3 kafelkach:
- f < 0,1: mediana |Δr|/r < 1%, 99. percentyl < 3%;
- f 0,1–0,3: raport kierunku różnic.

Do tego `distance_gspphot*` jako kontrola S2 D8.

**T5 — próba generalna pomiaru dysku (DR3, potem DR4).**
- **Próbka:**
  - walec R < 250 pc, |z| < 1250 pc (d ≤ 1275 pc, ϖ_c ≥ 0,784 mas);
  - 4,5 < M_G < 6,0, z M_G z 1000/ϖ_c;
  - `ruwe < 1.4`, bez `spurious_parallax`.
- **Okno koloru szerokie.** Obejmuje locus ciągu głównego od [Fe/H] ≈ +0,3
  do ≈ −1,0 przy danym M_G (izochrony PARSEC lub MIST; wybór przy kalibracji
  do weryfikacji), plus margines 0,05 mag. Kontrola okna: gwiazdy grubego
  dysku wybrane kinematycznie (|V_tot| > 100 km/s, podzbiór z
  `radial_velocity`, 100–300 pc) muszą w ≥ 98% mieścić się w oknie. Okno
  odrzuca tylko podolbrzymy (nad locus) i białe karły oraz podkarły. Okno
  „wąskie” (z CMD 100 pc, ±2σ wokół locus) jest obowiązkowym wariantem T5c.
- **Brak cięcia f.** Przy d = 1275 pc i G ≤ 17,0 typowe f ≈ 0,07–0,09. Po
  mnożniku k z T8 (≤ 1,3) i zmienności pokrycia (×1,5) najgorsze f ≈ 0,18.
  Cięcie f < 0,1 działałoby więc zależnie od kierunku i od z, akurat w
  zakresie grubego dysku. Zamiast cięcia:
  - raport frakcji z f > 0,15 w przedziałach |z| po 100 pc; wymagane < 0,5%
    w każdym przedziale;
  - jeśli nie, zawężenie do M_G < 5,5 (G ≤ 16,5) i ponowny raport;
  - obciążenie inwersji przy f ≈ 0,1–0,15 (rzędu f², ≤ 2% odległości na
    brzegu) obejmuje mock, bo ma ten sam szum.
- **Zgodność z selekcją S3:**
  - G ≤ 17,0 przy DM 10,5, więc margines do `g_max_mag = 19` wynosi
    ≥ 2 mag;
  - ϖ_c ≥ 0,784, czyli ≥ 0,28 mas nad progiem 0,5 przy zp DR3 ∈
    [−0,10; +0,05] mas.

  Jeśli S3 zmieni `g_max_mag` poniżej 17,5 albo `parallax_min_mas` powyżej
  0,7, T5 trzeba przeliczyć.
- **T5a, z☉.** |z_pc| < 200 pc (heliocentryczne), model
  sech²((z + z☉)/(2H)) + c, MLE niebinowane, bootstrap. Kryterium:
  **z☉ ∈ [10, 30] pc.**
- **T5b, miara słabo modelowa.** Jeden wykładnik na 150 < |z + z☉| < 450 pc.
  Kryterium: **h_1 ∈ [270, 370] pc.**
  - Oczekiwane: ~302 pc (Everall+2022), ~343 pc (Jurić+2008).
  - Przedział zakłada niski udział grubego dysku w płaszczyźnie
    (f_thick ≈ 0,1). Przy f_thick = 0,75 (Vieira+2023) wyszłoby ~457 pc.
    T5b jest więc „słabo”, a nie „w ogóle niezależny od modelu”. Wynik
    > 370 pc przy poprawnym T5c to sygnał do diagnozy dekompozycji, nie
    błędu pipeline'u.
- **T5c, fit dwuskładnikowy.** Okno 100 < |z + z☉| < 1250 pc, z☉ stała,
  bootstrap z ziarnem z manifestu. Kryterium: **h_thin ∈ [250, 350] pc.**
  Obowiązkowe warianty:
  - h_thick ∈ {700, 900} pc ustalone;
  - f_thick ∈ {0,06; 0,12} ustalone;
  - okno koloru wąskie vs szerokie.

  Rozrzut wariantów to systematyka.
- **Kontrole bez progu:** maska |b| > 30° i maska Oph/Taurus; N vs S; okno
  M_G ±0,25 mag (efekt Eddingtona).
- **Test metody (mock T5, warunek oceny T5 na danych).** Mock: h = 300,
  h_thick = 900, f_thick = 0,12, z☉ = 20,8, bez pyłu, ta sama selekcja i ten
  sam fit. Wymagane:
  - z☉ ± 3 pc;
  - h_1 w ±3% od wartości wyliczonej z modelu;
  - h_thin ± 5%;
  - frakcja f > 0,15 zgodna z danymi w ±50%.
- **Werdykt:**
  - **zaliczone:** T5a, T5b i T5c w przedziałach;
  - **szara strefa:** h_thin ∈ [230, 250) ∪ (350, 370] albo h_1 do 20 pc
    poza przedziałem; wtedy diagnoza i decyzja właściciela w raporcie
    (Everall+2022: ±26 pc systematyki);
  - **niezaliczone:** wszystko inne, także z☉ poza przedziałem.

**T6 — ciągłość DR3 → DR4 (zbiór „bliski” z etapu A i walec z etapu B).**
- T6a. Dopasowanie pozycyjne z propagacją J2016,0 → J2017,5, kontrolnie
  przez `dr3_neighbourhood`. Te same cięcia jakości co T1. Źródła z
  rozwiązaniem NSS lub z przyspieszeniem w DR4 wyłączone (tabele `nss_*`;
  flaga w `gaia_source` do weryfikacji).
- T6b. Dopasowanych w 20 pc ≥ 99%. Reszta z przyczyną z listy T1 albo
  „rozdzielona/scalona w DR4”.
- T6c. |ϖ_c,4 − ϖ_c,3| < 3σ₃ dla ≥ 99% (σ₃, bo pomiary są skorelowane).
- **T6d, diagnostyka zero-pointu dla jasnych gwiazd** (raport wymagany).
  - Mediana i błąd mediany ϖ₄ − ϖ_c,3 w przedziałach G < 10,8 / 10,8–13 /
    13–15 / 15–17. Dla G < 13 dodatkowo w przedziałach koloru i |β|.
  - Dane: 20 pc (etap A, wynik wstępny w G2) i walec T5 (etap B, ~10⁵
    gwiazd, wynik w G3a).
  - Interpretacja: przesunięcie ZP DR4 względem L21 w danym przedziale.
    Zawiera systematykę L21, więc wynik jest raportowany obok wariantu
    `zinn2021_bright`.
  - **Ostrzeżenie w bramce** (G2 wstępnie, G3a), gdy w którymkolwiek
    przedziale G < 13 |mediana(ϖ₄ − ϖ_c,3) − Δ_qso| > 10 µas. Δ_qso to ta
    sama różnica dla kwazarów: offset DR4 minus mediana L21 dla DR3.
    Ostrzeżenie nie blokuje bramki. Podnosi wariant systematyczny dla S5 do
    zmierzonej różnicy i trafia do `zp_systematic_variant_mas`.

**T7 — odtwarzalność.**
- Ponowny przebieg z manifestu dla zbioru „bliskiego” i 2 kafelków, z
  zachowanych surowych odpowiedzi VOTable.
- Hash kanoniczny:
  - tabela posortowana po `source_id`;
  - kolumny `category` zdekodowane do stringów;
  - każda kolumna osobno: SHA-256 z bufora wartości (little-endian, bez
    wyrównania) i z bitmapy NaN/null;
  - hash tabeli = SHA-256 z listy (nazwa kolumny, hash) w stałej kolejności.

  Bajty Parquetu i Arrow IPC nie są kanoniczne, więc ich nie hashujemy.
- `report.json` porównywany bez pól czasu i ścieżek, które leżą w osobnej
  sekcji `run_meta`. Bootstrap T5 z ziarnem z manifestu.

**T8 — mnożnik błędów paralaksy (wymagany przez S2 D6).**
- Słabe źródła: kwazary z T3, odporne odchylenie (1,4826·MAD) z
  (ϖ − zp)/σϖ w przedziałach G 17–18 / 18–19 / 19–20 / 20–21.
- Jasne źródła (DR3): szerokie pary z katalogu El-Badry+2021 (Zenodo,
  rekord 4435257, 1,8 GB, ~1,8 mln par; dane EDR3 = astrometria DR3).
  Rozrzut (ϖ₁ − ϖ₂)/√(σ₁² + σ₂²) w przedziałach G co 1 mag, dla separacji
  > 4″.
- **Wynik:**
  - jeśli we wszystkich przedziałach G < 19 odchylenie mieści się w
    [0,95; 1,05], to k = 1 (skalar);
  - inaczej tablica k(G) (krawędzie G, wartości), przekazana do S2 przez
    zmianę kontraktu 3.

  Wariant k = 1 vs k(G) przechodzi do S5 jako systematyka. T5 i mock T5
  używają tego samego k.
- DR4: tylko kwazary. Dla G < 17 tymczasowo k(G) z DR3, z flagą
  `t8_dr3_carried`.

## Lista pobrań DR3 przed 25.11 (dla S4)

Pozycje 2–5 i 8 w oknie S3 dla jobów S4 (5–6.11):
1. Pełna objętość 1,25 kpc (S3), wszystkie kafelki `verified`.
2. Kwazary `agn_cross_id` z wejściami L21 (T3, T8), bez limitu G.
3. Próbka LMC z wejściami L21 (T3).
4. JOIN z `external.gaiaedr3_distance` i `distance_gspphot*` dla 2–3
   kafelków (T4).
5. Zbiór „bliski” i `hipparcos2_best_neighbour` (T1, S2).
6. Katalog El-Badry+2021 (Zenodo, nie zależy od archiwum ESA).
7. Surowe VOTable zbioru „bliskiego” i 2 kafelków (T7).
8. **Próbka 100 pc** (`parallax > 10`, `g_max_mag` z S3) z `radial_velocity`
   do `tracer_model` karłów i kalibracji okna koloru. Mała, potrzebna przed
   12.11, więc nie czeka na pełne pobranie.

## Bramki go/no-go

- **G1a (24.11, dane DR3):**
  - pozycje 1–5, 7 i 8 zweryfikowane;
  - kryteria S1–S3 spełnione;
  - T1 i T7 zaliczone.

  Brakujące części po 25.11, 12:00 pobieramy z AIP (pełne kolumny DR3, do
  weryfikacji). GAVO odpada (`dr3lite`).
- **G1b (1.12, analizy offline):**
  - T2a–d, T3, T4, T5 (z testem metody) i T8 zaliczone;
  - k przekazane do S2.

  Bez G1b nie pobieramy DR4 w etapach B i C. Etap A jest dozwolony.
- **Kamień milowy S5 na DR3** (nieblokujący, zadanie S5): przed Z13 (fit
  główny DR4). Porównanie T5 z S5 tylko w raporcie, bez progu.
- **G2 (10.12, DR4 etap A):**
  - lista kontrolna kompletna;
  - ZP DR4 wybrany;
  - T3-DR4 (test kodu) zaliczone, jednorodność i LMC zaraportowane;
  - T8 dla kwazarów;
  - T2 z σϖ(G) z DR4;
  - T6a–c i T7 zaliczone;
  - testy T1 niezależne od ID;
  - T6d wstępnie, z ewentualnym ostrzeżeniem.
- **G3a (15.12, DR4 etap B):**
  - T5 na DR4 zaliczone;
  - |h_DR4 − h_DR3 − Δh_zp| < max(10 pc; 3%) dla h_1 i h_thin, gdzie Δh_zp
    to T5 na DR3 z zp przesuniętym o Δ_qso;
  - |Δz☉| < 3 pc;
  - T6d na walcu, z ostrzeżeniem i wariantem systematycznym przekazanym S5.
- **G3b (przed Z13 S5, DR4 etap C):** wszystkie kafelki 1,25 kpc
  `verified`.
- **Wycofanie, twarde daty:**
  - 18.12: mniej niż 80% kafelków etapu C gotowych → fit główny S5 na DR3 (z
    Edenhofer), DR4 przechodzi na styczeń;
  - jeśli ≥ 80% → termin 22.12, po nim ta sama reguła;
  - G2 niezaliczona do 14.12 albo G3a do 18.12 → wycofanie od razu.

  Kontrakt kolumn się nie zmienia.

## Etapy pobierania DR4

- **A (3–9.12):** małe joby, bez kafelkowania:
  - zbiór „bliski”;
  - `dr3_neighbourhood` dla tych źródeł;
  - `gaia_crf4` z wejściami ZP;
  - próbka LMC.
- **B (10–14.12):** walec T5, około 6% objętości kuli 1,25 kpc. Zapytanie z
  **zapasem**: R < 300 pc, |z| < 1350 pc, `parallax > 0.7` i
  `phot_g_mean_mag < :g_max`. Dokładne cięcie (R < 250, |z| < 1250 na ϖ_c)
  robi kod. Kafelkowane, pierwszeństwo w puli jobów. Warunek na `b` lub
  `ra/dec` → `b` do weryfikacji w modelu danych DR4.
- **C (10–22.12):** pełne 1,25 kpc (S3), równolegle z B. Limit to 5 jobów
  wykonywanych równolegle i 50 w kolejce. S3 trzyma ≤ 3, B ma pierwszeństwo.

## Lista kontrolna rozpoznania DR4 (od 2.12; przy każdym punkcie wynik, źródło, data)

1. **Known issues i dokumentacja astrometrii.** Data sprawdzenia w
   `known_issues_checked_at`, przegląd co tydzień do G3b.
2. **Model danych:** finalny vs szkic z 26.06.2026, nazwa schematu.
   Kolumny `gaia_source` (do weryfikacji):
   - astrometria: `parallax`, `parallax_error`, `ruwe`,
     `astrometric_params_solved`;
   - wejścia ZP: `nu_eff_used_in_astrometry`, `pseudocolour`, `ecl_lat`;
   - fotometria i RV: `phot_g_mean_mag`, `bp_rp`, `radial_velocity`;
   - `l`, `b`;
   - flaga NSS.
3. **Epoka J2017.5 i Gaia-CRF4** → `gaia_ref_epoch` w konfiguracji.
4. **`source_id` ↔ HEALPix.** Test na etapie A: `source_id // 2^35` vs
   HEALPix poziomu 12 z `ra, dec` dla 10⁴ źródeł. Plan B dla S3: kafelki po
   `ra/dec`.
5. **Zero-point:** czy wydanie zawiera narzędzie lub receptę. Jeśli nie,
   decyzja 6.
6. **Mnożnik błędów:** czy dokumentacja podaje inflację σϖ (wejście do T8
   dla DR4).
7. **RUWE i fałszywe paralaksy:**
   - definicja RUWE i mediana ≈ 1,0;
   - kolano rozkładu w 20 pc, które decyduje o progu 1,4;
   - rola `spurious_signal`, `all_source_flags`, `crowded_field_source`.
8. **Apsis:**
   - kolumny odległości i ekstynkcji GSP-Phot w `ap_xp` / `ap_xp_supp`;
   - wewnętrzna korekta ZP w GSP-Phot (dla DR3: dokumentacja CU8 przed
     25.11);
   - `total_galactic_extinction_map` jest 2D, nie zastępuje Edenhofer.
9. **Pasma DR4 vs DR3:** wpływ na `photometry`, Teff z koloru,
   współczynniki Fitz19 (S5) i okno koloru T5.
10. **Archiwum:** stan dziś to wiersze async bez limitu, 120 min na job,
    20 GB na wyniki, 1 GB na tabele, 5 jobów wykonywanych równolegle i 50 w
    kolejce. Do sprawdzenia: czy DR4 zmienia limity i które centra
    partnerskie mają DR4.

## Zadania i harmonogram

| # | Zadanie | Termin |
|---|---|---|
| 1 | Zamrozić referencję (CSV, ADQL, wywołanie CLI z flagami, tag); sprawdzić `TOP N` | 3.11 |
| 2 | Szkielet raportu, hash kanoniczny (T7), wpięcie w manifest | 4.11 |
| 3 | Joby S4 w oknie S3: pozycje 2–5 i 8 | 5–6.11 |
| 4 | T1 (po `corrected_parallax` z S2) | 7.11 |
| 5 | `tracer_model` karłów (funkcja jasności i kolor z próbki 100 pc), kalibracja okna koloru (izochrony + kontrola kinematyczna) | 7–9.11 |
| 6 | **Mock T5** na generatorze S2 D11 (dysk dwuskładnikowy, bez pyłu) | 10–11.11 |
| 7 | Kod T2a–d, T3, T8 | 7–12.11 |
| 8 | Kod T5 (T5a–c, warianty, raport f) i test metody na mocku T5; pilot na 1 kafelku | 12–19.11 |
| 9 | Pełne pobieranie 1,25 kpc (S3); S4 codziennie sprawdza kompletność i duplikaty | 10–21.11 |
| 10 | Dobieranie nieudanych kafelków, T7, **G1a** | 21–24.11 |
| 11 | Offline: T2–T5 i T8 na DR3; szkic `gaiadr4.toml`; skrypty etapów A/B i T6d | 25.11–1.12 |
| 12 | **G1b** | 1.12 |
| 13 | Lista kontrolna, etap A | 2–9.12 |
| 14 | **G2** | 10.12 |
| 15 | Etap B, T5 i T6d na DR4 → **G3a** | 10–15.12 |
| 16 | Etap C → **G3b** albo decyzja o wycofaniu | 18.12 (twardo), 22.12 |

## Kryteria akceptacji segmentu

- Raporty G1a i G1b z wynikami T1–T5, T7, T8. Każdy test zaliczony albo w
  szarej strefie z diagnozą i decyzją właściciela.
- Mock T5 przechodzi test metody przed oceną T5 na danych.
- k (skalar lub k(G)) przekazane do S2 z uzasadnieniem.
- Lista kontrolna DR4: 10/10 punktów z wynikiem, źródłem i datą.
- Raport T6d z przedziałami G i wartością `zp_systematic_variant_mas`
  przekazaną S5.
- Raporty G2, G3a i G3b albo formalne wycofanie na DR3 w dniu reguły.

## Ryzyka i otwarte pytania

- **Zależności od S2:** `corrected_parallax` do 7.11, a generator D11 z
  dyskiem dwuskładnikowym i wymiennym `tracer_model` do 10.11. Bez
  generatora mock T5 się opóźnia, więc test metody, a za nim G1b, też.
  Wyjście awaryjne: uproszczony mock S4, czyli pozycje z modelu i szum z
  `sigma_parallax_model`, z adnotacją w raporcie. Bez warstwy paralaksy
  minimalne G1a = T1 (inwersja) + dane.
- **σϖ(G) do mocka przed pełnym pobraniem** pochodzi z pilota i próbki
  100 pc. Po 21.11 trzeba to powtórzyć na pełnych danych (zadanie 11).
- **Pula jobów:** małe joby S4 idą w oknie 5–6.11, przed pełnym
  obciążeniem.
- **Degeneracja h_thin ↔ f_thick ↔ h_thick:** obsługują ją T5b i warianty.
  Wynik Vieira+2023 to podpróbka wybrana kinematycznie, nie wprost
  porównywalna.
- **Populacja:** Bovy 2017 daje z_d ~50 pc dla gwiazd A i ~108–177 pc do
  G3V, przy |z| < 400 pc. Różnica wynika z populacji i zakresu z. T5 ocenia
  starsze karły w dużym |z|.
- **Okno koloru a metaliczność:** przesunięcie locus dla [Fe/H] ≈ −1 jest
  przybliżone (do weryfikacji na izochronach). Kontrola kinematyczna
  ogranicza ryzyko.
- **ZP DR4 bez oficjalnej recepty** jest prawdopodobny. Zabezpieczenia:
  decyzja 6, T6d i LMC. T6d mierzy względem L21, a nie absolutnie.
- **`source_id` bez HEALPix w DR4:** plan B to kafelki `ra/dec`.
- **Okres świąteczny:** stąd twarda data 18.12.

## Zmiany w kontrakcie

1. **Ujednolicenie z S2 v3 i S3 v3:**
   - nazwy `parallax_zp_mas`, `zp_origin`, `parallax_zp_method`;
   - ZP we wszystkich gałęziach zużywających surową paralaksę;
   - kwantyle 0,1587 / 0,8413;
   - progi selekcji wyłącznie z konfiguracji S3 (`parallax_min_mas`,
     `g_max_mag`).
2. **Nowe pola manifestu:**
   - `known_issues_checked_at`;
   - `validation_report`;
   - `parallax_error_inflation_source` (`t8_dr3` / `t8_dr4_qso` /
     `t8_dr3_carried` / `default`);
   - `zp_systematic_variant_mas` (domyślnie 0,015; może rosnąć po T3-DR4 i
     T6d; dla S5);
   - `zp_dr4_vs_dr3_report` (ścieżka raportu T6d).
3. **`parallax_error_inflation` jako skalar albo tablica** (decyzja
   koordynatora 3; do uzgodnienia z S2 przy składaniu):
   - forma: `{G_edges: [...], k: [...]}`, stała w przedziale;
   - poza zakresem wartość brzegowa;
   - stosowana identycznie w `corrected_parallax` i `sigma_parallax_model`;
   - w manifeście tablica i jej SHA-256.
4. **Wymagania dla generatora S2 D11:**
   - dysk dwuskładnikowy (h, h_thick, f_thick) jako opcja obowiązkowo
     wspierana;
   - `tracer_model` wymienny przez interfejs (funkcja jasności M_G i
     rozkład koloru), z dostawcą S4 dla karłów i S5 dla RC;
   - `extinction_model = none`;
   - termin: 10.11.
5. **S3:** szablon zapytania etapu B (walec z zapasem) w `WHERE`. Warunki na
   `parallax`, `b` i `phot_g_mean_mag` to selekcja, nie jakość, więc test S3
   musi je przepuszczać.
6. **S5:** kryterium 9 („DR3 przed 2.12 warunkiem Z12”) zamienione na
   kamień milowy nieblokujący przed Z13. Wejście na DR4 wymaga G2 + G3a
   (+ G3b dla fitu głównego). S5 przyjmuje `zp_systematic_variant_mas` jako
   wariant systematyczny. Mock red clump zostaje w S5.

## Odpowiedź na recenzję (runda 2)

1. **[IST.] ZP DR4 dla G < 13 — przyjęte w wersji z decyzji koordynatora 1.**
   - Nowy T6d: mediana ϖ₄ − ϖ_c,3 w przedziałach G, a dla G < 13 także koloru
     i |β|. Liczona na etapach A i B, bez dodatkowych pobrań.
   - Próg ostrzeżenia 10 µas względem Δ_qso. Wariant systematyczny rośnie do
     zmierzonej różnicy.
   - Kalibracja różnicowa jako `zp_origin` odrzucona: miesza produkty i
     dziedziczy L21 (decyzja 6).
2. **[IST.] Cięcie f < 0,1 — przyjęte.**
   - Cięcie f usunięte z T5.
   - Wymagany raport frakcji f > 0,15 w przedziałach |z|, z progiem < 0,5%.
     Jeśli nie przejdzie, zawężamy do M_G < 5,5.
   - Obciążenie inwersji pokrywa mock z tym samym szumem i tym samym k.
3. **[IST.] Właściciel mocka T5 — przyjęte** (decyzja koordynatora 2).
   - S4 dostarcza `tracer_model` karłów z próbki 100 pc. Próbka 100 pc jest
     nową pozycją 8 pobrań, bo pełne dane przyjdą za późno.
   - `extinction_model = none`.
   - Wymagania dla S2 D11 i termin 10.11 w zmianach kontraktu (pkt 4) i w
     ryzykach, z mockiem awaryjnym.
4. **[IST.] T2c po selekcji — przyjęte.** T2c liczony przed selekcją. Nowy
   T2d testuje selekcję przez `prob_parallax_in_window` (χ², Poisson).
5. **[IST.] k(G) w kontrakcie — przyjęte.** Zmiana kontraktu 3 (skalar lub
   tablica, SHA-256 w manifeście), do uzgodnienia przez koordynatora z S2.
6. **[IST.] Okno koloru a gruby dysk — przyjęte.**
   - Okno szerokie do [Fe/H] ≈ −1 z izochron, z kontrolą kinematyczną
     (≥ 98% gwiazd grubego dysku w oknie).
   - Wariant wąski vs szeroki jest obowiązkowy w T5c.
7. **[DR.] T5b zakłada niskie f_thick — przyjęte.** Założenie zapisane, z
   wartością 457 pc dla parametrów Vieiry. Wynik > 370 pc przy poprawnym
   T5c kieruje do diagnozy.
8. **[DR.] Próg paralaksy — przyjęte** (decyzja koordynatora 4). Progi
   wyłącznie z konfiguracji S3 (dziś 0,5 / 19,0). Margines T5 przeliczony:
   ≥ 0,28 mas.
9. **[DR.] Podział `gaia_crf4` na połowy — przyjęte.** Losowe połówki
   usunięte. Test kodu (< 1 µas) liczony na całej próbce. Jednorodność badana
   po półkulach, |β| i G, z ostrzeżeniem powyżej 10 µas.
10. **[DR.] T1 na zbiorze „bliskim” — przyjęte.** T1 i T6 działają na zbiorze
    „bliskim”. Przyczyna (e) usunięta z T1; jej wystąpienie oznacza błąd
    zbioru. Limit G opisany tylko dla produktu i viewera.
11. **[DR.] Hash kanoniczny — przyjęte.** Hash kolumna po kolumnie po
    zdekodowaniu słowników, bez IPC. `run_meta` wyłączone z porównania.
12. **[DR.] Zapas w zapytaniu etapu B — przyjęte.** Zapytanie z R < 300,
    |z| < 1350, ϖ > 0,7. Dokładne cięcie w kodzie na ϖ_c.

**Fakty z rundy 2 wpisane:** `agn_cross_id` 1 612 202 wiersze; LMC
49,59 ± 0,54 kpc (bez „z pamięci”, systematyka ~0,2 µas); El-Badry+2021 na
Zenodo, rekord 4435257.

## Źródła

- ESA:
  - Gaia DR4 content — https://www.cosmos.esa.int/web/gaia/dr4
  - Data Release 4 — https://www.cosmos.esa.int/web/gaia/data-release-4
  - News 2026 — https://www.cosmos.esa.int/web/gaia/news-2026
  - DR4 software tools —
    https://www.cosmos.esa.int/web/gaia/dr4-software-tools
  - limity archiwum — cosmos.esa.int/web/gaia-users/archive
- Literatura:
  - Jurić+2008, arXiv:astro-ph/0510520
  - Everall+2022, arXiv:2111.08043
  - Vieira+2023, Galaxies 11, 77
  - Bennett & Bovy 2019, arXiv:1809.03507
  - Bland-Hawthorn & Gerhard 2016, arXiv:1602.07702
  - Bovy 2017, arXiv:1704.05063
  - Lindegren+2021, arXiv:2012.01742
  - Zinn+2021, arXiv:2101.07252
  - El-Badry+2021, arXiv:2101.05282; Zenodo 4435257
  - Pietrzyński+2019, arXiv:1903.08096
