# Jak liczymy odległości — po ludzku

Ten dokument opisuje kamień milowy M3: jak z pobranych kafelków Gai
(`docs/JAK_POBIERAMY_DANE.md`) powstaje katalog, w którym każda gwiazda ma
odległość, przedział niepewności i położenie w Galaktyce. Kod jest w
`milkyway/parallax.py`, `milkyway/distance.py` i `milkyway/build.py`,
decyzje w `docs/DECISIONS.md` (D-005, D-013, D-020). Wszystkie liczby
poniżej policzyliśmy na naszych danych 31.10.2026.

---

## 1. Co się dzieje w M3

Na wejściu mamy 192 kafelki z **23 371 857** gwiazdami Gai i dwie tabele
Hipparcosa. Na wyjściu jest jeden katalog (Parquet, schemat w wersji 2)
z **23 373 946** wierszami: gwiazdy Gai plus 2 089 gwiazd, które ma tylko
Hipparcos. Budowa trwa 4–7 minut (`python MilkyWay.py --build`).

Każdy kafelek przechodzi tę samą drogę:

1. poprawiamy paralaksę o **zero-point** (rozdział 2),
2. z poprawionej paralaksy liczymy **odległość i jej przedział**
   (rozdział 3),
3. liczymy **położenie w przestrzeni**: względem Słońca i względem środka
   Galaktyki (rozdział 5),
4. dokładamy rzeczy znane ze starego pipeline'u: kolor do wyświetlania,
   szacunek masy, prędkości UVW (dla 19 mln gwiazd z prędkością radialną)
   i klasę gwiazdy z położenia na diagramie HR.

Niczego po drodze nie wyrzucamy. Gwiazdy z wątpliwą astrometrią (np.
RUWE ≥ 1,4, czyli 3,4 mln wierszy, 14,6%) zostają, z zapisanym
wskaźnikiem. Cięcie do 1,25 kpc zrobi dopiero eksport do viewera (M4).

## 2. Zero-point, czyli waga, która zawsze trochę zaniża

Wyobraź sobie wagę kuchenną, która zawsze pokazuje o 3–4 gramy za mało.
Przy kilogramie mąki to nieważne, ale przy szczypcie soli zmienia wszystko.
Paralaksy Gai mają taki stały błąd: są przeciętnie **za małe o kilkadziesiąt
mikrosekund łuku** (µas; 1 mas = 1000 µas). Ten błąd to **zero-point**.

Lindegren i współpracownicy (2021) zmierzyli go na kwazarach, które są tak
daleko, że ich prawdziwa paralaksa to zero, więc wszystko, co Gaia dla nich
pokazuje, jest błędem. Wyszło, że zero-point zależy od jasności gwiazdy, jej
koloru i położenia na niebie względem ekliptyki. ESA udostępnia gotowy
program (`gaiadr3-zeropoint`), który dla każdej gwiazdy liczy tę poprawkę.
Stosujemy go tak:

**paralaksa poprawiona = paralaksa zmierzona − zero-point**

Zero-point jest zwykle ujemny, więc poprawiona paralaksa jest **większa**,
a gwiazda **bliżej**. W naszym katalogu:

| G (mag) | gwiazd | mediana zero-pointu | mediana błędu paralaksy |
|---|---|---|---|
| 6–7 | 14 184 | −30,6 µas | 26,2 µas |
| 9–10 | 288 365 | −27,8 µas | 17,3 µas |
| 12–13 | 3 089 339 | −21,9 µas | 15,1 µas |
| 14–15 | 11 643 956 | −39,5 µas | 22,6 µas |

Ważne jest to, że **poprawka jest tego samego rzędu co błąd pomiaru**
(mediana −37 µas przy typowym błędzie 15–23 µas). Pominięcie jej nie jest
więc drobiazgiem: dla jasnych gwiazd to przesunięcie o 1–3 odchylenia
standardowe w jedną stronę.

Skutek na liczbach: mediana paralaksy rośnie o **3,2%**. Gwiazda, która bez
poprawki leżałaby 1000 pc od nas, po poprawce leży ok. 966 pc. W promieniu
1,25 kpc jest teraz **17,20 mln** gwiazd, a bez poprawki byłoby ich
16,44 mln. Około 760 tys. gwiazd „wjechało” do środka.

### Co, gdy gwiazda wypada poza zakres programu

