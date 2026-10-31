# S2 — Odległości, współrzędne, Hipparcos
Wersja: v3 · Etap: 1 (z przygotowaniem pod DR4 w etapie 2)

## Cel

S2 dostarcza dwa osobne produkty.

1. **Dla S5 (fit dysku w przestrzeni paralaks):**
   - funkcje dla obserwowanych wierszy: skorygowana paralaksa ϖ_c, jej błąd
     σ_c, zero-point, wiarygodność p(ϖ | r);
   - **funkcje punktowe dla całej populacji:** zp(G, kolor, β), model
     σ_ϖ(G, kierunek) i przeliczenie odległość ↔ próg ϖ_c. S5 potrzebuje ich
     w członie normalizacyjnym i w funkcji selekcji, gdzie występują gwiazdy,
     których nie ma w katalogu.
2. **Dla katalogu, viewera i statystyk opisowych:** kwantyle
   `r_lo/r_med/r_hi` z EDSD z provenance.

Do tego współrzędne galaktocentryczne z parametrami w manifeście oraz reguły
dla wierszy Hipparcosa i deduplikacji, które działają też w DR4.

## Zakres / poza zakresem

**W zakresie:**
- warstwa paralaksy: zero-point, mnożnik błędów, maska rozwiązań,
  wiarygodność;
- modele populacyjne: zp i σ_ϖ;
- estymatory `edsd_prior`, `parallax_inversion` i opcjonalnie `gspphot`;
- sampler odległości do wizualizacji;
- generator mocka do testu S2 → S5;
- kolumny `xgc/ygc/zgc_pc`;
- Hipparcos: dopasowanie i deduplikacja.

**Poza zakresem:**
- fit dysku, definicja okien selekcji, efektywna objętość, ekstynkcja i
  funkcja jasności trasera (S5);
- katalogi zewnętrzne BJ i StarHorse jako źródło odległości (etap 3; BJ 2021
  tylko do walidacji DR3);
- UVW i MC dla wielkości cylindrycznych (etap 3);
- mapa L(l,b) z BJ 2018 (backlog).

## Wejścia i wyjścia

**Wejścia (z S3, na wiersz):** `source_id`, `ra`, `dec`, `l`, `b`, `parallax`
(surowa, mas), `parallax_error`, `phot_g_mean_mag`, `bp_rp`,
`nu_eff_used_in_astrometry`, `pseudocolour`, `ecl_lat`,
`astrometric_params_solved`, `ruwe`. Hipparcos: `hip`, astrometria na
J1991.25 i paralaksa z Hipparcos-2 (van Leeuwen 2007).

**Wejścia (konfiguracja):**
- `gaia_release`, `gaia_ref_epoch`;
- model ZP i jego wariant;
- `parallax_error_inflation`;
- estymator i L;
- preset ramki;
- `parallax_min_mas` z S3.

**Wejścia od S5 (tylko do mocka, D11):**
- funkcja jasności i rozkład koloru trasera: M_G i (BP−RP)_0 dla RC plus tło
  RGB;
- ekstynkcja A_0(x): mapa Edenhofer albo uproszczony model z S5 (do
  wcześniejszych testów);
- okna selekcji S5 zapisane w ϖ_c.

**Wyjścia — kolumny:**
- produkt 1: `parallax_mas` (surowa), `parallax_error`, `parallax_zp_mas`,
  `zp_origin`;
- produkt 2: `r_lo_pc`, `r_med_pc`, `r_hi_pc`, `dist_origin`, `dist_flag`,
  `dist_pc` (alias), `x_pc/y_pc/z_pc` (z `r_med_pc`), `xgc_pc/ygc_pc/zgc_pc`.

ϖ_c i σ_c nie są kolumnami. Odtwarza je `corrected_parallax()`, bo jest
jedynym miejscem ZP i mnożnika.

**Wyjścia — API (Python).** Funkcje dla wierszy:
- `corrected_parallax(rows, config) → (varpi_c, sigma_c, zp, zp_origin)`.
  Konwencja: **ϖ_c = ϖ − zp** (zp to `parallax_zp_mas`);
