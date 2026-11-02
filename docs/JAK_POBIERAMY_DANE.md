# Jak pobieramy dane — po ludzku

Ten dokument opisuje drogę danych od satelity do naszego dysku: skąd się
biorą, jak o nie prosimy, co dokładnie pobieramy i dlaczego akurat tak.
Szczegóły techniczne są w kodzie (`milkyway/raw.py`, `milkyway/fetch.py`)
i w dzienniku decyzji (`docs/DECISIONS.md`, zwłaszcza D-008, D-011, D-012,
D-019). Tu chodzi o zrozumienie.

---

## 1. Skąd są dane

### Gaia

**Gaia** to satelita Europejskiej Agencji Kosmicznej (ESA). Od 2014 do
początku 2025 roku obracał się powoli w przestrzeni i w kółko skanował całe
niebo, za każdym razem mierząc te same gwiazdy na nowo. Z dziesiątek pomiarów
jednej gwiazdy wychodzi:

- **gdzie dokładnie jest na niebie** (pozycja),
- **jak szybko się po nim przesuwa** (ruch własny),
- **jak bardzo „drga” w ciągu roku**, gdy Ziemia krąży wokół Słońca —
  z tego liczy się odległość (paralaksa, rozdział 3),
- **jak jest jasna i jakiego koloru** (fotometria),
- dla części gwiazd: **jak szybko leci do nas lub od nas** (prędkość
  radialna) i oszacowanie **temperatury**.

ESA publikuje wyniki w „wydaniach” (Data Release). Używamy **DR3** z czerwca
2022: ok. **1,8 miliarda** obiektów, z czego ok. 1,5 miliarda ma zmierzoną
paralaksę. Następne wydanie, DR4, ma objąć cały czas trwania misji (to etap
M6 naszego planu).

### Hipparcos

**Hipparcos** to starszy satelita ESA (1989–1993), który zmierzył ok. **118
tysięcy** gwiazd. Potrzebujemy go z jednego powodu: najjaśniejsze gwiazdy
nieba (Syriusz, Wega, Arktur…) są dla Gai **zbyt jasne** — oślepiają jej
detektor jak słońce w obiektywie aparatu i część z nich nie ma w Gai dobrych
pomiarów. Hipparcos mierzył je bez problemu. Bez niego na naszej mapie
brakowałoby akurat gwiazd, które każdy zna.

---

## 2. Gdzie leżą dane i jak się o nie prosi

Katalog Gai to jedna gigantyczna tabela: wiersz = gwiazda, kolumna = jedna
zmierzona wielkość (152 kolumny). Nikt jej nie trzyma w całości „u siebie” —
leży w **archiwach**, które przyjmują zapytania:

| Archiwum | Co to | Rola u nas |
|---|---|---|
| **AIP** (Instytut Astrofizyki w Poczdamie) | kopia katalogu Gai | **główne źródło** (D-012) |
| **ESA Gaia Archive** (Madryt) | archiwum oficjalne | zapas; stąd bierzemy też katalog Hipparcosa |
| **HATS / LSDB** | cały katalog jako zwykłe pliki do ściągnięcia | zapas awaryjny (D-017) |

Rozmawia się z nimi przez standard **TAP**, a pytania pisze się w języku
**ADQL** — to po prostu SQL (język baz danych) z dodatkami do pracy na
niebie. Nasze zapytanie wygląda tak (skrócone):

```sql
SELECT source_id, ra, dec, parallax, phot_g_mean_mag, ...   -- jakie kolumny
FROM gaiadr3.gaia_source                                     -- z jakiej tabeli
WHERE source_id BETWEEN 4035225266123964416 AND ...          -- który kawałek nieba
  AND parallax > 0.5                                         -- tylko bliższe niż ~2000 pc
  AND phot_g_mean_mag < 15.0                                 -- tylko jaśniejsze niż 15 mag
```

Duże zapytania wysyła się w trybie **asynchronicznym** — jak zamówienie
w bibliotece: składasz rewers, dostajesz numer zamówienia, wracasz, gdy
książka czeka na półce. Konkretnie:

1. wysyłamy zapytanie → archiwum odpowiada adresem „zlecenia” (job),
2. co kilka sekund pytamy o stan: *w kolejce → wykonuje się → gotowe*,
3. pobieramy wynik (u nas w formacie **Parquet** — kompaktowy plik
   tabelaryczny, czytany wprost przez nasz kod),
4. **usuwamy zlecenie z serwera**, żeby nie zajmowało mu miejsca.

---

## 3. Paralaksa, czyli jak się mierzy odległość

Wyciągnij rękę z uniesionym kciukiem i patrz na niego na przemian lewym
i prawym okiem. Kciuk „skacze” na tle pokoju. Im bliżej oczu go trzymasz,
tym bardziej skacze. To jest **paralaksa**.

