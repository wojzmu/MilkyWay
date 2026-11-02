# Jak rysujemy mapę — po ludzku

Ten dokument opisuje kamień milowy M4: jak z katalogu 23 mln gwiazd
(`docs/JAK_LICZYMY_ODLEGLOSCI.md`) powstaje interaktywna mapa 3D, którą
przeglądarka obraca płynnie. Kod: `milkyway/viewer_export.py` (eksport),
`web/src/data/loadPointCloud.ts` i `web/src/components/GalaxyField3D.tsx`
(viewer). Decyzja: D-021. Liczby policzone na naszych danych 31.10.2026.

---

## 1. Problem: 17 milionów to za dużo dla przeglądarki

W promieniu 1,25 kpc mamy **17 198 645** gwiazd. Stary viewer czytał plik
CSV i robił z każdej gwiazdy obiekt z ~35 polami. To działa dla 60 tys.
gwiazd, ale przy milionach przeglądarka zużyłaby gigabajty pamięci i
parsowałaby tekst przez minutę. Potrzebne były trzy rzeczy:

1. **mniej punktów**, ale tak wybranych, żeby obraz się nie zmienił,
2. **format binarny** zamiast tekstu,
3. **rysowanie na karcie graficznej** bez osobnego obiektu na gwiazdę.

## 2. Przerzedzenie: losowanie, które zawsze daje ten sam wynik

Bierzemy co ~11. gwiazdę (dokładnie ułamek f = **0,0872**), ale nie „co
jedenastą z listy”, bo lista jest posortowana po niebie i powstałyby
pasy. Dla każdej gwiazdy liczymy z jej numeru **hasz**, czyli
pseudolosową liczbę (funkcja `splitmix64`), i zostawiamy ją, gdy hasz
wypada poniżej progu. To jak rzut monetą, tyle że ten sam numer zawsze daje
ten sam wynik. Kolejny eksport wybierze więc te same gwiazdy.

Ważne jest, że **ten sam ułamek obowiązuje wszędzie**. Gdzie gwiazd jest
dwa razy więcej, zostaje ich dwa razy więcej, więc kontrast między gęstym
dyskiem a pustym halo się zachowuje. Wyjątek: gwiazdy widoczne gołym
okiem (G < 6) i gwiazdy z nazwami (§8) zostają zawsze, bo to je ludzie
rozpoznają; razem **6 746**.

Wynik: **1 505 771** gwiazd. Kolejność w pliku też jest przemyślana: najpierw
jasne, potem reszta w kolejności haszu. Dzięki temu każdy początek pliku to
też losowa próbka, a suwak „Points shown” rysuje po prostu pierwsze k
punktów, bez przeliczania.

## 3. Format binarny

Zamiast tekstu zapisujemy liczby tak, jak trzyma je pamięć komputera
(`points.bin`, 16,6 MB). Na jedną gwiazdę przypada **11 bajtów**:

- 6 bajtów na położenie x, y, z (3 liczby całkowite int16; jednostką jest
  1250/32767 ≈ 0,038 pc, ok. 7 800 au; przy skali mapy różnica
  niewidoczna),
- 3 bajty na kolor R, G, B,
- 1 bajt na **niepewność odległości** (kod U, rozdział 4),
- 1 bajt na klasę gwiazdy (ciąg główny, olbrzym…).

Przeglądarka wczytuje taki plik jednym ruchem i od razu przekazuje karcie
graficznej, bez parsowania.

Szczegóły gwiazdy, czyli numer katalogowy, przedział odległości, jasność
i kolor (24 bajty na gwiazdę, 36 MB), leżą w osobnym `details.bin`. Viewer
nie pobiera go w całości. Po kliknięciu gwiazdy prosi serwer tylko o jej
24 bajty (zapytanie HTTP *Range*), co sprawdziliśmy w przeglądarce.

## 4. Kod niepewności: jeden bajt na „jak bardzo jestem pewien”

Z rozdziału 3 dokumentu o odległościach: każda gwiazda ma przedział
`r_lo`–`r_hi`. Względna niepewność to f = (r_hi − r_lo) / (2 · odległość).
W eksporcie ma medianę **1,4%**, ale rozciąga się od 0,1% do ponad 50%.
Taki zakres najlepiej zapisać w skali logarytmicznej: bajt 0 oznacza
f = 0,1%, bajt 254 oznacza f = 50%, a 255 „nie wiadomo”.

Bajt niesie informację, a nie przezroczystość. O tym, jak go narysować,
decyduje suwak „Max uncertainty” w viewerze (domyślnie 20%). Gwiazdy
powyżej progu (**11 205**, czyli 0,7%) robią się prawie przezroczyste.
Zmiana progu nie wymaga nowego eksportu.