- `parallax_loglike(varpi_c, sigma_c, r_pc)`: gaussowska w ϖ, wektorowa
  (gwiazdy × siatka r);
- `selection_threshold_corrected(rows) = parallax_min_mas − zp`: próg S3 w
  przestrzeni ϖ_c.

Funkcje punktowe (populacja, D12):
- `zp_model(G, bp_rp, l, b, solved=31, config)`: ten sam kod co dla wierszy,
  ale na dowolnej siatce. ν_eff wyliczane z BP−RP relacją empiryczną (D12),
  β z (l, b);
- `sigma_parallax_model(G, l, b, config)`: σ_ϖ już z mnożnikiem z D6;
- `parallax_cut_for_distance(D_pc) = 1000/D_pc`, `distance_for_parallax_cut(ϖ)`;
- `parallax_window_for_absmag(G, M_lo, M_hi, A_G)`: okno ϖ_c odpowiadające
  M_G ∈ [M_lo, M_hi] przy danym A_G (ze wzoru
  M = G − A_G + 5·log₁₀(ϖ_c/100), ϖ w mas);
- `prob_parallax_in_window(r_pc, lo, hi, sigma, dzp=0)`: P(lo < ϖ_c < hi | r)
  = Φ((hi − ϖ_t)/σ) − Φ((lo − ϖ_t)/σ), gdzie ϖ_t = 1000/r + dzp. dzp to
  różnica zp_true − zp_model, używana w testach systematyki.

Pozostałe: `estimate(rows, config) → DistanceResult`,
`sample_distances(rows, n, seed)` (tylko do wizualizacji),
`mock_parallaxes(...)` (D11).

**Manifest (`distance`, `parallax`, `frame`, `hipparcos`):**
- estymator, wersja, kwantyle, L i kryterium jego wyboru;
- `parallax_zp_method` z wersją pakietu, wariant ZP, polityka „poza
  zakresem” i ε przycięcia, mnożnik błędów;
- źródło i data budowy modelu σ_ϖ oraz relacji ν_eff(BP−RP), z sumą
  kontrolną;
- 5 parametrów `Galactocentric` i wersja astropy;
- `gaia_ref_epoch`, promień i |ΔG| dla Hipparcosa.

## Decyzje

**D1. Podział ról: paralaksa dla fitu, EDSD dla obrazu.**
- S5 fituje w przestrzeni paralaks:
  ln L = Σ_i ln ∫ p(ϖ_c,i | r)·ν(r, l_i, b_i)·r² dr − Λ, gdzie
  Λ = ∫ ν(x)·P_sel(x) dV.
- Prawdopodobieństwo selekcji P_sel(x) całkuje po populacji (G, kolor) w
  punkcie x. Używa przy tym `zp_model`, `sigma_parallax_model` i
  `prob_parallax_in_window`, a nie danych pojedynczych gwiazd (D12).
- Wszystkie cięcia zależne od odległości S5 wykonuje na ϖ_c (decyzja
  koordynatora). Dzięki temu wchodzą do modelu jako warunki na ϖ_c.
- **`r_med` nie bierze udziału w żadnej selekcji do fitu.**
- Uzasadnienie (symulacja `scratchpad/s2/fwd.py`, potwierdzona przez
  weryfikatora): fit w przestrzeni paralaks daje h = 298–301 pc, fit na
  r_med do 342 pc przy σ = 0,3 mas.
- *Odrzucone:* fit lub histogram na próbkach posteriorów EDSD.

**D2. `DistanceResult`.** r_lo / r_med / r_hi to kwantyle 0,1587 / 0,5 /
0,8413 posteriora, jak w BJ 2021 i jak `distance_gspphot_lower/upper` w DR3
(percentyle 16/84, mediana; Andrae i in. 2022). *Odrzucone:* moda + HDI.

**D3. Estymator katalogu: `edsd_prior`, prior r²·exp(−r/L), L globalny.**
- Kwantyle z CDF na siatce w log r.
- Prior izotropowy jest obciążony zależnie od |b| przy dużym f, więc r_med
  służy tylko do obrazu (D1).
