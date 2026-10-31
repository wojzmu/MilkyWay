# S5 — Pomiar dysku: pył, trasery, fit
Wersja: v3 · Etap: 2 (kod i test na mocku w listopadzie; przebieg DR3 jako
nieblokujący kamień milowy; fit główny na DR4 po G3b z S4 v2)

## Cel

Zmierzyć pionowy profil gęstości red clump (RC) w ~1,1 kpc wokół Słońca na
Gaia DR4. Wynikiem są trzy wielkości:
- `h_1` — jeden wykładnik dopasowany na 150–450 pc. To miara główna: dane
  dobrze ją określają, niezależnie od tego, jak rozłożymy je na składniki;
- **profil wiarygodności** `h_thin` dla kilku ustalonych wartości `h_thick`;
- `z_sun` z fitu na pełnym zakresie |z|, z jawnym modelem asymetrii N/S.

Fit liczymy w przestrzeni paralaks (forward modelling). Korekta pyłu pochodzi z
mapy Edenhofer et al. 2024. Każde cięcie zależne od odległości jest przedziałem
ϖ_c wyznaczonym **dokładnie** tą samą funkcją obserwabli w danych i w modelu.
Modele porównujemy w obserwablach. Wynik musi być odtwarzalny z manifestu.

## Zakres / poza zakresem

**W zakresie:**
- `extinction.py` (jedna mapa) i odczerwienienie G/BP/RP;
- model trasera Φ: RC + tło RGB;
- okna selekcji w ϖ_c i siatka normalizacji W(r, kierunek);
- fit, porównanie modeli, mock, budżet systematyki;
- widok z boku w viewerze (filtr `tracer`).

**Poza zakresem:**
- inne mapy pyłu i blending (3.2);
- flara i warp (3.4);
- kinematyka;
- EDSD w ficie: `r_med` służy tylko viewerowi (S2 D1);
- `gaiaunlimited` w ścieżce głównej (dla RC tylko kontrola, D6).

## Wejścia i wyjścia

**Od S2 v3 (D1, D11, D12), bez zmian API:**
- wiersze: `corrected_parallax`, `parallax_loglike`;
- populacja: `sigma_parallax_model(G, l, b)` z mnożnikiem k(G) z S4 T8,
  `prob_parallax_in_window(r, lo, hi, σ, dzp)`,
  `parallax_window_for_absmag(G, M_lo, M_hi, A_G)`,
  `parallax_cut_for_distance`;
- `zp_model` tylko w wariantach systematyki (D8);
- `mock_parallaxes` i wariant `zinn2021_bright`.

**Od S1/S3:**
- Parquet przez DuckDB, kolumny: `phot_g_mean_mag`, `bp_rp`,
  `phot_bp_mean_mag`, `phot_rp_mean_mag`, `parallax`, `parallax_error`,
  `ruwe`, `astrometric_params_solved`, `l`, `b`;
- selekcja pobierania `parallax > 0.5 AND phot_g_mean_mag < 19`;
- manifest.

**Od S4 v2:**
- G1b przed przebiegiem DR3;
- G2 i G3a przed pracą na DR4, G3b przed Z13;
- wariant ZP ±15 µas.

**Zewnętrzne** (nie z archiwum ESA, więc wyłączenie archiwum 25.11–2.12 ich
nie blokuje):
- mapa `dustmaps.edenhofer2023`: średnia ~3,2 GB, próbki ~19 GB;
- `Fitz19_EDR3_extinctionlawcoefficients.zip`;
- krzywa ZGR23 (Zenodo 10.5281/zenodo.6674521).

**Do S2 (wejście mocka D11):** Φ, model ekstynkcji (mapa albo uproszczony
dysk pyłowy), definicje okien.

**Wyjścia:**
- kolumny (sekcja „Zmiany w kontrakcie”);
- `disk_fit.json`: parametry, profile, porównanie modeli, warianty, ziarna,
  hashe;
- raport;
- manifest: sekcje `extinction` i `fit`.

## Fakty (z v1–v2, zweryfikowane przez recenzenta)

**Mapa Edenhofer 2024:**
- 69–1250 pc, 516 przedziałów logarytmicznych, N_side 256;
- jednostki E w skali ZGR23. Oczekiwane E→A_0 ≈ 2,7 przy 550 nm; autorzy
  podają 2,8 przy 540 nm;
- artefakty na 600/900/1200 pc, zaniżenie ekstynkcji w gęstych obłokach,
  niepewność ~10%;
- `integrated=True` z σ tylko z próbek. Poza centrami skrajnych przedziałów
  zwraca NaN.

