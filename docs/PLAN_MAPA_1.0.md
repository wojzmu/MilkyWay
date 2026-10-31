# Plan „Mapa 1.0" — mapa 3D okolicy Słońca w ~1,25 kpc

Wersja 2 (31.10.2026; v1 → v2: zmierzona liczność i jej skutki, D-011–D-014).
Plan dla jednej osoby pracującej z Claude Code.
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
  odległości w granicach niepewności). Porównanie przy **tych samych cięciach**:
  nowy pipeline uruchomiony bez limitu G (`g_max` wyłączone) i z cięciami
  starego (`parallax_over_error > 10`, `ruwe < 1.4`), bo stary katalog zawiera
  słabe karły M z G > 15 (D-013);
- orientacyjna wysokość skali mieści się w 200–450 pc (szeroki przedział, bo
  bez korekt z planu v4).

## 2. Co bierzemy z planu v4 (tanie, a dużo daje)

| Element | Źródło w v4 | Uproszczenie w 1.0 |
|---|---|---|
| Parquet + DuckDB, manifest zapisywany jako ostatni | S1 | Partycje HEALPix poz. 2; bez warstw `layers/` i `details.bin` |
| Funkcja selekcji `parallax > 0.5 AND phot_g_mean_mag < g_max` | S3, U2 | `g_max = 15` na start (parametr); G < 19 później |
| Pobieracz uproszczony: kafelki po `source_id`, joby async, pomijanie gotowych plików | S3 | Bez pełnego klienta UWS, bez atrapy TAP |
| Korekta zero-pointu (`gaiadr3-zeropoint`, przycięcie do zakresu z flagą) | S2 | Bez wariantów systematyki |
| Odległość: inwersja ϖ_c dla wszystkich, flaga `low_snr` dla ϖ/σ ≤ 5, `dist_origin`, `r_lo/r_med/r_hi` (D-020) | S2 | EDSD opcjonalnie, tylko do viewera |
| Współrzędne galaktocentryczne, preset astropy `v4.0` | S2, U11 | Bez zmian |
| Mapa pyłu Edenhofer 2024 (średnia) do odczerwienienia koloru | S5 | Bez próbek posterioru |
| Eksport binarny dla viewera, przerzedzenie, przezroczystość wg niepewności | S1 | Jeden plik, bez kafelków x/y/z na start |

**Dlaczego `g_max = 15` na start:** zbiór jest ~8× mniejszy niż przy G < 19
(zmierzone 31.10.2026, D-011: **23 371 857 wierszy**, 192 piksele poz. 2,
maks. 462 780, mediana 83 738; liczności w `docs/data/dr3_g15_hpx2_counts.csv`).
To ~3,5 GB Parquetu, więc mieści się na laptopie, a jasne gwiazdy mają dobre
paralaksy, więc proste odległości wystarczą. Kosztem jest to, że daleko widać
tylko jaśniejsze gwiazdy. Dla mapy to akceptowalne, bo selekcja jest sferyczna
i spłaszczenie dysku pozostaje widoczne.

**Konsekwencje liczności:**
- selekcja `parallax > 0.5` sięga ~2 kpc; cięcie do 1,25 kpc robimy dopiero po
  odległościach (M3), więc pobieramy też pas 1,25–2 kpc jako zapas na
  niepewność paralaksy;
- pobranie trwa godziny, nie minuty: pobieracz musi wznawiać pracę i pomijać
  gotowe kafelki; kafelek = piksel poz. 2 (≤ ~0,5 mln wierszy);
- viewer dostaje przerzedzenie f ≈ 1,5 mln / N (~6% przy całości, więcej po
  cięciu do 1,25 kpc);
- lista pobieranych kolumn musi zawierać wejścia zero-pointu (M3):
  `nu_eff_used_in_astrometry`, `pseudocolour`, `ecl_lat`,
  `astrometric_params_solved` — bez nich M3 wymaga ponownego pobrania.

## 3. Kamienie milowe

Szacunki w sesjach pracy z Claude Code (wieczór lub pół dnia weekendu).

| # | Kamień milowy | Sesje | Termin |
|---|---|---|---|
| M1 | Magazyn: CSV → Parquet + DuckDB, manifest, test zgodności z katalogiem referencyjnym 60 pc | 2–3 | do ~9.11 |
| M2 | Pobieracz uproszczony + pobranie DR3 (`parallax > 0.5`, `g_max = 15`; ~2,3·10⁷ wierszy) | 2–3 | przed 25.11 (cel) |
| M3 | Zero-point, odległości, współrzędne galaktocentryczne | 2–3 | do ~1.12 |
| M4 | Eksport binarny, viewer z ~1,5 mln punktów, widok z boku | 3–4 | grudzień |
| M5 | Pył (Edenhofer) dla kolorów, orientacyjny fit wysokości skali | 2–3 | grudzień |
| M6 | Przejście na DR4 (zmiana konfiguracji + test katalogu referencyjnego) | 1–2 | styczeń |

**Stan na 31.10.2026** (gałąź `m3-odleglosci`, wypchnięta, bez PR; bazuje na
niepołączonej `m1-magazyn`):
- M1–M4 **zrobione**; dokumenty: `JAK_POBIERAMY_DANE.md`,
  `JAK_LICZYMY_ODLEGLOSCI.md`, `JAK_RYSUJEMY_MAPE.md`. M5 **zrobione**:
  pył (D-024, `JAK_LICZYMY_PYL.md`, katalog schematu v3) i orientacyjna
  wysokość skali **h ≈ 331 pc** (warianty 316–342; D-025,
  `JAK_MIERZYMY_DYSK.md`). M2 T6 (ESA = AIP)
  i T7 (przegląd) zamknięte (D-022).
