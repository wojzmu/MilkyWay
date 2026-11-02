# Jak liczymy pył — po ludzku

Ten dokument opisuje pierwszą część kamienia milowego M5: jak dla każdej
z 23 mln gwiazd katalogu liczymy, ile światła zabrał jej pył między nią
a nami, i co to zmienia na mapie. Kod: `milkyway/dust.py` (mapa pyłu,
współczynniki pasm, odczerwienianie), wywołanie w `milkyway/build.py`,
kolory w `milkyway/viewer_export.py`. Decyzja: D-024. Liczby policzone
na naszych danych (katalog `dr3_g15_p0.5_v3`) 31.10.2026.

---

## 1. Problem: pył przyciemnia i czerwieni

Między gwiazdami jest pył: ziarenka wielkości dziesiątych części
mikrometra. Działają jak mgła o zachodzie słońca. Gwiazda za pyłem jest
**ciemniejsza** (ekstynkcja, A) i **bardziej czerwona** (poczerwienienie,
E(BP−RP)), bo pył rozprasza niebieskie światło silniej niż czerwone.

Dla naszej mapy ma to trzy skutki:

1. **Kolor.** Viewer barwi gwiazdę na podstawie BP−RP. Gorąca gwiazda za
   obłokiem pyłu wychodzi pomarańczowa, choć naprawdę jest biała.
2. **Jasność absolutna.** M_G = G + 5 log ϖ − 10 bez pyłu wychodzi za
   słaba. Gwiazda wypada z okna „disc tracers” (M_G ≤ 2) albo z okna
   fitu wysokości skali (M_G ≤ 6).
3. **„Promienie” w widoku z góry.** Za gęstym obłokiem gwiazdy spadają
   poniżej G = 15 i znikają z próbki. Na mapie widać ciemny klin
   rozchodzący się od Słońca (D-023). To cień, nie prawdziwa pustka.

## 2. Skąd wiemy, gdzie jest pył: mapa Edenhofer et al. 2024

Gordian Edenhofer i współpracownicy złożyli trójwymiarową mapę pyłu
z ekstynkcji milionów gwiazd zmierzonych przez Zhang, Green & Rix (2023) z widm BP/RP Gai.
Obejmuje kulę od **68,6 do 1248 pc**. To prawie dokładnie nasza objętość
1,25 kpc, i nie przypadkiem: zasięg mapy wybraliśmy jako zasięg Mapy 1.0
(D-003).

Mapa jest siatką w dwóch kierunkach:

- **na niebie** to 786 432 piksele HEALPix (nside 256, ~0,23° każdy);
- **w odległości** to 516 „skorupek”, coraz grubszych w miarę oddalania
  się od Słońca: pierwsza ma 0,39 pc, ostatnia 7 pc.

W każdej komórce jest **gęstość pyłu** (ile ekstynkcji na parsek).
Używamy średniej z posterioru (plik 3,25 GB). Próbki posterioru (19,5 GB)
odkładamy na plan v4.

**Analogia:** mapa jest jak cebula z 516 warstw, a każda warstwa jest
podzielona na 786 tys. kafelków. Żeby wiedzieć, ile pyłu jest przed
gwiazdą, sumujemy kafelki wzdłuż promienia od Słońca do niej.

## 3. Jak liczymy pył przed gwiazdą

1. **Sumowanie.** Raz, przy wczytaniu mapy, dla każdego kierunku
   sumujemy gęstość × grubość warstwy od środka na zewnątrz. Mamy wtedy
   „ile pyłu do granicy warstwy k” (E_k). Wczytanie i zsumowanie trwa
   27 s i zajmuje 1,6 GB RAM.
2. **Kierunek.** Gwiazda rzadko trafia w środek piksela, więc mieszamy
   4 najbliższe piksele z wagami (interpolacja dwuliniowa).
3. **Odległość.** Gwiazda leży gdzieś między granicami dwóch warstw. Bierzemy
   E liniowo między nimi. Jest to **dokładne**, bo w jednej warstwie
   gęstość jest stała.
4. **Brzegi.** Bliżej niż 68,6 pc mapa podaje tylko sumę, więc skalujemy
   ją jak d / 68,6 pc (`dust_flag = inner`, 64 494 wiersze). Dalej niż
   1248 pc przyjmujemy wartość z brzegu, czyli dolne ograniczenie
   (`beyond_map`, 6 201 471 wierszy; i tak nie trafiają na mapę).

Wynik to `dust_e`: ilość pyłu w jednostkach „E” Zhanga i in.

**Dlaczego nie gotowy pakiet `dustmaps`:** wymaga healpy, którego nie da
się zainstalować na Windows. Pakiet interpoluje też na środkach warstw,
co przesuwa wszystko o pół warstwy. Czytamy plik sami (kilkadziesiąt linii), a
interpolację HEALPix robi `astropy-healpix`, którego już używamy.

## 4. Z „E” na magnitudo w pasmach Gai