Gaia robi to samo, tylko zamiast dwojga oczu ma dwie strony ziemskiej orbity
(odległe o 300 mln km), a zamiast kciuka — gwiazdę. Bliska gwiazda w ciągu
roku zatacza na tle bardzo dalekich obiektów maleńką elipsę. Te skoki są
**mikroskopijne**, więc mierzy się je w **milisekundach łuku** (mas). Dla
wyczucia: 1 mas to grubość ludzkiego włosa oglądanego z odległości ok.
20 km.

Zasada jest prosta: **odległość w parsekach = 1000 / paralaksa w mas**
(1 parsek ≈ 3,26 roku świetlnego).

| Paralaksa | Odległość |
|---|---|
| 768 mas | 1,3 pc — Proxima Centauri, najbliższa gwiazda |
| 16,7 mas | 60 pc — granica naszego starego katalogu |
| 0,8 mas | 1250 pc — granica mapy „Mapa 1.0” |
| **0,5 mas** | **2000 pc — nasz próg pobierania** |

**Dlaczego pobieramy do 2000 pc, skoro mapa sięga 1250 pc?** Bo każdy pomiar
ma błąd. Gwiazda, która naprawdę jest w odległości 1200 pc, może mieć
zmierzoną paralaksę trochę mniejszą niż 0,8 mas. Gdybyśmy cięli na granicy
mapy już przy pobieraniu, takie gwiazdy by przepadły. Zapas 0,3 mas pozwala
potem (w M3) przyciąć dokładniej, gdy już poprawimy paralaksy i policzymy
odległości z niepewnościami.

**Pułapka: paralaksy Gai są lekko przesunięte.** Pomiar ma drobny
systematyczny błąd zera (*zero-point*), rzędu kilkunastu–kilkudziesięciu
mikrosekund łuku (dla kwazarów średnio ok. −0,017 mas), różny dla różnych gwiazd (zależy od jasności, koloru i położenia na
niebie). Przy gwieździe w 1250 pc to już parę procent odległości. Dlatego
pobieramy też kolumny potrzebne do tej poprawki (rozdział 6) — sama poprawka
to etap M3.

---

## 4. Jasność G i dlaczego bierzemy tylko G < 15

Astronomowie mierzą jasność w **wielkościach gwiazdowych (magnitudo, mag)**.
Ta skala jest dziwna z dwóch powodów:

- **odwrócona**: mniejsza liczba = jaśniejsza gwiazda (Syriusz ma ok. −1,
  najsłabsze gwiazdy widoczne gołym okiem ok. 6),
- **logarytmiczna**: różnica 5 mag to 100 razy w jasności.

**G** to jasność w szerokim filtrze Gai. Gaia widzi gwiazdy do ok. G = 21.

**Dlaczego G < 15 (D-008, D-011):** przy samym progu paralaksy dostalibyśmy
setki milionów gwiazd, w większości słabych, dalekich i z kiepskimi
pomiarami. Z limitem G < 15 jest ich **23 371 857** — sprawdziliśmy to
zapytaniem liczącym przed pobraniem. To ~4,2 GB, wygodnie na laptopie.
Jasne gwiazdy mają też najdokładniejsze paralaksy: przy G = 15 błąd to
zwykle ok. 0,02–0,03 mas, czyli dla gwiazdy w 1250 pc kilka procent
odległości.

**Cena, którą płacimy: daleko widać tylko jasne gwiazdy.** Gwiazda wydaje
się słabsza, im jest dalej. Ile może być daleko, żeby jeszcze zmieścić się
w G < 15, zależy od tego, jak jasna jest naprawdę:

| Gwiazda | Prawdziwa jasność (M_G) | Widzimy ją do |
|---|---|---|
| jasny olbrzym | ok. 0 | > 2000 pc (cała sfera) |
| **Słońce** | 4,7 | **ok. 1150 pc** |
| pomarańczowy karzeł (typ K) | ok. 7 | ok. 400 pc |
| czerwony karzeł (typ M) | ok. 10 | ok. 100 pc |

(Bez uwzględnienia pyłu, który dodatkowo przyciemnia gwiazdy.)

To nazywa się **efektem selekcji** i trzeba o nim pamiętać przy każdym
wniosku. Np. gdybyśmy liczyli, jak szybko maleje liczba karłów typu K
z wysokością nad płaszczyzną Galaktyki, to od ok. 400 pc „znikałyby” nie
dlatego, że ich nie ma, tylko dlatego, że są za słabe dla naszego limitu.
Dlatego orientacyjny fit grubości dysku (M5) bierze tylko gwiazdy
z M_G ≤ 6 (D-014).

---

## 5. Czego celowo NIE filtrujemy