**Fitz19:** k_X(X, A_0), ważne dla −0,06 < X < 2,5 i 0,01 < A_0 < 20.

**RC:**
- M_G = 0,44 ± 0,20 (Hawkins+2017), locus (BP−RP)_0 ≈ 1,2;
- n₀ ≈ 9·10⁻⁵ pc⁻³;
- G ≈ 4,7 (70 pc) … 10,6 (1,1 kpc) bez pyłu, ≲ 13,8 z pyłem do A_0 = 3.
  Limit G < 19 jest więc nieaktywny, a aktywny jest jasny kraniec G > 6
  (RC bliżej ~95–165 pc wypada).

**Liczności i statystyka** (rachunki własne,
`scratchpad/s5v3/{win,fish4}.py`, zgodne z recenzją):
- ~1,3·10⁵ RC w objętości fitu, ~7·10⁴ w oknie 150–450 pc;
- σ_stat(h_1) ≈ **5 pc**; σ_stat(z_sun) ≈ 1–2 pc (8 realizacji Poissona,
  model z D9).

### Przedział oczekiwany dla h_1 (tabela; `scratchpad/s5v3/tab.py`)

h_1 to jeden wykładnik dopasowany (KL, bez wagi objętości) do profilu modelu
na 150 < |z| < 450 pc. Udziały f to **lokalne udziały gęstości w płaszczyźnie**.
Khanna: udziały masowe 34/66 przy R_d = 4,24 i 2,66 kpc przeliczone na
gęstość w R = 8,2 kpc (ρ₀ ∝ M·R_d⁻²·e^{−R/R_d}/2h) dają f_local = 0,37.

| Model (h_thin / h_thick / f_local) | Traser | h_1 [pc] | W obwiedni? |
|---|---|---|---|
| Jurić+2008 (300/900/0,12) | karły SDSS | 348 | tak |
| Everall+2022 (260/693/0,124) | karły Gaia | 302 | tak |
| Khanna+2024, 2 dyski (180/480/0,37) | RC | 292 | tak |
| Khanna+2024, 2 dyski, f = 0,66 (udział masowy, skrajny) | RC | 379 | tak (górny kraniec) |
| Yoldaş+2025, 1 wykładnik 295 | RC | 295 | tak |
| Yoldaş+2025 jako kształt Jurića przeskalowany do 295 na 0–1000 pc | RC | 279 | tak (dolny kraniec) |
| Bovy+2016, 280 | RC (APOGEE) | 280 | tak |
| Khanna+2024, 1 dysk z flarą (460) | RC | 460 | **nie** |
| Vieira+2023 (280/797/0,43) | podpróbka kinematyczna | 457 | **nie** |
| model mocka (300/900/0,10) | — | 340 | — |

- **Obwiednia** modeli z gęstości liczby gwiazd: 279–379 pc. Zapas ±15 pc
  (≈ 3σ_stat; rząd systematyki Everalla ±26 pc rozłożonej na oba krańce) daje
  **przedział testowy 265–395 pc**.
- **Wyłączone** z obwiedni:
  - Vieira: podpróbka wybrana kinematycznie, niewprost porównywalna (S4 v2);
  - jeden dysk Khanny: Khanna i in. wolą model dwudyskowy (do weryfikacji).
- **Szara strefa:** 395–470 pc (zgodna z jednym dyskiem Khanny) i 250–265 pc.
  Prowadzi do diagnozy, a nie do automatycznego „nie”.

## Decyzje

**D1. Pył: w ścieżce głównej średnia mapy; 12 próbek posterioru jako
systematyka.** Bez zmian względem v2:
- `integrated=True`, `mode='mean'`;
- próbki czytane własnym czytnikiem `h5py` po paczkach HEALPix, tylko dla
  kandydatów i węzłów siatki W;
- dla każdej próbki pełne powtórzenie selekcji, W i fitu;
- `a0_err_mag = 0,1·A_0` wyłącznie informacyjnie.

Koszt w D8.

**D2. Krańce i artefakty mapy.** Bez zmian względem v2:
- r_min i r_max to centra skrajnych przedziałów;
- d < r_min → A(r_min)·d/r_min;
- d > r_max → A(r_max) z flagą;
- ekstynkcja zawsze liczona w 1000/ϖ_c;
- 600/900 pc: diagnostyka skorup i wariant D_max = 0,55 kpc;
- wariant 2 kpc jako kontrola krańca.

Dodane: ta sama reguła d > r_max obowiązuje w siatce W i w członie
gwiazdowym, które sięgają do ~1,3 kpc (D8).