- L wybierany na mocku spośród {0,47; 0,8; 1,35} kpc: najmniejsza mediana
  |Δz|/|z| dla f < 0,2. Wybór i kryterium trafiają do manifestu.
- *Odrzucone:* L(l,b) i GGD, bo są dopasowane do mocka z założonym dyskiem.
  Także hybryda inwersja/EDSD.

**D4. Ujemne i bliskie zeru paralaksy.**
- EDSD liczone zawsze. Gdy posterior numerycznie się zeruje: NaN i
  `no_solution`.
- Inwersja: ϖ_c ≤ 0 albo f > 0,1 → NaN i `inversion_invalid`; przy
  ϖ_c − σ_c ≤ 0 tylko `r_hi` = NaN.
- Wiarygodność przyjmuje każde ϖ.

**D5. Korekta zero-pointu: w każdej gałęzi, która zużywa surową paralaksę Gai.**
Nigdy przy gotowych odległościach (BJ, StarHorse, GSP-Phot; GSP-Phot używa
już paralaks z korektą Lindegrena wg Andrae i in. 2022).

- *Model `lindegren2021_dr3`.*
  - Pakiet `gaiadr3-zeropoint`, wersja przypięta przy instalacji i zapisana
    w manifeście.
  - `load_tables()`, potem `get_zpt(..., _warnings=False)`.
  - ϖ_c = ϖ − zp.
- *Maska przed wywołaniem.* Do pakietu idą tylko wiersze z
  `astrometric_params_solved` ∈ {31, 95} i skończonymi wejściami (pakiet
  rzuca `ValueError` dla całej partii). Pozostałe:
  - 2p → `zp_origin = none`, `dist_flag = no_parallax`;
  - 5p/6p z brakującym wejściem → `global_fallback` (−0,017 mas, jak BJ 2021
    dla źródeł bez G).
- *Poza zakresem stosowalności — opcja (ii): własne przycięcie do wnętrza
  zakresu, flaga `lindegren2021_clamped`. To nasza decyzja, nie zachowanie
  pakietu.*
  - Przycinamy G do [6 + ε_G; 21 − ε_G] z ε_G = 10⁻³ mag, ν_eff do
    [1,1 + ε_c; 1,9 − ε_c] i pseudocolour do [1,24 + ε_c; 1,72 − ε_c] z
    ε_c = 10⁻⁴ µm⁻¹. Potem wywołujemy pakiet z `_warnings=False`.
  - Przycięcie musi być do **wnętrza**, bo pakiet traktuje granice włącznie
    jako poza zakresem i zwróciłby NaN.
  - W G wynik praktycznie równa się wartości brzegowej pakietu, bo pakiet
    sam obcina węzły tabeli.
  - W kolorze świadomie **różni się** od pakietu, który przy
    `_warnings=True` ekstrapoluje liniowo przez człony min/max.
  - Dlaczego przycięcie: wynik jest ograniczony, przewidywalny i taki sam w
    `zp_model` (populacja) i w `corrected_parallax` (wiersze).
  - *Odrzucone:* opcja (i), ekstrapolacja pakietu z wyciszonymi
    ostrzeżeniami. Daje nieograniczony zp dla skrajnych kolorów, a i tak nie
    wiemy, co robił BJ 2021 z kolorem poza zakresem.
  - Dla traserów S5 (RC: G 9–12, kolor w zakresie) polityka nie ma znaczenia.
    Dotyczy wierszy katalogu do viewera.
- *Wariant testowy `zinn2021_bright`* (nie domyślny):
  - zp_Zinn(G) = zp_L21 + Δ(G), gdzie Δ = 0,015 mas dla G ≤ 10,0, liniowo do
    0 przy G = 11,5, a powyżej 0;
  - skutek: ϖ_c,Zinn = ϖ_c − Δ, czyli paralaksy jasnych gwiazd **maleją**,
    a odległości rosną (Zinn i in. 2021: paralaksy po korekcie Lindegrena są
    o 15 ± 3 µas za duże dla G ≲ 10,8; próbka 9 ≲ G ≲ 13);
  - rampa usuwa skok w środku zakresu RC. Jej kształt to nasze założenie,
    nie wynik Zinna;
  - działa identycznie w `zp_model`.