Gaia ma kolumny „jakości” pomiaru — np. **RUWE** mówi, jak dobrze ruch
gwiazdy pasuje do modelu pojedynczej gwiazdy (wysoki RUWE często znaczy
gwiazdę podwójną). Stary pipeline odrzucał gwiazdy z RUWE ≥ 1,4.

Przy pobieraniu **nie tniemy po jakości** (kod wręcz na to nie pozwala —
w zapytaniu wolno użyć tylko paralaksy i jasności). Powód: tego, czego nie
pobierzemy, nie odzyskamy bez ponownego obciążania serwera, a progi jakości
chcemy móc zmieniać i porównywać. Kolumny jakości pobieramy, a cięcia
robimy później, lokalnie, na własnej kopii.

---

## 6. Jakie kolumny pobieramy (36 z 152)

| Grupa | Kolumny | Po co |
|---|---|---|
| **Identyfikator** | `source_id` | numer gwiazdy w Gai (zawiera „adres” na niebie, rozdział 7) |
| **Pozycja** | `ra`, `dec` (współrzędne na niebie), `l`, `b` (to samo w układzie Galaktyki), `ecl_lat` | gdzie jest gwiazda |
| **Odległość** | `parallax`, `parallax_error` | paralaksa i jej niepewność |
| **Ruch** | `pmra`, `pmdec` (+ błędy), `radial_velocity` (+ błąd) | ruch po niebie i wzdłuż linii widzenia; z tego prędkości w Galaktyce |
| **Jakość astrometrii** | `ruwe`, `astrometric_excess_noise`, `ipd_gof_harmonic_amplitude`, `ipd_frac_multi_peak`, `visibility_periods_used`, `duplicated_source` | do późniejszych cięć jakości |
| **Wejścia poprawki zera paralaksy** | `nu_eff_used_in_astrometry`, `pseudocolour`, `astrometric_params_solved`, `ecl_lat` | bez nich M3 musiałby pobierać wszystko od nowa |
| **Jasność i kolor** | `phot_g_mean_mag` (G), `phot_bp_mean_mag` (niebieski), `phot_rp_mean_mag` (czerwony), `bp_rp` (kolor), `phot_bp_rp_excess_factor` | jasność; **kolor BP−RP** mówi o temperaturze (niebieskie = gorące) i daje barwę punktu na mapie |
| **Oszacowania Gai (GSP-Phot)** | `teff_gspphot` (temperatura), `distance_gspphot` (+ granice), `ag_gspphot`, `ebpminrp_gspphot` (przyciemnienie przez pył) | dla porównania z naszymi wynikami |

Pełna lista z typami: `RAW_SCHEMA` w `milkyway/raw.py`.

---

## 7. Jak dzielimy niebo na kawałki

Jedno zapytanie o 23 miliony gwiazd byłoby za duże (AIP przyjmuje do
5 milionów wierszy na zlecenie), a gdyby się przerwało, trzeba by zaczynać
od zera. Dlatego dzielimy niebo na **192 kafelki** i pobieramy je po kolei.

Podział to **HEALPix** — sposób pocięcia kuli nieba na kawałki o **równej
powierzchni**. Zaczyna się od 12 kawałków, a każdy można dzielić na 4
mniejsze. Poziom 2 to 12 × 4 × 4 = **192 kawałki** po ok. 215 stopni
kwadratowych (dla porównania: Księżyc w pełni zajmuje ok. 0,2 stopnia
kwadratowego).

**Sprytny trik:** numer gwiazdy w Gai (`source_id`) w swoich pierwszych
cyfrach (w zapisie binarnym) **zawiera numer kawałka nieba**, w którym
gwiazda leży. Wszystkie gwiazdy z kafelka mają więc numery z jednego
ciągłego przedziału. Dlatego zapytanie o kafelek to proste
`source_id BETWEEN … AND …`, które baza wykonuje bardzo szybko.

Kafelki są bardzo nierówne — i to już jest pierwszy obraz Galaktyki:

| Kafelek | Gwiazd (G < 15, < 2 kpc) | Gdzie |
|---|---|---|
| 112 (najgęstszy) | 462 780 | gwiazdozbiór Strzelca — **w stronę centrum Galaktyki** |
| 165 | 414 053 | Skorpion — też przy płaszczyźnie Galaktyki |
| 109 | 30 068 | Warkocz Bereniki — blisko **bieguna** Galaktyki |
| 111 (najrzadszy) | 30 055 | Wielka Niedźwiedzica — blisko bieguna |

Różnica ok. 15 razy: patrząc wzdłuż płaszczyzny dysku, widzimy przez
grubą warstwę gwiazd; patrząc „w górę”, szybko z niej wychodzimy. To jest
dokładnie spłaszczenie dysku, które mapa ma pokazać w 3D. Liczby dla
wszystkich 192 kafelków: `docs/data/dr3_g15_hpx2_counts.csv`.