Program ma sprawdzony zakres: jasność 6 < G < 21 i kolor w określonych
granicach. Poza nim zwraca brak wyniku albo wynik ekstrapolowany, czyli
zgadywany. U nas poza zakresem jest **33 606** gwiazd: 6 470 jaśniejszych
niż G = 6, 773 o skrajnym kolorze z rozwiązaniem 5-parametrowym i 26 729
z rozwiązaniem 6-parametrowym (to te, u których Gaia musiała zgadywać
kolor). Takim gwiazdom wpisujemy wartość z **samego brzegu zakresu**
(minimalnie do środka, bo program traktuje brzeg jako „poza”) i flagę
`zp_origin = lindegren2021_clamped`. Dzięki temu poprawka jest zawsze
skończona i rozsądnej wielkości. To nasza decyzja (plan v4, S2 D5), nie
zachowanie programu.

## 3. Od paralaksy do odległości

Odległość w parsekach to po prostu **1000 / paralaksa w mas**. Robimy tak
dla wszystkich gwiazd (D-020). Ciekawsze jest to, **jak pewna** jest ta
liczba.

Pomiar paralaksy ma błąd σ, rozkład „dzwonowy” (gaussowski). Jeśli
paralaksa to ϖ ± σ, to odległość leży najpewniej między **1000/(ϖ + σ)**
a **1000/(ϖ − σ)**. Te dwie liczby zapisujemy jako `r_lo_pc` i `r_hi_pc`,
a środek 1000/ϖ jako `dist_pc`. Odpowiadają one 16%, 50% i 84%
prawdopodobieństwa, tak jak „±1σ”. Przedział nie jest symetryczny: w górę
sięga dalej niż w dół, bo dzielenie przez coraz mniejszą liczbę rośnie
coraz szybciej.

**Przykład z naszego katalogu** (Gaia DR3 4466765988430592, G = 12,07):

- paralaksa zmierzona: 0,996844 mas, błąd 0,014472 mas;
- zero-point: −0,034574 mas, więc paralaksa poprawiona to 1,031418 mas;
- odległość: 1000 / 1,031418 = **969,5 pc** (bez poprawki byłoby 1003,2 pc);
- przedział: od 1000 / 1,045890 = **956,1 pc** do 1000 / 1,016946 =
  **983,3 pc**.

Typowa niepewność rośnie z odległością (mediana połowy przedziału jako
procent odległości):

| odległość | gwiazd | niepewność | przesunięcie przez zero-point |
|---|---|---|---|
| < 250 pc | 1,13 mln | 0,3% | 1 pc |
| 250–500 pc | 3,33 mln | 0,7% | 5 pc |
| 500–1000 pc | 8,91 mln | 1,4% | 20 pc |
| 1000–1250 pc | 3,83 mln | 2,2% | 48 pc |
| > 1250 pc | 6,18 mln | 3,0% | 85 pc |

Przy 1 kpc zero-point przesuwa gwiazdy o ok. 2 razy więcej, niż wynosi
ich niepewność pomiarowa.

### Gwiazdy o słabej paralaksie

Gdy paralaksa jest mniej niż 5 razy większa od swojego błędu (ϖ/σ ≤ 5),
proste odwrócenie zaczyna oszukiwać: przedział robi się szeroki
i niesymetryczny, a środek jest przesunięty. Takich gwiazd jest
**187 607** w Gai (0,8%) i 1 009 w Hipparcosie. Dostają flagę
`dist_flag = low_snr`. Ich typowa niepewność to ±31% odległości, wobec
±1,8% u pozostałych. Dla 1 614 z nich ϖ − σ ≤ 0, więc górna granica nie
istnieje i `r_hi_pc` jest puste.

Lepsza metoda (prior EDSD Bailer-Jonesa, plan v4 S2 D3) dodaje wiedzę
„gwiazd jest więcej daleko niż blisko” i daje rozsądniejsze odległości dla
słabych paralaks. Zmieniłaby jednak obraz tylko dla tych 0,8% gwiazd,
a kosztuje kilka sesji pracy, więc odkładamy ją na później. Viewer może te
gwiazdy przygasić.

## 4. Hipparcos: kogo dokładamy, a kogo nie

Hipparcos jest potrzebny dla gwiazd, które Gaia zmierzyła źle albo wcale.
Reguła jest prosta: **gwiazda z Hipparcosa wchodzi do katalogu tylko
wtedy, gdy Gaia nie ma dla niej pełnego rozwiązania z paralaksą** (5p/6p).
Trudność polega na ustaleniu, czy je ma:

1. Ze **118 184** gwiazd Hipparcosa **97 984** ma w tabeli ESA
   `hipparcos2_best_neighbour` wskazany odpowiednik w Gai z paralaksą.
   Te gwiazdy bierzemy z Gai.