- *Strażnik wydania:* biała lista wydań per model; dla DR4 kolejność jak w
  S4 (oficjalna recepta → `qso_global_offset`).

**D6. Błędy paralaksy.** `parallax_error_inflation` (domyślnie 1,0, w
manifeście) jest stosowany w `corrected_parallax` i w
`sigma_parallax_model`. Wartość ≠ 1 przyjmujemy dopiero po teście S4.
El-Badry i in. 2021: do ~30% dla izolowanych jasnych źródeł.

**D7. Próbki odległości: tylko wizualizacja i propagacja.**
- Ziarno: `hash(source_id)`; dla Hipparcosa `hash(hip) + 2⁶³`.
- Próbek nie zapisujemy.
- Ostrzeżenie „nie do estymacji gęstości” w docstringu i w manifeście.

**D8. Kiedy który estymator.**
- Katalog: `edsd_prior`.
- `parallax_inversion`: regresja 20 pc i porównania.
- `gspphot`: kontrola w S4, bez ZP (D5). Znane zaniżenie odległości powyżej
  ~2 kpc.
- Kolumny porównawcze tylko w pliku walidacyjnym.

**D9. Układ galaktocentryczny.**
- Preset astropy przypięty jako **`v4.0`**: R☉ = 8,122 kpc, z☉ = 20,8 pc,
  v☉ = (12,9; 245,6; 7,78) km/s, roll = 0°, galcen_coord =
  (266,4051°; −28,936175°).
- z☉ realizowane obrotem; Słońce leży w (−8121,97; 0; 20,8) pc.
- Dla S5: z☉ mierzyć na heliocentrycznym `z_pc`, nie na `zgc_pc`.

**D10. Hipparcos.**
- Odległość: estymator główny na paralaksie Hipparcos-2, bez ZP. Wiersze
  wyłączone z fitu S5.
- Epoka: propagacja J1991.25 → `gaia_ref_epoch` (J2016.0 / J2017.5).
- Dopasowanie: promień 1″, |ΔG| < 1 mag. Niejednoznaczność: zostaje wiersz
  Gai, przypadek trafia do raportu.
- Priorytet: Gaia 5p/6p wygrywa. Hipparcos zostaje tylko bez odpowiednika
  albo przy odpowiedniku 2p.
- Kontrola krzyżowa:
  - DR3: `gaiadr3.hipparcos2_best_neighbour`;
  - DR4: HIP → `hipparcos2_best_neighbour` → `dr3_neighbourhood` → DR4.

**D11. Mock do testu S2 → S5.** `mock_parallaxes(disc_model, tracer_model,
extinction_model, config, seed)`:
- **Pozycje:** z modelu dysku (h = 300 pc, z☉ = 20,8 pc, opcjonalnie gruby
  dysk) w objętości większej niż objętość fitu, z marginesem na rozmycie.
- **Fotometria:** M_G i (BP−RP)_0 z modelu trasera S5. A_0(x) z modelu
  ekstynkcji S5, przeliczone na A_G i E(BP−RP) tym samym kodem co w S5.
  Wynik: G, BP−RP.
- **Astrometria:**
  - ν_eff z BP−RP (relacja z D12), ecl_lat z pozycji;
  - zp_true = `zp_model(...)` + dzp, z wariantami dzp ∈ {0; Zinn-podobny Δ(G);
    ±0,010 mas globalnie};
  - σ_ϖ = `sigma_parallax_model(G, l, b)`;
  - ϖ = 1000/r + zp_true + N(0, σ_ϖ_true). σ_ϖ_true = σ_ϖ albo σ_ϖ × 1,2
    (test mnożnika).
- **Selekcja:** próg S3 na surowej ϖ.
- **Zapis:** schemat katalogu, więc przechodzi przez cały pipeline.
- **Zasada:** mock i fit używają **tych samych** funkcji `zp_model` i
  `sigma_parallax_model`. Warianty dzp i σ_true różne od σ_model to jedyny
  sposób, żeby mock sprawdził systematykę, a nie samego siebie.