**D3. E → A_0 → pasma.** Bez zmian względem v2:
- C(550) z krzywej ZGR23, potem tablica Fitz19 „top HRD”;
- iteracja, k(X; 0,01) dla A_0 < 0,01, przycięcie X z flagą;
- wariant: całkowanie ZGR23 po pasmach.

Dla siatki W (D5) iteracja jest **zbędna**, bo w modelu X = c węzła jest
znane. Mamy wprost A_G(r) = k_G(c, A_0(r))·A_0(r), a tak samo dla E. W danych
iteracja daje to samo X z dokładnością 0,001 mag (kryterium 1).

**D4. Trasery i okna.**
- Kandydaci i Φ (2D Gauss RC + liniowe tło RGB) jak w v2.
- Okno CMD: M_G,0 ∈ locus ± 2,5σ, (BP−RP)_0 ∈ locus ± 2,5σ (startowo
  [−0,1; 1,1] × [1,0; 1,4]).
- Okno Wesenheita: M_W = W_obs + 5 log₁₀(ϖ_c/100), gdzie
  W_obs = G − λ(BP−RP)_obs. λ to wartość Fitz19 dla RC przy X = 1,2 i A_0
  = 1; liczba i źródło trafiają do manifestu. Szerokość okna to locus ± 2,5σ
  z próbki niskoekstynkcyjnej, **bez poszerzania o dryf**.
  - Rezydualne A_G − λE nie znika przy dużym A_0. Model ujmuje je dokładnie:
    węzeł (M, c) w odległości r ma
    W_obs = M − λc + DM(r) + [A_G(r) − λE(r)].
  - Spadek skuteczności okna przy dużym A_0 jest więc w W, a nie w
    poszerzonym oknie, które wpuszczałoby więcej RGB.
- `tracer = rc` wymaga obu okien. Wariant bez mapy: samo okno Wesenheita +
  szerokie okno koloru surowego.
- Argument z v1 bez zmian: odległości pochodzą z paralaksy, więc domieszka RGB
  zmienia tylko populację.

**D5. Okna jako przedziały ϖ_c — dokładnie, bez przybliżenia E(r).**
- Dla piksela (l, b) i obserwabli (G, c_obs) każde cięcie to warunek
  g(ϖ) ∈ [lo, hi], gdzie g jest ściśle monotoniczne w ϖ. Powody:
  - całkowana mapa A_0(r) rośnie w r;
  - k zmienia się wolno z A_0, więc monotoniczność zachowuje się dla
    A_0 < 3, czyli w obszarze poza maską;
  - g dla M_G,0 to 5 log₁₀ ϖ − A_G(1000/ϖ);
  - dla koloru warunek E(1000/ϖ) ∈ [c_obs − c_hi, c_obs − c_lo];
  - dla Wesenheita g = 5 log₁₀ ϖ, bez pyłu w danych.
- Granice liczy funkcja `windows_in_parallax(pixel, G, c_obs)`: odwrotna
  interpolacja g na siatce r piksela. **Ten sam kod** selekcjonuje dane
  (gwiazda w oknie ⇔ ϖ_c,i ∈ przedział).
- Test sprawdza monotoniczność g w każdym pikselu. Jeśli się nie zgadza,
  liczymy sumę przedziałów na siatce.
- Selekcja to przecięcie przedziałów:

| Cięcie | Warunek na ϖ_c | Narzędzie |
|---|---|---|
| d < D_max = 1100 pc | ϖ_c > 0,909 | `parallax_cut_for_distance` |
| R_xy < 1000 pc | ϖ_c > cos b | wprost |
| okno M_G,0 | g_M(ϖ) ∈ [M_lo, M_hi] | `windows_in_parallax` |
| okno koloru | E(1000/ϖ) ∈ [·, ·] | `windows_in_parallax` |
| okno M_W | `parallax_window_for_absmag(W_obs, M_W,lo, M_W,hi, A_G=0)` | API S2 bez zmian |
| okna w z (M1, M2) | \|1000·sin b/ϖ + z_ref\| ∈ [z_lo, z_hi] | wprost |
| próg S3 | `selection_threshold_corrected` | nieaktywny (> 10σ) |

- **z_ref = 20,8 pc** jest stałą z manifestu. Okna w z nie zależą od z_sun,
  więc W liczymy raz, a z_sun występuje tylko w ν.
- `r_med` nie występuje nigdzie.

**D6. Selekcja niezależna od ϖ.** Bez zmian względem v2:
- |b| > 5°;
- maska kierunków A_0(r_max) > A_mask (2/3/4 mag);
- 6 < G < 19;
- S_q(G, piksel HEALPix 3) zawsze w W, wariant bez RUWE.