E nie jest magnitudo. Ekstynkcję przy długości fali λ daje
**A_λ = E · R(λ)**, gdzie R(λ) to krzywa ekstynkcji z tej samej pracy
(R = 4,0 przy 392 nm, 2,68 przy 550 nm, 1,08 przy 952 nm). Pasmo G Gai
jest jednak szerokie (330–1050 nm), więc A_G to średnia A_λ ważona
tym, ile światła gwiazda wysyła w każdej części pasma.

Liczymy to wprost: krzywa przepuszczalności pasma (EDR3, z SVO) ×
widmo ciała doskonale czarnego o temperaturze gwiazdy × λ (Gaia liczy
fotony). Wychodzi tabela A_G, A_BP, A_RP w zależności od temperatury
i od E. Przykłady na naszej tabeli:

| Gwiazda | A_G/E | E(BP−RP)/E | A_G/E(BP−RP) |
|---|---|---|---|
| czerwony karzeł, 3500 K | 1,96 | 1,08 | 1,82 |
| jak Słońce, 5800 K | 2,30 | 1,24 | 1,85 |
| gorąca, 10 000 K | 2,58 | 1,39 | 1,85 |

(przy małym E; przy E = 1 A_G/E spada o ~9%: dalsze porcje pyłu działają
głównie na czerwoną część pasma, bo niebieska jest już wygaszona.)

**Sprawdzian:** dla gwiazdy typu Słońca A_G/A_V ≈ 0,86, a
A_G/E(BP−RP) ≈ 1,85. Te same wartości dają typowe krzywe ekstynkcji
z literatury (A_G/A_V ~0,83–0,86).

**Kółko z temperaturą:** temperaturę bierzemy z koloru, a kolor jest
poczerwieniony przez pył, którego właśnie szukamy. Robimy więc pętlę:
kolor → temperatura → poczerwienienie → poprawiony kolor → … aż zmiana
spadnie poniżej 0,0001 mag. Na kafelku 100 (46 289 gwiazd) wystarczyły
3 obroty: po pierwszym zmiana sięga 0,12 mag, po drugim 0,002, po trzecim 0,00004.

## 5. Co dostajemy na naszych danych

W 1,25 kpc (17 198 645 gwiazd):

- mediana **A_G = 0,18 mag**, 90% gwiazd ma < 0,75 mag, 99% < 1,55 mag,
  maksimum 4,36 mag;
- 19,8% gwiazd traci > 0,5 mag, 5,1% traci > 1 mag;
- mediana **E(BP−RP) = 0,10 mag** (90%: < 0,41).

Pył rośnie z odległością, i szybciej w płaszczyźnie dysku:

| Odległość | mediana A_G (wszystkie) | mediana A_G (\|b\| < 5°) |
|---|---|---|
| 0–100 pc | 0,01 | 0,01 |
| 100–250 pc | 0,04 | 0,07 |
| 250–500 pc | 0,11 | 0,26 |
| 500–750 pc | 0,17 | 0,38 |
| 750–1000 pc | 0,24 | 0,55 |
| 1000–1250 pc | 0,30 | 0,69 |

Pierwsze ~100 pc to prawie czysto: Słońce siedzi w **Bąblu Lokalnym**,
wydmuchanym przez dawne supernowe.

## 6. Czy to się zgadza? Porównanie z Gaią

Gaia sama szacuje A_G z widma każdej gwiazdy (`ag_gspphot`). To metoda
niezależna od mapy, bo jedna gwiazda naraz, bez sąsiadów. Na próbce
1 823 118 gwiazd (co 8. kafelek nieba):

- mediana: **nasze 0,172 mag, Gaia 0,173 mag**;
- korelacja 0,81;
- przy dużym pyle nasze wartości są niższe: gdzie my mamy A_G = 1–3,
  Gaia ma medianę 1,37. Mapa uśrednia pył po pikselu ~0,23° i warstwie,
  więc gęste jądra obłoków się rozmywają. GSP-Phot ma z kolei własne
  obciążenia (jedna gwiazda, model widma). Prawdy nie rozstrzygamy.

## 7. Co to zmienia na mapie

**Kolory.** Viewer barwi teraz gwiazdy kolorem *po odjęciu pyłu*
(`bp_rp0`). Gwiazdy w płaszczyźnie dysku robią się bielsze i bardziej
niebieskie, czyli takie, jakie są naprawdę. Katalog trzyma oba kolory:
`rgb_*` z koloru obserwowanego, `bp_rp0` po korekcie.

**Disc tracers.** Okno M_G ≤ 2 liczymy teraz z `abs_g0` = M_G − A_G.
Wchodzi do niego **1 269 275** gwiazd zamiast 913 280 (+39%). Te 356 tys.
to jasne gwiazdy, które pył udawał słabszymi. Cień zostaje tylko tam,
gdzie A_G > ~2,5 mag, bo dopiero wtedy gwiazda M_G = 2 z 1250 pc wypada
poza G = 15.