**D12. Modele populacyjne zp i σ_ϖ.**
- **σ_ϖ(G, l, b):** empiryczna mediana `parallax_error` (po mnożniku z D6)
  dla 5p/6p.
  - Przedziały: G co 0,25 mag w zakresie 6–21; kierunek jako piksel HEALPix
    poziomu 3 (768 pikseli), żeby oddać wzór skanowania.
  - Puste lub małe komórki (< 20 gwiazd) dziedziczą wartość z przedziału
    (G, |β| co 10°).
  - Interpolacja liniowa w G.
  - Budowane z pobranych danych danego wydania (DR3, potem DR4) i zapisywane
    jako tablica z sumą kontrolną w manifeście.
  - *Odrzucone:* analityczna σ(G) z dokumentacji Gai. Nie oddaje zależności
    od kierunku ani przeszacowania przy jasnych gwiazdach.
- **ν_eff(BP−RP):** empiryczna mediana `nu_eff_used_in_astrometry` w
  przedziałach BP−RP co 0,05 mag (5p). Potrzebna, bo w populacji mamy kolor
  trasera, a nie ν_eff.
  - Kontrola: rozrzut ν_eff w przedziale przeniesiony na zp < 3 µas dla RC.
  - Do weryfikacji: przy dużej ekstynkcji BP−RP zawiera poczerwienienie,
    a ν_eff mierzy kolor obserwowany. Relacja z obserwowanym BP−RP jest więc
    spójna, ale S5 musi podawać kolor **obserwowany**, nie odczerwieniony.
- **zp_model:** ten sam kod co `corrected_parallax` (z przycięciem z D5),
  wywołany z ν_eff(BP−RP) i β(l, b), `solved = 31`.
- **Selekcja wyrażona w ϖ_c:**
  - objętość d < D_max ⇒ ϖ_c > 1000/D_max (`parallax_cut_for_distance`);
  - okno M_G ⇒ okno w ϖ_c zależne od G i A_G (`parallax_window_for_absmag`);
  - S5 łączy je z progiem S3 w przestrzeni ϖ_c i liczy P_sel przez
    `prob_parallax_in_window`.
  - Dla RC (ϖ ≥ 0,9 mas, σ ~ 0,02 mas) próg S3 0,4 mas leży > 20σ dalej i
    praktycznie nie działa. Aktywne są cięcia D_max i okno M_G.
  - A_G zależy od r, więc okno w ϖ_c jest uwikłane. Rozwiązanie po stronie
    S5: na siatce r, bo `prob_parallax_in_window` przyjmuje r.

## Zadania

1. `DistanceResult`, rejestr, enum `dist_flag`, szkielet testów. (1 dzień)
2. Warstwa paralaksy: maska 31/95, przycięcie do wnętrza z flagą
   `clamped`, fallback, mnożnik, biała lista, wariant `zinn2021_bright` z
   rampą, `selection_threshold_corrected`, manifest. Testy: mieszana partia
   (3, 31, 95, NaN), G = 6,0, G = 21,0, G = 5,5, ν_eff = 1,95, ν_eff = 1,05,
   pseudocolour = 1,80, znak wariantu Zinna. (1,5 dnia)
3. `parallax_loglike`, `parallax_inversion`, `prob_parallax_in_window`,
   `parallax_cut_for_distance`, `parallax_window_for_absmag`. (1 dzień)
4. `edsd_prior`: siatka, CDF, kwantyle, sampler, benchmark na 10⁶ wierszy.
   Wybór L po zadaniu 7. (2 dni)
5. Modele populacyjne (D12): tablica σ_ϖ(G, HEALPix 3), relacja
   ν_eff(BP−RP), `zp_model`, zapis i manifest. Na DR3 od razu, na DR4 po
   pobraniu. (1,5 dnia)
6. Kolumny galaktocentryczne (`v4.0`), manifest, testy. (1 dzień)
7. Mock D11 z wariantami dzp i σ_true; uzgodnienie interfejsu modeli
   trasera i ekstynkcji z S5; raport obciążenia r_med (podstawa wyboru L).
   (2 dni)