**D7. Objętość.** Bez zmian: D_max 1,1 kpc, R_xy < 1 kpc, |b| > 5°, maska.

**D8. Wiarygodność i numeryka normalizacji.**
- Człon gwiazdowy (poprawny wg recenzji):
  Σ_i ln ∫ p(ϖ_c,i | r)·ν(x)·r²·Φ(G_i − A_G(r) − DM(r), c_i − E(r)) dr.
  - Siatka r obejmuje ϖ_c,i ± 6σ_i, czyli r do 1000/(ϖ_c,i − 6σ_i), w
    przypadku krańcowym ~1,37 kpc.
  - Powyżej r_max obowiązuje A(r_max) (D2). ν poza objętością nie jest
    ucinane, bo gwiazdy mogą do niej wpaść przez szum paralaksy.
- Normalizacja: Λ = ∫ dΩ ∫ dr r²·ν(x)·S_dir·W(r, Ω), gdzie
  W = Σ_q w_q·S_q(G_q)·1[6 < G_q < 19]·P(ϖ_c ∈ ∩ okna_q | r).
  - **Siatka r:** logarytmiczna, krok 1%, od 90 pc do 1300 pc (~270
    węzłów). Uzasadnienie: P(ϖ_c > 0,909 | r) przy σ = 0,03 mas wynosi
    5,8·10⁻³ dla 1200 pc, 1,4·10⁻⁴ dla 1250 pc i 1,6·10⁻⁶ dla 1300 pc. Wkład
    powyżej 1300 pc < 10⁻⁵ Λ. Przy σ = 0,015 granica 1200 pc wystarczyłaby.
  - **Kwadratura (M, c) deterministyczna**, nie losowanie:
    - siatka tensorowa w oknie poszerzonym o 0,5 mag: krok 0,05 mag w M (64
      węzły) i 0,05 w c (18 węzłów), ~1150 węzłów;
    - wagi w_q = Φ(M_q, c_q)·ΔM·Δc, normalizowane;
    - zbieżność sprawdzana krokiem 0,025: zmiana Λ < 0,1% i h_1 < 0,3 pc.
      Brak szumu MC, a skoki przy G = 6 i na krawędziach S_q są rozdzielone
      przez gęstą siatkę.
  - **Kierunki:**
    - ścieżka główna N_side 128 (~1,8·10⁵ pikseli z |b| > 5°); P uśredniane
      po 4 podpikselach N_side 256 z własnym A, bo P jest nieliniowe w A;
    - systematyka (12 próbek mapy, warianty Z11) przy N_side 64 (4,5·10⁴
      pikseli, 16 podpikseli);
    - test zbieżności 64/128/256 na wycinku |b| < 15°: zmiana Λ < 0,3%.
  - **σ i S_q** zależą tylko od (G, piksel poziomu 3). Prekomputujemy je
    na siatce G co 0,05 mag i bierzemy z tablicy, bez interpolacji per
    element.
  - **Rola zp:** ϖ_c = ϖ − zp_row, więc ϖ_c | r ~ N(1000/r + dzp, σ), gdzie
    dzp = zp_true − zp_row.
    - W ścieżce głównej **dzp = 0**, a `zp_model` w ogóle nie jest
      wywoływane.
    - W wariantach (Zinn, ±15 µas) dzp(G_q, c_q + E(r), l, b) =
      `zp_model`_wariant − `zp_model`_bazowy.
    - Próg S3 jest nieaktywny (> 10σ), test to potwierdza.
  - **Koszt realistyczny** (do potwierdzenia benchmarkiem w Z8):
    - elementy: ścieżka główna 1,8·10⁵ × 4 × 270 × 1150 ≈ 2,2·10¹¹;
      wariant N_side 64 ×16 podpikseli też ~2,2·10¹¹; bez podpikseli
      1,4·10¹⁰;
    - przy ~100 ns/element w numpy (4–6 erfc, tablice, przecięcia) daje to
      ~6 h·rdzeń na siatkę główną i ~0,4 h·rdzeń na jedną siatkę N_side 64
      bez podpikseli;
    - 12 próbek mapy: ~5 h·rdzeń;
    - ~20 wariantów Z11: ~8 h·rdzeń.
  - **Jak się zmieścić:**
    - przetwarzanie po paczkach pikseli, równolegle na 8–16 rdzeniach: ścieżka
      główna < 1 h, systematyka kilka godzin w nocy;
    - piksele z A_0(r_max) < 0,05 bez podpikseli (większość |b| > 30°);
    - przy > 300 ns/element jądro w `numba`.