## 5. Rysowanie: wszystko na karcie graficznej

Karta graficzna dostaje całą chmurę punktów raz. Każdy suwak (maksymalna
odległość, niepewność, klasy, jasność, rozmiar punktu) zmienia tylko kilka
liczb przekazywanych do małego programu na karcie (**shadera**), który dla
każdego punktu decyduje, czy go narysować i jak. Dlatego przesuwanie suwaka
działa płynnie przy 1,5 mln punktów.

Punkty się **sumują** (mieszanie addytywne): tam, gdzie jest ich dużo,
obraz jaśnieje, jak prawdziwa Droga Mleczna na niebie. Przy 1,5 mln
punktów pełna jasność każdego daje biały placek, dlatego domyślna
„Brightness” to 15%.

## 6. Co widać z boku

Przycisk „Side (edge-on)” ustawia kamerę w płaszczyźnie Galaktyki. Mapa
jest kulą o promieniu 1,25 kpc, ale gwiazdy układają się w **spłaszczony
dysk**. Na liczbach, w powłoce 1000–1250 pc:

- **44%** gwiazd leży mniej niż 10° od płaszczyzny Galaktyki; gdyby były
  rozłożone równomiernie w kuli, byłoby to 17%;
- tylko **2,2%** leży wyżej niż 60° nad lub pod płaszczyzną, a przy
  rozkładzie równomiernym byłoby to 13%.

To jest efekt, który chcieliśmy pokazać: dysk ma grubość kilkuset
parseków, więc na 1,25 kpc jego płaskość już widać. W M5 zmierzymy ją
liczbowo (wysokość skali).

## 7. Mapa „disc tracers”: jak naprawdę zobaczyć dysk

Na pełnej mapie gęstość punktów zależy bardziej od naszego limitu jasności
niż od kształtu Galaktyki (rozdział 8). Dlatego jest druga mapa: **tylko
gwiazdy jasne z natury**, o jasności absolutnej M_G ≤ 2 (olbrzymy, gwiazdy
typu A i F). Z 1250 pc taka gwiazda ma jasność obserwowaną najwyżej
2 + 10,5 = 12,5 mag, więc mieści się w limicie G < 15 nawet przy 2 mag
osłabienia przez pył. Widzimy więc **wszystkie** takie gwiazdy w całej
kuli, a nie tylko te bliskie.

Bez korekty pyłu było ich 913 280, po korekcie (D-024) **1 269 275**,
i bierzemy wszystkie, bez przerzedzania. Do tego 7 gwiazd z nazwami,
które są słabsze niż próg (§8), razem 1 269 282.
W widoku z boku dysk jest wyraźnie cieńszy niż na pełnej mapie. W liczbach
(walec o promieniu 800 pc wokół Słońca): w pierwszych 100 pc nad lub pod
płaszczyzną jest 15 771 takich gwiazd, a w przedziale 700–800 pc tylko 917,
czyli 17 razy mniej.

## 8. Nazwy znanych gwiazd

Na mapie podpisujemy **102 gwiazdy**: wszystkie gwiazdy z oficjalnego
katalogu nazw IAU jaśniejsze niż V = 2,5 (85) oraz 17 słynnych słabszych,
np. Proxima Centauri, Gwiazda Barnarda i Mira. Lista jest w
`milkyway/star_names.csv`. Podpisy są po angielsku, jak cały interfejs
(Sirius, Betelgeuse, Vega, Polaris…): to nazwy IAU, a tylko dla Alfy
Centauri A i B dajemy angielską formę „Alpha Centauri A/B” zamiast
mniej znanych Rigil Kentaurus i Toliman (te widać w dymku). Decyzje:
D-026, D-027.

**Jak trafiamy na gwiazdę.** Każda nazwa ma numer z katalogu Hipparcosa
(HIP), a nasz katalog ma kolumnę `hip`. Tak znajdujemy wszystkie 102.
Aż 86 z nich to wiersze Hipparcosa, bo jasne gwiazdy oślepiają detektor
Gai. Najdalszy jest Deneb, 990 pc, z dużą niepewnością.

**Plik.** Eksport zapisuje `labels.json` (nazwa, pozycja, indeks punktu
w `points.bin`). Gwiazdy z nazwami trafiają do eksportu zawsze, z pominięciem
przerzedzania i progu jasności, żeby każdy podpis dało się kliknąć (D-027).
Bez tego Proxima i Gwiazda Barnarda wypadały przy przerzedzaniu, a na mapie
tracers brakowało 7 karłów słabszych niż M_G = 2 (Altair, Procjon, Alfa
Centauri A i B, Proxima, Gwiazda Barnarda, Alkor). Gdyby jakiejś gwiazdy zabrakło w katalogu albo leżała dalej niż
1250 pc, eksport wypisze ją w raporcie.