2. Pozostałe 19 247, które przechodzą naszą selekcję (paralaksa > 0,5 mas,
   G < 15; dla 160 gwiazd bez koloru B−V sprawdzamy jasność V, bo G
   nigdy nie jest wyraźnie słabsze od V), przesuwamy z epoki Hipparcosa (1991,25) na epokę Gai (2016,0)
   wzdłuż ich ruchu własnego, bo przez 25 lat gwiazda przesuwa się po niebie,
   i szukamy w kafelkach Gai gwiazdy w tym samym miejscu.
3. **17 158** z nich ma tam odpowiednik, mimo że tabela ESA go nie
   podawała. Gdybyśmy zaufali samej tabeli, te gwiazdy byłyby w katalogu
   dwa razy.
4. Zostaje **2 089** gwiazd Hipparcosa, w tym 117 najjaśniejszych
   (G < 3), których Gaia nie umie zmierzyć.

Wiersze Gai z odpowiednikiem dostają numer HIP (kolumna `hip`, 113 635
wierszy), co ułatwia późniejsze porównania. Każdy numer występuje raz.

Dlaczego tyle gwiazd o przeciętnej jasności (G = 6–9) nie ma odpowiednika?
Sprawdziliśmy 40 z nich bezpośrednio w archiwum. **36 ma w Gai tylko
rozwiązanie 2-parametrowe**, czyli pozycję bez paralaksy (zwykle ciasne
układy podwójne). Hipparcos jest wtedy jedynym źródłem odległości, więc te
wiersze są potrzebne.

Reguła dopasowania przeszła trzy poprawki, wszystkie wymuszone danymi:

- **2″ zamiast 1″.** W próbce dwie gwiazdy miały odpowiednik w Gai
  1,2–1,3″ od pozycji z Hipparcosa (błędy ruchu własnego przez 25 lat),
  więc przy 1″ weszłyby podwójnie.
- **Poniżej 0,5″ jasność nie ma znaczenia.** Najpierw wymagaliśmy też, żeby
  jasność z Hipparcosa (przeliczona z V na G) zgadzała się z Gaią
  z dokładnością do 1 mag. Test 60 pc pokazał, że to psuje dopasowanie
  bardzo czerwonych karłów: **Proxima Centauri** trafiłaby do katalogu
  dwa razy, bo przeliczenie V → G dla tak chłodnych gwiazd jest
  niedokładne. Teraz gwiazda bliżej niż 0,5″ to ta sama gwiazda, a kryterium
  jasności stosujemy tylko między 0,5″ a 2″, gdzie bliski sąsiad może być
  naprawdę inną, słabszą gwiazdą.
- **Układy podwójne do 3″.** Hipparcos często mierzył łączne światło
  dwóch bliskich gwiazd, a Gaia widzi je osobno. Jeśli w odległości do 3″
  jest gwiazda Gai o tej samej paralaksie (w granicach 3 błędów) i nie
  więcej niż 2,5 mag słabsza, to jest to ten sam układ (tak jest np.
  z 70 Ophiuchi). Dzięki temu 41 układów nie wchodzi dwa razy. Limit
  2,5 mag chroni przed sytuacją, w której słaby towarzysz „zastępuje”
  jasną gwiazdę główną, której Gaia nie zmierzyła.

Zostaje znane ryzyko: w próbce 1 na 40 gwiazd Hipparcosa Gaia ma, ale z
paralaksą poniżej naszego progu (czyli daleko). Takiego duplikatu nie da
się wykryć bez dodatkowego pobrania. To ok. 2,5% z 2 089 wierszy, czyli
kilkadziesiąt gwiazd na 23 mln.

## 5. Gdzie jest gwiazda: dwa układy współrzędnych

Katalog trzyma położenie w dwóch układach:

- **Heliocentryczny** (`x_pc, y_pc, z_pc`): Słońce w środku, oś x w stronę
  środka Galaktyki, y w kierunku obrotu Galaktyki, z w stronę jej północnego
  bieguna. Wygodny do mapy okolicy.
- **Galaktocentryczny** (`xgc_pc, ygc_pc, zgc_pc`): środek Galaktyki
  w środku. Używamy standardowych parametrów astropy `v4.0`: Słońce leży
  8122 pc od centrum i **20,8 pc nad płaszczyzną dysku**, czyli w punkcie
  (−8121,97; 0; 20,8) pc. Te 20,8 pc to drobne przechylenie całego układu,
  dlatego różnica między układami nie jest dokładnie przesunięciem o 8122 pc.