- W nie zależy od parametrów dysku, więc liczymy go raz na konfigurację
  (mapa, okna, wariant). Jeden krok MCMC to ~10⁷ mnożeń.
- *Odrzucone:* K = 100 losowań z Φ (schodkowe W, stały szum) i siatka r do
  1150 pc (ucina przeciek przez krawędź ϖ_c > 0,909, uwaga 4).

**D9. Modele, z_sun i asymetria N/S.**
- Zmienna u = z_obs + z_sun w ν. Okna fitu są w |z_obs + z_ref| (D5).
- **M1 (h_1):** jeden wykładnik na |z_obs + z_ref| ∈ [150; 450] pc, z_sun
  = z_ref (h_1 prawie nie zależy od z_sun: ±25 pc daje ±2 pc wg recenzji).
  Dodatkowo h_1 liczone z najlepszych M2-exp i M2-sech² tym samym fitem do
  przewidywanych liczb w oknie. To kontrola w obserwablach.
- **M2 (pełny zakres |z_obs + z_ref| < 1050 pc), dwa kształty rdzenia:**
  - M2-exp: (1−f)e^{−|u|/h_thin} + f e^{−|u|/h_thick};
  - M2-sech²: (1−f)sech²(u/2H) + f e^{−|u|/h_thick};
  - wolne parametry: n₀, h_thin (lub H), f, h_thick, **z_sun** i asymetria
    N/S.
- **Asymetria N/S:** ν → ν·(1 + a_k·sign(u)) w przedziałach |u|:
  [u_sym, 350), [350, 450), [450, 600), [600, 800), [800, 1050] pc, gdzie
  u_sym = 250 pc. W rdzeniu |u| < u_sym zakładamy symetrię.
  - **Degeneracja (wprost):** gdyby rdzeń miał własną asymetrię (osobne n₀
    dla N i S), z_sun i ta asymetria byłyby zdegenerowane. z_sun jest
    określone **tylko przy założeniu symetrii rdzenia**.
  - Rachunek własny (`fish3–5.py`, geometria D7, Poisson asymptotycznie):
    - fale N/S o amplitudzie 5–10% poza rdzeniem przesuwają z_sun o < 0,5 pc
      i h o < 1 pc;
    - bez parametrów a_k stała asymetria 5% przesuwa z_sun o ~−50 pc
      (sech²);
    - asymetria 2% **w rdzeniu** przesuwa z_sun o −6…−19 pc w zależności od
      kształtu i u_sym;
    - zły kształt rdzenia (exp dla prawdziwego sech²) przesuwa z_sun o
      ~−11 pc.
  - Wnioski:
    - z_sun raportujemy dla obu kształtów i dla u_sym ∈ {150, 250, 400} pc;
    - rozrzut tych wartości to systematyka z_sun, która dominuje nad
      σ_stat ≈ 1–2 pc.
- **M0** (sech² + stała na |z_obs + z_ref| < 200 pc): tylko kontrola. Według
  recenzji σ ≈ 5 pc, a 2% asymetrii daje przesunięcie ~26 pc.
- **h_thin:**
  - test pipeline'u: M2-exp z priorem h_thick ~ N(900, 150);
  - pomiar: profil ln L(h_thin) przy h_thick ∈ {500, 700, 900, 1200} pc;
  - h_thin^best(h_thick) i Δln L między h_thick.
- **Porównanie modeli w obserwablach (zamiast progu na parametrach):**
  - przewidywane liczby w przedziałach |z_obs + z_ref| (25 pc do 300 pc,
    potem 50 pc), osobno dla N i S, porównane z obserwowanymi: dewiancja
    Poissona i residua (obserwowane − przewidywane)/√przewidywane;
  - Δln L i ΔBIC między M1, M2-exp, M2-sech² oraz z asymetrią i bez;
  - różnica przewidywanej gęstości w 150–450 pc między modelami;
  - h_thin i H **nie są porównywane** jako liczby, bo mają różne znaczenie
    (recenzja: 364 vs 261 pc dla tego samego profilu).
  - Przy ~10⁵ gwiazd żaden gładki model nie przejdzie formalnego testu
    dobroci, bo dane mają fale pionowe. Dlatego raportujemy dewiancję i
    residua, a progiem jest tylko zgodność h_1 w oknie (kryterium 7).
- Niepewności: `emcee` z ziarnem; budżet systematyki osobno (Z11).