8. Hipparcos: epoka, dopasowanie, priorytety, raport, kontrole DR3/DR4.
   (2 dni)
9. Walidacja DR3 z `external.gaiaedr3_distance` (`r_med_geo`, `r_lo_geo`,
   `r_hi_geo`). (1 dzień)
10. (opcjonalnie) `gspphot` porównawczo. (0,5 dnia)

## Kryteria akceptacji

- **Interfejs:** każdy wiersz ma `dist_origin`, `dist_flag` i `zp_origin`.
  Przy `ok` zachodzi `r_lo ≤ r_med ≤ r_hi`, a wartości są skończone.
- **Warstwa paralaksy:**
  - partia mieszana przechodzi bez wyjątku;
  - w zakresie stosowalności wynik identyczny z `get_zpt`;
  - dla G = 6,0, G = 21,0, ν_eff = 1,95, pseudocolour = 1,80 wynik
    skończony, równy `get_zpt` w punkcie przyciętym, z flagą `clamped`
    (żadnego NaN);
  - dla G = 5,5 zp różni się od wartości przy G = 6,001 o < 1 µas;
  - konfiguracja spoza białej listy kończy się błędem.
- **Znak Zinna:** dla G = 9 ϖ_c,Zinn = ϖ_c − 0,015 mas (± 10⁻⁶); dla
  G = 12 ϖ_c,Zinn = ϖ_c; dla G = 10,75 różnica 0,0075 mas.
- **Spójność:**
  - ϖ_c i σ_c w EDSD bitowo równe `corrected_parallax()`;
  - `zp_model` z prawdziwym ν_eff, β i G wiersza bitowo równe zp wiersza;
  - `sigma_parallax_model` odtwarza medianę `parallax_error` w każdej
    komórce z ≥ 20 gwiazdami.
- **Przeliczenia selekcji:**
  - `prob_parallax_in_window` zgodne z MC (10⁶ losowań) z dokładnością
    10⁻³;
  - `parallax_window_for_absmag` odwraca wzór na M_G z dokładnością
    10⁻⁶ mag.
- **Inwersja:** kwantyle zgodne z MC z dokładnością 0,5% dla
  f ∈ {0,01; 0,05; 0,1}.
- **EDSD:**
  - CDF w kwantylach ± 0,001;
  - moda zgodna z równaniem sześciennym (Bailer-Jones 2015) z dokładnością
    10⁻³;
  - przy σ → ∞ mediana → 2,674·L ± 0,5%;
  - dla ϖ/σ ∈ [−3; 0] wynik skończony, a NaN tylko z `no_solution`.
- **20 pc (do 1.7.1):**
  - `parallax_mas == ϖ_stare` dokładnie dla wspólnych `source_id`; każda
    różnica to błąd danych;
  - |1000/ϖ_stare − r_med| ≤ 3·(r_hi − r_lo)/2 dla ≥ 99% gwiazd, a reszta
    wyjaśniona (oczekiwane: duże |zp|/σ);
  - raport rozkładu (ϖ_stare − ϖ_c)/σ.
- **Mock (wspólne z S5):**
  - przy dzp = 0 i σ_true = σ_model łańcuch odtwarza h_thin z błędem < 3% i
    z☉ < 3 pc;
  - przy dzp ≠ 0 lub σ_true ≠ σ_model raportowane przesunięcie h (wejście do
    budżetu systematyki S5), bez progu zaliczenia.
- **Wydajność:** 10⁶ wierszy EDSD w < 60 s na rdzeń (do potwierdzenia).
- **BJ 2021:** dla f < 0,1 mediana |Δr|/r < 1%; dla 0,1 < f < 0,3 raport
  różnic.
- **Galaktocentryczne:** Słońce → (−8121,97; 0,00; 20,80) ± 0,01 pc;
  helio → galacto → helio z błędem < 10⁻³ pc; manifest kompletny.
- **Hipparcos:**
  - brak par bliżej niż promień dopasowania;
  - ≥ 99% zgodności z `hipparcos2_best_neighbour` w DR3 (próg do
    kalibracji);
  - liczba wierszy w 20 pc zgodna z obecnym katalogiem albo różnice
    wyjaśnione.