---

## 8. Jak wygląda pobieranie, krok po kroku

Polecenie `python MilkyWay.py --fetch` robi dla każdego kafelka:

1. **Zlecenie** zapytania do AIP (najwyżej **2 naraz** — serwis jest
   darmowy i używają go zawodowi astronomowie, więc nie zajmujemy go
   bardziej, niż trzeba).
2. **Czekanie** na wynik (od kilkunastu sekund do ok. półtorej minuty;
   najgęstszy kafelek: 41 s zapytanie + 47 s pobieranie, 83 MB).
3. **Sprawdzenie** wyniku, zanim cokolwiek trafi na dysk:
   - **liczba gwiazd zgadza się co do sztuki** z wcześniej policzoną dla
     tego kafelka — to najmocniejsza kontrola: obcięty lub zdublowany
     wynik nie przejdzie,
   - wszystkie gwiazdy należą do tego kafelka i żadna się nie powtarza,
   - każda naprawdę spełnia warunki (paralaksa > 0,5, G < 15),
   - kolumny i ich typy są takie, jak oczekujemy.
4. **Zapis** pliku tak, żeby nie mógł powstać „pół-plik”: najpierw pod
   tymczasową nazwą, a dopiero po pełnym zapisie zmiana nazwy na docelową.
5. **Usunięcie zlecenia** z serwera.

Gdy coś pójdzie nie tak (sieć, przeciążony serwer), pobieracz próbuje
ponownie po 1, 5 i 15 minutach. Jeśli całość się przerwie, ponowne
uruchomienie **pomija gotowe kafelki**. Gdy są już wszystkie, powstaje
**manifest** — spis kafelków z liczbami gwiazd i „odciskami palców”
(SHA-256) każdego pliku. Dopiero wtedy pobranie jest uznane za kompletne.

Zbiory Hipparcosa pobiera osobno `python MilkyWay.py --fetch-aux`:
katalog Hipparcosa (118 184 gwiazd, z archiwum ESA) i tabelę dopasowań
„ta gwiazda Hipparcosa to ta gwiazda Gai” (99 524 par, z AIP). W etapie M3
do mapy dołączymy tylko te gwiazdy Hipparcosa, których Gaia nie zmierzyła
porządnie.

---

## 9. Raz pobrane — zostaje

Pobrane kafelki (`data/raw/dr3/dr3_g15_p0.5/`) to **trwała kopia**.
Wszystkie dalsze etapy — poprawka paralaks, odległości, kolory, mapa —
czytają je z dysku, nie z archiwum. Ponowne `--fetch` na kompletnym
zbiorze nie wysyła żadnego zapytania. Do serwerów wracamy tylko przy innej
selekcji (np. G < 19) albo nowym wydaniu (DR4).

Kopię warto zabezpieczyć (dysk zewnętrzny, chmura). Manifest pozwala po
odtworzeniu sprawdzić, że żaden bajt się nie zmienił.

---

## 10. Słowniczek

| Pojęcie | Znaczenie |
|---|---|
| **ADQL** | SQL do zapytań o dane astronomiczne |
| **asynchroniczne zlecenie (job)** | zapytanie, które archiwum wykonuje w tle; wynik odbiera się później |
| **BP−RP** | różnica jasności w niebieskim i czerwonym filtrze Gai; miara koloru, a więc temperatury |
| **efekt selekcji** | zniekształcenie wyników przez to, *co* w ogóle trafiło do próbki (np. tylko jasne gwiazdy) |
| **G, magnitudo** | jasność; skala odwrócona i logarytmiczna (5 mag = 100×) |
| **HEALPix** | podział kuli nieba na kawałki równej powierzchni |
| **M_G** (jasność absolutna) | jak jasna byłaby gwiazda z odległości 10 pc — mówi, jaka jest naprawdę |
| **manifest** | spis plików z liczbami wierszy i sumami kontrolnymi; znak, że zbiór jest kompletny |
| **mas** | milisekunda łuku, 1/3 600 000 stopnia |
| **paralaksa** | roczne „drganie” gwiazdy na niebie; odwrotność odległości |
| **parsek (pc)** | 3,26 roku świetlnego; 1 kpc = 1000 pc |
| **Parquet** | kompaktowy format plików z tabelami |
| **RUWE** | wskaźnik jakości dopasowania ruchu gwiazdy; wysoki często = gwiazda podwójna |
| **TAP** | standard rozmowy z archiwami astronomicznymi |
| **zero-point paralaksy** | drobne systematyczne przesunięcie paralaks Gai; poprawiamy je w M3 |