**D10. Kryteria naukowe.**
- **Testy pipeline'u** (ustalone przed fitem):
  - **h_1 ∈ [265; 395] pc** (obwiednia z tabeli);
  - **h_thin (M2-exp, prior h_thick 900) ∈ [250; 350] pc**;
  - **z_sun ∈ [10; 30] pc** (M2, u_sym = 250, wartość z lepszego kształtu
    wg ΔBIC).
- **Szara strefa → diagnoza** (warianty, maski, kształt rdzenia, u_sym):
  - h_1 ∈ [250; 265) ∪ (395; 470];
  - h_thin ∈ [230; 250) ∪ (350; 370];
  - z_sun ∈ [0; 10) ∪ (30; 40].
- **Pomiar:** h_1, profil h_thin(h_thick), z_sun z rozrzutem po wariantach,
  budżet systematyki.
- **Porównania bez progu:** S4 T5 (karły G/K; T5b vs h_1 ten sam typ
  miary), DR3 vs DR4, tabela literatury.
- **Traser zapasowy:** przed fitem ta sama tabela dla jego populacji.

## Czego S5 potrzebuje od S2 (API v3 bez zmian)

1. `prob_parallax_in_window`: wektorowe (numpy, broadcasting) dla paczek
   ~10⁸ elementów.
2. `parallax_window_for_absmag(W_obs, M_W,lo, M_W,hi, A_G=0)` dla
   Wesenheita. **Prośba o nowy parametr wycofana.**
3. `sigma_parallax_model(G, l, b)`: tablica (G co 0,05 mag × piksel poziomu
   3) z mnożnikiem k(G), osobno dla DR3 i DR4.
4. `zp_model` z kolorem obserwowanym, tylko w wariantach dzp.
5. `corrected_parallax` i `parallax_loglike` dla kandydatów.
6. Mock D11 z jasnymi RC (G < 6), tłem RGB i oknami z D5. S5 dostarcza
   `windows_in_parallax`, żeby mock i fit miały ten sam kod selekcji.

## Zadania

Każde ≤ 2 dni; Z1–Z10 w listopadzie (offline).

1. **Z1** Pobranie mapy i próbek (przed 25.11, nie z ESA). Układ HDF5,
   pamięć RAM, `distance_bounds`, testy krańców.
2. **Z2** `extinction.py` dla kandydatów, flagi, benchmark.
3. **Z3** C(550), Fitz19, iteracja, wariant ZGR23.
4. **Z4** Kolumny pochodne; λ(RC); tablica [A_G − λE](A_0) do modelu.
5. **Z5** Kalibracja okien i Φ (ϖ_c > 2, |b| > 20°, A_0 < 0,1, G > 6); locus
   w przedziałach G.
6. **Z6** S_q(G, piksel), maska (2/3/4 mag), kontrola `gaiaunlimited` na
   DR3.
7. **Z7** `windows_in_parallax` (D5) wspólne dla danych, W i mocka; test
   monotoniczności; selekcja `tracer`.
8. **Z8** Siatka W (D8):
   - kwadratura, siatka r do 1300 pc, paczki, równoległość;
   - benchmark ns/element i decyzja numpy/numba;
   - testy zbieżności (krok kwadratury, N_side, krok r);
   - test analityczny 1: bez pyłu i okien M, σ → 0, Λ = ∫ν dV walca;
   - test analityczny 2: gęstość płaska, σ = 0,03 mas, tylko cięcie
     ϖ_c > 0,909. Λ zgodne z ∫ r² Φ_N((1000/r − 0,909)/σ) dr z
     dokładnością 10⁻⁴.
9. **Z9** Likelihood M0, M1, M2-exp, M2-sech² z a_k, profile h_thick,
   porównanie w obserwablach, `disk_fit.json`.
10. **Z10** Mock S2 D11, **10 realizacji** na wariant, bias jako średnia:
    - (300/900/0,10), z_sun 20,8;
    - Khanna z lokalnym f = 0,37 (180/480) jako główny test degeneracji;
      f = 0,66 opisany jako skrajny;
    - sech² w rdzeniu;
    - fale N/S 5% poza rdzeniem;
    - fit „bez W” (naiwny histogram);
    - najpierw uproszczony pył, potem mapa.
11. **Z11** Budżet systematyki (każda pozycja jako wiersz):
    - 12 próbek mapy;
    - okna ±30%, wariant bez mapy;
    - |b|_min 5°/10°, D_max 0,55/0,8/1,1, A_mask;
    - ZP Zinn i ±15 µas, k = 1 vs k(G);
    - bez RUWE, ZGR23 vs Fitz19;
    - kształt rdzenia, u_sym, N/S, x > 0 / x < 0, skorupy 600/900 pc;
    - test „L z S2 nie zmienia wyniku”.