## Ryzyka i otwarte pytania

- **Zero-point DR4** nieznany przed 2.12.2026. Mock z dzp = ±0,010 mas daje
  budżet systematyki h.
- **Systematyka ZP jasnych gwiazd** (Zinn): wariant testowy z rampą. Kształt
  rampy to założenie.
- **Model σ_ϖ z danych traserów** zawiera ich własny rozkład jasności. Dla
  całki populacyjnej to właściwe, ale komórki z małą liczbą gwiazd są
  zaszumione (fallback do |β|).
- **Relacja ν_eff(BP−RP)** a ekstynkcja: patrz D12; do weryfikacji na DR3.
- **Niedoszacowane σ_ϖ** zawężają splot. Mock z σ_true = 1,2·σ_model mierzy
  wpływ.
- **Hipparcos:** układy podwójne, wysoki RUWE Gai. Otwarte: kiedy
  preferować Hipparcosa.

## Zmiany w kontrakcie

1. **Podział ról dla S5 (decyzja koordynatora).**
   - Do fitu S2 dostarcza dwa zestawy funkcji. Wierszowe:
     `corrected_parallax`, `parallax_loglike`,
     `selection_threshold_corrected`. Populacyjne: `zp_model`,
     `sigma_parallax_model`, `parallax_cut_for_distance`,
     `parallax_window_for_absmag`, `prob_parallax_in_window`.
   - `r_lo/r_med/r_hi` i `sample_distances` służą tylko do viewera,
     ekstynkcji w punktach i statystyk opisowych.
   - **Wszystkie cięcia zależne od odległości S5 wykonuje na ϖ_c.**
     Do przepisania w S5 v1:
     - D4: okno M_G,0 liczone z r_med → okno w ϖ_c przez
       `parallax_window_for_absmag`, z A_G(r) na siatce r;
     - D6: M_W z r_med → z ϖ_c;
     - D7: d < D_max na r_med → ϖ_c > 1000/D_max;
     - D9: ln L po K = 32 próbkach → całka z `parallax_loglike`, a Λ przez
       P_sel z funkcji populacyjnych;
     - „Zmiany w kontrakcie” 1: `sample_distances` nie do fitu.
   - Do przepisania w planie v3: 1.2 (statystyka na próbkach) i 2.5.
   - S5 podaje kolor **obserwowany** do `zp_model` (D12).
2. **Zero-point w każdej gałęzi na surowej paralaksie Gai**, nigdy przy
   gotowych odległościach (GSP-Phot ma już ZP — Andrae i in. 2022). Do
   aktualizacji: plan v3 1.2 i 2.1, S3 v1 (opis kolumn ZP: „warstwa paralaksy
   S2” zamiast „gałąź `parallax_inversion`”). S4 v1 jest zgodny; jego
   pozycja „sprawdzić ZP w GSP-Phot” jest zamknięta.
3. **Nowe kolumny:**
   - `dist_flag` (category);
   - `parallax_zp_mas` (float32);
   - `zp_origin` (category: `lindegren2021_dr3`, `lindegren2021_clamped`,
     `global_fallback`, `global_constant`, `qso_global_offset`,
     `dr4_official`, `none`);
   - `parallax_error` i `bp_rp` (float32, jeśli S3 ich nie trzyma).
   S1 dopisuje kolumny `category`.
4. **Nowe artefakty obok katalogu:** tablice σ_ϖ(G, HEALPix 3) i
   ν_eff(BP−RP) dla danego wydania. Format i miejsce ustala S1, sumy
   kontrolne trafiają do manifestu.
5. **Kwantyle:** 0,1587 / 0,5 / 0,8413, mediana (zgodne z S4 T1/T2 i z
   GSP-Phot).
6. **Ramka:** preset astropy `v4.0` (plan v3 1.4 do aktualizacji).
7. **Epoka Hipparcos → Gaia = `gaia_ref_epoch`.** S1 v1 l. 199: `healpix`
   wierszy Hipparcos-only na tej epoce (NESTED, poz. 12).