- Dane lokalne (git-ignorowane): pobranie `data/raw/dr3/dr3_g15_p0.5`,
  zbiór 60 pc `data/raw/dr3/dr3_p16.667`, Hipparcos `data/raw/dr3/aux`,
  mapa pyłu `data/dust/edenhofer2023`, katalog `data/dr3_g15_p0.5_v3`
  (23 373 946 wierszy; v2 nie otwiera się w schemacie v3), eksporty viewera
  `web/public/map_1250pc` i `web/public/map_tracers_1250pc`.
- **Otwarte przed publikacją mapy:** hosting eksportów na Hugging Face
  (D-023; konto i wgranie po stronie użytkownika), potem pełne URL-e
  w `web/public/datasets.json` i merge do `master`.
- **Zadanie viewera: nazwy znanych gwiazd** — **zrobione** (D-026):
  102 gwiazdy z listy IAU, nazwy po angielsku (D-027), `labels.json` w obu mapach,
  ukrywanie przy tłoku; opis w `JAK_RYSUJEMY_MAPE.md` §8.
- **Następny: M6** — przejście na DR4, gdy będzie dostępne (sprawdzić
  OP-1: gdzie i z jakimi kolumnami). Do tego czasu: hosting mapy.

Termin M2 przestał być twardy (D-012). Archiwum ESA jest wyłączone
25.11 12:00 – 2.12 CET, ale **głównym serwisem pobierania jest AIP**
(`gaia.aip.de/tap`): sprawdzone 31.10 — pełna `gaiadr3.gaia_source`
(153 kolumny), dostęp anonimowy, kolejka `QUEUE=2h` przyjmowana bez konta,
COUNT po całej selekcji w 5,5 min. ESA tego dnia zwróciło HTTP 500 i timeout,
więc jest zapasem, a nie podstawą. Trzecim zapasem, niezależnym od TAP, jest
kopia HATS z LSDB (~190 GB transferu dla naszych kolumn, D-017). Pobranie przed 25.11 pozostaje celem, bo
daje dwa działające serwisy na wypadek awarii AIP.

## 4. Orientacyjna wysokość skali (M5) — świadome uproszczenia

Prosty fit: walec R < 250 pc, karły ciągu głównego z oknem w CMD
**M_G ≤ 6** (G i wczesne K), histogram |z|, profil wykładniczy na 150–450 pc.

**Dlaczego M_G ≤ 6, a nie całe G/K (D-014):** przy `g_max = 15` próbka jest
kompletna tylko do M_G = 15 − μ − A_G. Najdalszy punkt walca to
√(250² + 450²) ≈ 515 pc (μ = 8,56), a A_G na tych wysokościach przyjmujemy
≤ ~0,3 mag, co daje M_G ≲ 6,1. Późne karły K (M_G ≈ 6–8) znikałyby z próbki
wraz z |z| i udawały spadek gęstości, czyli zaniżały h. Przy przejściu na
G < 19 okno można rozszerzyć (granica rośnie o 4 mag).

**Znane obciążenia, których 1.0 nie koryguje** (opisane w v4, S4 T5 i S5):
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

## 7. Otwarte punkty

Sprawy świadomie odłożone. Każda ma warunek, przy którym wraca; zamknięcie
punktu to wpis w `DECISIONS.md`.

### OP-1 · Wybór źródła pobierania danych Gai
**Stan (31.10.2026):** TAP z AIP główny (D-012), ESA zapasowy, HATS z LSDB
trzeci zapas (D-017). Kandydaci i to, co o nich wiemy:

| Źródło | Za | Przeciw |
|---|---|---|
| TAP AIP (`gaia.aip.de/tap`) | filtr po stronie serwera (~2,5 GB dla G < 15), anonimowo, `QUEUE=2h` | zależność od jednego serwisu i jego limitów |
| TAP ESA (`gea.esac.esa.int`) | źródło oficjalne, pierwsze z DR4 | 31.10 HTTP 500 i timeout; wyłączenie 25.11–2.12 |
| HATS / LSDB (`linea.data.lsdb.io/hats/gaia_dr3`), też MAST na AWS | statyczne pliki, wznawialne, układ HEALPix jak nasz magazyn | brak filtru po G: ~190 GB transferu dla naszych 21 kolumn |
| Hugging Face (`astro-legacy-archive/gaia-dr3-source`) | proste pobieranie, mirrory | 31.10 w trakcie wgrywania; format ECSV, bez zysku nad HATS |

**Wraca, gdy:**
- przechodzimy na G < 19 (~1,9·10⁸ wierszy, ~10% całości) — wtedy różnica
  TAP vs HATS maleje, a stabilność statycznych plików zyskuje na wadze;
- przechodzimy na DR4 (M6) — sprawdzić, gdzie i kiedy DR4 będzie dostępne
  (ESA, AIP, HATS) i czy kolumny się zgadzają;
- AIP zawiedzie przy pobieraniu M2 (limity, awarie, zmiana zasad dostępu);
- mirror na Hugging Face zostanie ukończony albo pojawi się wersja Parquet
  z filtrem po jasności.

**Do zrobienia przy powrocie:** pomiar czasu i transferu na jednym kafelku
z każdego źródła; zgodność wyniku (te same `source_id`, wartości bit w bit).