12. **Z12** Przebieg DR3 (nieblokujący, po G1b), porównanie z T5.
13. **Z13** DR4 po G3b; reguła wycofania wg S4 (18.12 / 22.12).
14. **Z14** Viewer, raport końcowy, odtworzenie z manifestu.

## Kryteria akceptacji

1. **Ekstynkcja:**
   - iteracja < 0,001 mag w ≤ 5 krokach;
   - krańce mapy pokryte testami;
   - C(550) ∈ [2,57; 2,84].
2. **Odczerwienienie:** locus RC w przedziałach A_0 i G stabilny
   (< 0,07 mag w M_G,0, < 0,03 w kolorze).
3. **Wesenheit:** konflikty < 5% (|b| > 10°), < 15% (5–10°).
4. **Numeryka W:** testy analityczne Z8 i zbieżność (Λ < 0,1% przy połowie
   kroku kwadratury, < 0,3% przy N_side 128 → 256).
5. **Mock (średnia z 10 realizacji, σ_średniej ≈ 1,6 pc dla h_1):**
   - |bias h_1| < 2% i < 3σ_średniej;
   - h_thin ±3%;
   - z_sun ±2 pc (rdzeń symetryczny);
   - fit „bez W” obciążony > 5σ_średniej;
   - mock Khanny (f = 0,37) daje profil h_thin(h_thick) z maksimum przy
     h_thick ≈ 480.
6. **Testy pipeline'u (D10)** na DR4, albo na DR3 w razie wycofania.
7. **Spójność w obserwablach:** h_1 z fitu M1 i h_1 przeliczone z najlepszych
   M2-exp i M2-sech² zgodne w ±3%. Residua n(z) bez trendu > 3σ poza
   amplitudą fal.
8. **Bliska/pełna:** M1 na d < 400 pc vs pełna objętość,
   |Δ| < 2√(σ²_stat + σ²_pył).
9. **Odporność:**
   - każdy wariant Z11 zmienia h_1 o < 10%;
   - rozrzut z_sun po wariantach raportowany;
   - N/S (a_k) raportowane.
10. **Odtwarzalność:**
    - identyczny `disk_fit.json` z manifestu;
    - zmiana L w S2 nie zmienia wyniku.
11. **Harmonogram (S4 v2):**
    - kryteria 1, 4, 5 przed G1b (1.12);
    - 2, 3, 6–9 na DR3 przed Z13 (nieblokujące);
    - wynik DR4 po G3b.

## Ryzyka i otwarte pytania

- **z_sun zależy od założenia symetrii rdzenia.** Asymetria 2% w rdzeniu
  przesuwa z_sun o 6–19 pc. Mitygacja: warianty u_sym i kształtu, szara
  strefa, porównanie z S4 T5a.
- **Degeneracja h_thin ↔ h_thick ↔ f.** Mitygacja: h_1 i profil zamiast
  jednej liczby.
- **Jeden dysk Khanny (h_1 ≈ 460)** wypadłby poza przedział testowy, choć
  jest opisem literaturowym. Do weryfikacji, który model Khanna i in. uznają
  za lepszy. Szara strefa do 470 pc.
- **Koszt W:** benchmark może dać > 100 ns/element. Plan: numba, mniej
  podpikseli w pikselach o niskim A.
- **Zaniżony pył w obłokach:** maska, kryterium 2, wariant bez mapy.
- **Φ zmienne z |z|** (gradient wieku): okno ±30%, podział okna.
- **DR4:** pasma, σ_ϖ, zp (S4). Wariant ±15 µas.
- **Monotoniczność g(ϖ)** może zawieść przy dużym A_0 i zależności k od A_0.
  Test w Z7; przy niezgodności suma przedziałów.

## Zmiany w kontrakcie

1. API S2 v3 bez zmian. Wycofana prośba o parametr offsetu.
2. S5 dostarcza `windows_in_parallax(pixel, G, c_obs, config)`, wspólne dla
   danych, W i mocka S2.
3. Kolumny bez zmian względem v2:
   - `a0_mag`, `a0_err_mag`, `ag_mag`, `ebprp_mag`, `bp_rp0`, `abs_g0`,
     `wes_g`;
   - `ext_origin`, `ext_flag`, `tracer` (`string` w Parquecie, `category` w
     pandas).
4. Manifest `fit`, nowe pola: `z_ref_pc` (20,8), u_sym, przedziały a_k,
   siatka r (90–1300 pc, krok 1%), krok kwadratury, N_side, tabela h_1
   (wersja), λ.