**Tłok.** Z daleka wszystkie bliskie gwiazdy (Syriusz 2,6 pc, Wega
7,8 pc…) zlewają się ze Słońcem. Co klatkę układamy podpisy od
najbardziej znanych: podpis, który zasłoniłby wcześniejszy, znika. Przy
oddaleniu zostają więc najsłynniejsze i najdalsze (Deneb, Rigel,
Alnilam), a po przybliżeniu do Słońca pojawia się kilkadziesiąt nazw.
Kliknięcie podpisu wybiera gwiazdę. Przełącznik „Star names” chowa
wszystkie podpisy.

**Mapy 20–60 pc (stary pipeline).** Te same nazwy są na mapach z plików
CSV. Plików nie zmieniamy: viewer wczytuje `star_names.json` i szuka gwiazd
po `star_id`. Jedna gwiazda może tam być zapisana jako „HIP 32349” albo
jako „Gaia DR3 …”, więc każda nazwa ma listę obu wersji (128 identyfikatorów
na 102 nazwy). W zbiorze 60 pc są wszystkie 58 gwiazd z listy, które leżą
w tej odległości, w zbiorze 20 pc 41. W zbiorze 120 pc (≥ 0,9 M☉) tylko 12,
bo nie ma w nim gwiazd bez oszacowania masy, czyli m.in. olbrzymów jak
Arktur.

## 9. Skutki uboczne, o których trzeba pamiętać

- **Jasny środek to częściowo złudzenie.** Na sześcian parseka przypada
  w pobliżu Słońca (do 250 pc) **19 razy** więcej narysowanych gwiazd niż
  w powłoce 1000–1250 pc. Gwiazd w kosmosie nie ma tam 19 razy więcej:
  przy limicie G < 15 z daleka widać tylko jaśniejsze gwiazdy (rozdział 4
  dokumentu o pobieraniu). Mapa pokazuje to, co Gaia zmierzyła, a nie
  prawdziwą gęstość. Poprawka na to jest w planie M5.
- **Pył** przyciemnia i zaczerwienia gwiazdy w płaszczyźnie dysku, więc
  część z nich wypadła za limit G < 15. Kolory na mapie nie są jeszcze
  poprawione o pył (też M5).
- **Diagram HR** jest wyłączony dla tej mapy. Pełne dane do niego są
  w `details.bin`, ale wymagałyby pobrania 36 MB. Może wrócić później.
- **Strona publiczna.** Pliki mapy (~97 MB obu map) są generowane lokalnie
  i nie trafiają do gita. Leżą na Hugging Face
  (`huggingface.co/datasets/WojZmu/MilkyWay`), a aplikacja zna ich pełne
  adresy (D-028). Po każdym nowym eksporcie trzeba je wgrać ponownie.
- **„Promienie” w widoku z góry** to głównie cienie obłoków pyłu: obłok
  100–200 pc od nas zasłania klin aż do brzegu mapy. W płaszczyźnie dysku
  (|b| < 5°, 600–1200 pc) w kierunku centrum Galaktyki jest ok. 130 tys.
  gwiazd, a w kierunku obłoku Aquila Rift (l ≈ 15–45°) tylko 61–72 tys.
  Mapa pyłu w M5 pokaże obłoki na początku tych klinów.

## 10. Słowniczek

- **Przerzedzenie (thinning):** zostawienie losowej części punktów
  z zachowaniem proporcji.
- **Hasz:** liczba wyliczona z numeru gwiazdy, która wygląda losowo, ale
  dla tego samego numeru jest zawsze taka sama.
- **int16:** liczba całkowita w 2 bajtach (od −32 767 do 32 767); tu
  położenie w jednostkach ~0,038 pc.
- **Jasność absolutna M_G:** jak jasna byłaby gwiazda z odległości 10 pc;
  im mniejsza liczba, tym jaśniejsza gwiazda (Słońce: M_G ≈ 4,7).
- **HTTP Range:** prośba do serwera o fragment pliku zamiast całości.
- **Shader:** mały program uruchamiany na karcie graficznej dla każdego
  punktu z osobna, równolegle.
- **Mieszanie addytywne:** kolory nakładających się punktów się sumują,
  jak światło, a nie zasłaniają jak farba.
- **Widok face-on / edge-on:** Galaktyka oglądana z góry / z boku
  (z płaszczyzny dysku).