8. **Hipparcos** (plan v3 1.5): estymator główny na paralaksie Hipparcosa,
   bez ZP.

## Odpowiedź na recenzję

Runda 1: wszystkie uwagi zamknięte lub zamykane poniżej (3 → N2/N4, 5 → N5,
6 → N6).

Runda 2:

1. **[ISTOTNA] Interfejs nie wystarcza do selekcji i normalizacji —
   przyjęte, zgodnie z decyzją koordynatora.**
   - Dodane funkcje populacyjne (D12; „Wyjścia — API”): `zp_model`,
     `sigma_parallax_model` (jedno źródło dla mocka i fitu, zasada budowy z
     danych w przedziałach G × HEALPix 3), relacja ν_eff(BP−RP) i
     przeliczenia odległość/M_G ↔ okno w ϖ_c.
   - Wybrałem rekomendowane cięcie wprost na ϖ_c > 1000/D_max zamiast
     odwracania r_med. Jest prostsze, a r_med nie bierze udziału w selekcji.
   - W „Zmianach w kontrakcie” 1 wymienione S5 D4/D6/D7/D9 do przepisania.
   - Zgoda, że dla RC aktywne są D_max i okno M_G, a nie próg S3 (D12).
   - Zapis „S_i(r)” z D1 zastąpiony przez P_sel(x) populacyjne.
2. **[ISTOTNA] Polityka poza zakresem — przyjęte, opcja (ii).**
   - Własne przycięcie do wnętrza zakresu (ε_G = 10⁻³ mag, ε_c = 10⁻⁴),
     flaga `lindegren2021_clamped`, nazwane jako własna decyzja.
   - Jawnie odnotowane, że w kolorze różni się od pakietu, który ekstrapoluje
     liniowo.
   - Usunięte zdanie, że tak robi pakiet i BJ 2021.
   - Testy G = 6,0 / 21,0 / ν_eff = 1,95 / pseudocolour = 1,80 w zadaniu 2 i
     w kryteriach.
3. **[DROBNA] Mock wymaga fotometrii — przyjęte.**
   - W D11 wskazane wejścia od S5 (model trasera, model ekstynkcji).
   - σ_ϖ z komórek (G, HEALPix 3) z fallbackiem (G, |β|).
   - Warianty dzp (0, Zinn-podobny, ±10 µas) i σ_true = 1,2·σ.
4. **[DROBNA] Znak Zinna — przyjęte.** Wzór ϖ_c,Zinn = ϖ_c − Δ(G),
   `parallax_zp_mas` += Δ, rampa 0,015 mas przy G ≤ 10 → 0 przy G = 11,5
   (opisana jako założenie), test znaku w kryteriach.
5. **[DROBNA] Tautologia 20 pc — przyjęte.** Równość `parallax_mas ==
   ϖ_stare` i warunek |1000/ϖ_stare − r_med| ≤ 3·(r_hi − r_lo)/2 dla ≥ 99%,
   reszta wyjaśniona. Dodałem próg 99% zamiast 100%: dla gwiazd z
   |zp|/σ > 3 warunek może legalnie nie przejść.
6. **[DROBNA] GSP-Phot — przyjęte, zamknięte.** ZP Lindegrena wbudowany
   (Andrae i in. 2022), `lower/upper` = percentyle 16/84 (D2, D5, D8,
   Zmiany 2).

---
Źródła:
- PyPI `gaiadr3-zeropoint` i kod `zpt.py` (kopia w desitarget);
- Bailer-Jones i in. 2021 (arXiv:2012.05220), 2018 (arXiv:1804.10121);
- Bailer-Jones 2015 (arXiv:1507.02105);
- Astraatmadja & Bailer-Jones 2016 (arXiv:1609.07369);
- Zinn i in. 2021 (arXiv:2101.07252);
- El-Badry i in. 2021;
- Andrae i in. 2022 (arXiv:2206.06138);
- dokumentacja DR3 CU8 (GSP-Phot);
- astropy `galactocentric_frame_defaults`;
- ESA „Gaia DR4 content”;
- archiwum GDR3, sekcja cross-matches.