5. Plan v3, do aktualizacji:
   - sekcja 0: kryterium jako trzy testy pipeline'u (h_1 265–395, h_thin
     250–350, z_sun 10–30);
   - 2.5: fit w ϖ_c, porównanie w obserwablach, z_sun z modelem N/S.

## Odpowiedź na recenzję (runda 2)

1. **[IST.] z_sun z M0 — przyjęte.**
   - z_sun jest wolne w M2 na pełnym zakresie, z jawną asymetrią a_k poza
     rdzeniem; M0 tylko jako kontrola.
   - Degeneracja „asymetria rdzenia ↔ z_sun” zapisana wprost.
   - Własny rachunek potwierdza i doprecyzowuje kierunek recenzji:
     - fale poza rdzeniem przesuwają z_sun o < 0,5 pc;
     - asymetria w rdzeniu o 6–19 pc;
     - zły kształt rdzenia o ~11 pc.
   - Stąd warianty u_sym i kształtu jako systematyka oraz szara strefa
     (D9, D10).
2. **[IST.] sech² vs exp na parametrach — przyjęte.**
   - Próg 15% usunięty.
   - Porównanie w obserwablach: liczby w przedziałach N/S, dewiancja,
     Δln L/ΔBIC.
   - Kryterium: h_1 z M1 i h_1 przeliczone z M2-exp i M2-sech² w ±3%
     (D9, kryterium 7).
3. **[IST.] Przedział h_1 — przyjęte.**
   - Tabela 10 modeli z lokalnym f; Khanna f_local = 0,37 → 292 pc.
   - Obwiednia 279–379 pc, przedział testowy 265–395 pc.
   - Vieira i jeden dysk Khanny wyłączone, z uzasadnieniem; szara strefa
     do 470 pc.
   - Mock Khanny z f = 0,37, a f = 0,66 opisany jako skrajny.
   - Zdanie o „niezależności od dekompozycji” zastąpione sformułowaniem
     recenzenta.
4. **[IST.] Numeryka Λ — przyjęte.**
   - Siatka r do 1300 pc z A(r_max) powyżej mapy; człon gwiazdowy do
     ϖ_c − 6σ.
   - Kwadratura tensorowa 0,05 mag z testem połowy kroku.
   - Koszt przeliczony na ~2·10¹¹ elementów i ~6 h·rdzeń na siatkę główną,
     plus ×12 dla próbek przy N_side 64, z planem zmieszczenia i
     benchmarkiem w Z8.
   - Test analityczny przy σ ≠ 0 na krawędzi D_max.
5. **[DROB.] Okna dokładne — przyjęte.** `windows_in_parallax` przez odwrotną
   interpolację monotonicznej g(ϖ). Ten sam kod w danych, W i mocku.
   Przybliżenie i ryzyko „krawędzi obłoków” usunięte (D5).
6. **[DROB.] Wesenheit — przyjęte.** Rezydualne A_G − λE wchodzi do W_obs
   węzła. Okno bez poszerzania. API S2 z A_G = 0, prośba wycofana.
7. **[DROB.] z_ref — przyjęte.** Okna względem z_ref = 20,8 pc z manifestu;
   z_sun tylko w ν, W liczone raz.
8. **[DROB.] Rola zp_model — przyjęte.** W ścieżce głównej dzp = 0, bez
   wywołań; w wariantach dzp = zp_wariant − zp_bazowy (D8).
9. **[DROB.] σ_stat — przyjęte.** σ(h_1) ≈ 5 pc (Fisher własny: 5,1 pc przy
   7,1·10⁴ RC). Mock oceniany średnią z 10 realizacji (kryterium 5).

## Źródła

- Edenhofer+2024, A&A 685, A82; `dustmaps.edenhofer2023` (readthedocs)
- Gaia EDR3 extinction law (cosmos.esa.int)
- Hawkins+2017 (arXiv:1705.08988); Ripepi+2019 (arXiv:1810.10486)
- Yoldaş+2025 (arXiv:2501.04079); Khanna+2024 (arXiv:2410.22036);
  Bovy+2016 (wg Yoldaş)
- Jurić+2008 (astro-ph/0510520); Everall+2022 (arXiv:2111.08043);
  Vieira+2023 (Galaxies 11, 77) — parametry wg S4 v2 i recenzji S4
- Bennett & Bovy 2019 (arXiv:1809.03507)
- Rachunki własne: `/tmp/claude-0/-home-claude/addc613e-7c0c-52b8-a56b-ecb26da16d8e/scratchpad/s5v3/{tab,fish2,fish3,fish4,fish5,fish6,win}.py`
- S2 v3, S3 v2, S4 v2