**Promienie to cienie pyłu.** Liczymy gwiazdy 600–1200 pc w pasie
|z| < 100 pc w przedziałach co 10° długości galaktycznej:

| l | gwiazd | mediana A_G |
|---|---|---|
| 0–10° | 107 191 | 0,60 |
| 20–30° | 51 406 | 1,24 |
| 30–40° | 48 564 | 1,17 |
| 60–70° | 88 291 | 0,36 |
| 140–150° | 45 948 | 1,15 |
| 230–240° | 77 854 | 0,12 |

Przy l = 20–40° gwiazd jest o połowę mniej niż obok, a pyłu dwa razy
więcej. To **Szczelina Orła** (Aquila Rift), pas obłoków kilkaset parseków
od nas. Przy l ≈ 140–160° widać to samo w stronę Perseusza i Żyrafy. Po
36 przedziałach korelacja log(liczba) z A_G wynosi −0,47. Nie −1, bo
liczba gwiazd zależy też od kierunku (w stronę centrum Galaktyki gęstość
rośnie).

**Fit wysokości skali (M5, dalej).** Okno M_G ≤ 6 z D-014 też liczymy
z `abs_g0`: 15 557 416 zamiast 15 219 651 gwiazd.

## 8. Skutki uboczne, o których trzeba pamiętać

- **Odległość to założenie.** E zależy od tego, gdzie jest gwiazda.
  Dla gwiazd `low_snr` (0,8%) odległość jest niepewna, więc ich pył też.
- **Ciało doskonale czarne zamiast widma.** Dla karłów M (linie TiO)
  współczynnik pasma może się różnić o kilka procent. Przy medianie
  A_G = 0,18 to setne części magnitudo.
- **Poniżej 392 nm krzywa jest przedłużona** linią prostą. To mniej niż
  4% wagi pasma BP dla gwiazdy typu Słońca.
- **Jedna krzywa R(λ) dla całej Galaktyki.** W gęstych obłokach krzywa
  bywa bardziej płaska (R_V ~ 4–5). Mapa i tak tego nie rozróżnia.
- **Średnia mapy, nie próbki.** Nie znamy niepewności A_G dla każdej
  gwiazdy (kolumna std w pliku dotyczy gęstości, nie sumy). Plan v4 S5
  używa 12 próbek.
- **Schemat v3.** Stary katalog `dr3_g15_p0.5_v2` nie otworzy się już
  w nowym kodzie. Odbudowa: `python MilkyWay.py --build` (333 s,
  w tym 27 s na mapę).

## 9. Jak to odtworzyć

```powershell
mkdir data\dust\edenhofer2023 -Force
curl.exe -L -o data\dust\edenhofer2023\mean_and_std_healpix.fits `
  "https://zenodo.org/records/8187943/files/mean_and_std_healpix.fits?download=1"
# MD5: 10c823a5fcf81b47b6e15530bcdf54dc
python MilkyWay.py --build                       # -> data/dr3_g15_p0.5_v3
python MilkyWay.py --dataset dr3_g15_p0.5_v3 --export-viewer web/public/map_1250pc
python MilkyWay.py --dataset dr3_g15_p0.5_v3 --export-viewer web/public/map_tracers_1250pc --abs-mag-max 2 --viewer-target 0
```

## 10. Słowniczek

- **Ekstynkcja (A_G)** — o ile magnitudo gwiazda jest ciemniejsza
  w paśmie G przez pył. 1 mag ≈ 2,5× mniej światła.
- **Poczerwienienie (E(BP−RP))** — o ile kolor BP−RP jest większy
  (czerwieńszy) przez pył; A_BP − A_RP.
- **Odczerwienianie** — odjęcie poczerwienienia: `bp_rp0 = bp_rp − E(BP−RP)`.
- **E (Zhang, Green & Rix 2023)** — jednostka ilości pyłu w mapie
  Edenhofera; A_λ = E · R(λ), A_V ≈ 2,7 E.
- **Krzywa ekstynkcji R(λ)** — jak bardzo pył gasi światło przy każdej
  długości fali, względem ilości pyłu.
- **HEALPix** — podział sfery na równe piksele; nside 256 to 786 432 piksele.
- **Posterior, średnia, próbki** — mapa jest wynikiem statystycznym:
  wiele równie dobrych wersji (próbek); średnia to ich uśrednienie.
- **Pasmo przepuszczalności** — jaka część światła o danej długości fali
  przechodzi przez filtr i trafia do detektora Gai.
- **Bąbel Lokalny** — obszar ~100 pc wokół Słońca prawie bez pyłu
  i gazu, wydmuchany przez supernowe sprzed kilku–kilkunastu mln lat.
- **Szczelina Orła (Aquila Rift)** — ciemny pas obłoków pyłu w Orle
  i Wężu, widoczny gołym okiem jako przerwa w Drodze Mlecznej.
