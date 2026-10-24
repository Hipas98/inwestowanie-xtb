# Wiedza: doradca XTB (wersja dla projektu Claude)

Stan: tabela opłat XTB z 29.05.2026, limity IKE/IKZE na 2026. Opłaty i przepisy się zmieniają. Przed decyzją zależną od kosztu albo podatku sprawdź aktualne źródło.

## 1. Koszty XTB (akcje i ETF-y, nie CFD)
- Prowizja 0% do 100 000 EUR obrotu miesięcznie. Powyżej: 0,2%, minimum 10 EUR za transakcję.
- **Przewalutowanie 0,5% w każdą stronę**, gdy instrument jest w innej walucie niż rachunek. Akcja z USA na rachunku PLN: ok. 1% za kupno i sprzedaż.
- Opłata 10 EUR/mies. za nieaktywność, gdy jednocześnie: brak transakcji przez 365 dni i brak wpłaty przez 90 dni. Nie dotyczy, gdy jest otwarta pozycja. Nie dotyczy IKE/IKZE.
- Wypłata środków bezpłatna.
- XTB nie ma API (wyłączone 14.03.2025). Historię transakcji można wyeksportować z xStation do CSV.
- CFD: 77% rachunków detalicznych traci pieniądze (ostrzeżenie regulacyjne XTB).

## 2. Podatki (Polska)
- 19% od zysku kapitałowego (Belka). XTB wystawia PIT-8C, rozliczenie w PIT-38 do 30 kwietnia roku następnego.
- Stratę z giełdy można odliczać od zysków przez 5 kolejnych lat [szczegóły limitów sprawdzić w aktualnych przepisach].
- Dywidendy z USA: 15% podatku u źródła (W-8BEN) + dopłata 4% w Polsce. Dywidendy z GPW: 19% pobrane u źródła.
- IKE/IKZE: bez Belki przy spełnieniu warunków ustawowych. **Nie zwalniają z amerykańskiego podatku u źródła od dywidend.**
- Limity wpłat 2026: IKE 28 260 zł, IKZE 11 304 zł (działalność gospodarcza: 16 956 zł).
- Pozycje długoterminowe lepiej trzymać na IKE/IKZE. Krótkie spekulacje na koncie zwykłym tracą 19% zysku.

## 3. Punkt odniesienia
- Alternatywa dla każdej spółki: tani ETF na indeks (GPW: ETF na WIG20TR, np. Beta ETF WIG20TR; USA/świat: ETF na S&P 500 albo MSCI World).
- Badania (Barber & Odean) pokazują, że inwestorzy indywidualni wybierający spółki tracą do rynku średnio kilka punktów procentowych rocznie, a najaktywniejsi najwięcej. Częsty handel to koszt, nie przewaga.
- Rekomendacja „kupić” wymaga powodu lepszego niż „może urośnie”.

## 4. Gdzie szukać danych
| Co | Źródło pierwotne | Pomocniczo |
|---|---|---|
| Cena GPW/USA | screenshot xStation (z godziną) | stooq.pl, bankier.pl, biznesradar.pl, Yahoo Finance |
| Wyniki GPW | raport okresowy / prezentacja na stronie IR spółki, komunikaty ESPI | stockwatch.pl, biznesradar.pl |
| Wyniki USA | 10-Q / 10-K / 8-K (SEC EDGAR), strona IR | Yahoo Finance, macrotrends |
| Kalendarz wyników i dywidend | strona IR spółki, komunikat ESPI | portale |
| Newsy | komunikat spółki | PAP Biznes, Parkiet, Bankier, Reuters (zawsze z datą) |

## 5. Confidence (rubryka)
Start 50. Plus za każdy spełniony warunek:
- +10 trend zgodny z kierunkiem decyzji (wyższe dołki i szczyty, cena nad rosnącą średnią 200-sesyjną)
- +10 wyniki poprawiają się r/r, potwierdzone raportem spółki
- +5 wycena (P/E, EV/EBITDA) poniżej własnej historii przy nie gorszych wynikach
- +5 spółka silniejsza od indeksu przez ostatnie 6 miesięcy
- +10 R:R do pierwszego targetu ≥ 2

Minus za każdy:
- −10 wyniki albo ważne zdarzenie w ciągu 10 dni (ryzyko luki cenowej)
- −10 konflikt techniki i fundamentów
- −10 cena lub dane niepotwierdzone albo nieaktualne
- −10 niska płynność (mały obrót, szerokie spready)
- −10 adwokat diabła ma argument bez odpowiedzi

Zakres 10–85. Wypisz, które punkty zadziałały.

## 6. Kontrola danych (checklista na końcu każdej analizy)
- [ ] Cena ma źródło i datę/godzinę notowania
- [ ] Każda liczba fundamentalna ma link do źródła i datę publikacji
- [ ] Ostatni kwartał potwierdzony w raporcie lub komunikacie spółki
- [ ] Liczba akcji, koszty, strata i R:R z kalkulator_pozycji.py
- [ ] Jest invalidation (poziom + zdarzenia)
- [ ] Jest porównanie z ETF na indeks
- [ ] Jest sekcja adwokata diabła
- [ ] Brak słów „na pewno”, „gwarantowane”
- [ ] Poziomy ze screenshota oznaczone jako odczyt wizualny

## 7. Szablon pełnego raportu
```
# <Nazwa> (<TICKER>) — RRRR-MM-DD
Ostrzeżenia: (np. cena sprzed 2 dni, wyniki za 3 dni)

1. DECYZJA: kupić / kupić etapami / obserwować / czekać na poziom / unikać
   Najważniejszy argument + co spółka daje ponad ETF na indeks.
2. SYTUACJA TERAZ: cena [źródło, data], zmiana 1M/1R, trend, najważniejsze wydarzenie.
3. FUNDAMENTY: wyniki r/r [link], marże, dług netto, wycena teraz vs historia.
4. TECHNIKA: trend, wsparcia, opory, wolumen.
5. KATALIZATORY: najbliższe zdarzenia z datami; nowe czy już wycenione.
6. PLAN WEJŚCIA (z kalkulatora): | Transza | Cena | Akcje | Koszt PLN | Warunek |
7. TARGETY (z kalkulatora): | Target | Cena | Ruch % | Zysk netto PLN | R:R |
8. INVALIDATION: poziom + zdarzenia, które unieważniają tezę.
9. ADWOKAT DIABŁA: 3–5 argumentów przeciw i odpowiedź na każdy.
10. SCENARIUSZE: 🟢 byczy (~X%) · 🟡 bazowy (~X%) · 🔴 niedźwiedzi (~X%), zgrubnie co 10%.
11. CONFIDENCE: X/100 + punkty rubryki. Najważniejszy poziom. Największe ryzyko.
KONTROLA DANYCH: checklista z sekcji 6.
ŹRÓDŁA: lista linków z datami.
DO ZAPISANIA: ticker · data · decyzja · invalidation · targety · data przeglądu
```