Nasza przykładowa gwiazda z rozdziału 3 leży w (−8834,8; 91,0; −630,1) pc:
ok. 710 pc dalej od centrum niż Słońce i 630 pc pod płaszczyzną Galaktyki.

## 6. Czy nowy pipeline liczy to samo co stary

To jedno z kryteriów „gotowe” planu 1.0 (D-013). Stary katalog 60 pc
powstał z innymi cięciami (dobra paralaksa, RUWE < 1,4) i bez limitu
jasności, więc do porównania pobraliśmy osobno wszystkie gwiazdy Gai
z paralaksą > 16,67 mas (97 394 wiersze, 9 minut) i przepuściliśmy je przez
nowy kod z tymi samymi cięciami. Wynik (`tests/test_reference.py`):

- **Gaia:** dokładnie te same **58 931** gwiazd, paralaksy identyczne co do
  bitu.
- **Hipparcos:** z 2 585 gwiazd starego katalogu nowy nie ma 10. To
  układy podwójne, które stary katalog miał dwa razy: raz z Hipparcosa,
  raz składnik z Gai 2,3–2,9″ obok, z tą samą paralaksą. Nowy ma za to
  2 gwiazdy więcej. Stary kod dopasował je do słabego sąsiada 1,5–1,6″
  obok (różnica jasności 4,6 i 6,2 mag) i przez to zgubił.
- **Odległości:** różnią się wyłącznie o zero-point. Dla 4,0% gwiazd różnica
  przekracza 3 połówki przedziału niepewności. To zawsze gwiazdy, dla
  których zero-point jest większy niż 3 błędy paralaksy: bliskie, jasne,
  zmierzone bardzo precyzyjnie. Dla nich poprawka znaczy najwięcej.

## 7. Skutki uboczne i czego (jeszcze) nie robimy

- **Odległości z prostego odwrócenia** są obciążone dla 0,8% gwiazd ze słabą
  paralaksą (rozdział 3). Do mapy wystarczą. Do pomiaru grubości dysku plan
  v4 każe dopasowywać model wprost do paralaks (D-006). W 1.0 robimy
  szacunek orientacyjny (M5).
- **Błędy paralaks bierzemy takie, jak podaje Gaia.** Wiadomo, że dla
  jasnych gwiazd są nieco niedoszacowane (do ~30%). Mnożnik istnieje
  w kodzie, ale na razie wynosi 1.
- **Hipparcos to katalog z 1997 roku**, ten sam co w starym pipeline'ie,
  a nie nowsza redukcja van Leeuwena (2007). Dla 2 089 gwiazd ma to
  niewielkie znaczenie.
- **Porównanie ESA z AIP** (czy oba archiwa zwracają te same bity, T6)
  czeka: 31.10 ESA odpowiadało błędem 503.

## 8. Słowniczek

- **Paralaksa (ϖ):** pozorne przesunięcie gwiazdy w ciągu roku, gdy Ziemia
  krąży wokół Słońca. Im większe, tym gwiazda bliżej. 1 mas ↔ 1000 pc.
- **mas, µas:** milisekunda i mikrosekunda łuku. 1 mas = 1000 µas, czyli
  grubość włosa oglądanego z ok. 20 km.
- **Zero-point:** stały błąd paralaks Gai, zależny od jasności, koloru
  i położenia. U nas mediana −37 µas.
- **σ (sigma):** błąd pomiaru; prawdziwa wartość leży w ±1σ z
  prawdopodobieństwem ~68%.
- **ϖ/σ:** jakość paralaksy; powyżej 5 proste odwrócenie jest wiarygodne.
- **Kwantyl:** wartość, poniżej której leży dany procent możliwości;
  mediana to kwantyl 50%.
- **Rozwiązanie 2p / 5p / 6p:** ile parametrów Gaia wyznaczyła. 2p = sama
  pozycja (bez paralaksy), 5p = pozycja, paralaksa, ruch własny, 6p = to
  samo plus kolor zgadnięty z astrometrii.
- **Epoka:** chwila, do której odnosi się pozycja (Hipparcos 1991,25,
  Gaia DR3 2016,0).
- **RUWE:** miara, jak dobrze ruch gwiazdy pasuje do modelu pojedynczej
  gwiazdy; powyżej 1,4 zwykle podwójna albo zaburzona.
- **Heliocentryczny / galaktocentryczny:** układ ze Słońcem albo ze środkiem
  Galaktyki w początku.
- **EDSD:** sposób liczenia odległości, który zakłada, że gęstość gwiazd
  maleje wykładniczo z odległością; lepszy dla słabych paralaks, odłożony.
