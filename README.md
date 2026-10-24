---
typ: projekt
status: w_trakcie
utworzono: 2026-10-24
przebudowa: 2026-10-24
---

# Inwestowanie XTB — doradca inwestycyjny (system agentów)

Protokół działania: [[CLAUDE]]. Spec źródłowy (archiwum, wdrożony wybiórczo): [[MASTER-PROMPT]].

## Jak używać
1. Terminal: `cd ~/Projekty/CichyOperator/CichyOperator/Inwestowanie-XTB && claude`. Start z tego folderu jest ważny, bo ładuje `CLAUDE.md` i subagentów.
2. Piszesz naturalnie: „Sprawdź CDR.PL”, „Czy warto kupić TTWO.US?”, „Mam 5000 zł, jak wejść w XTB.PL?”, „XTB.PL -8%, co się stało?”, „Przegląd portfela”, albo wklejasz screenshot wykresu.
3. Raport: `analizy/`, wykres: `wykresy/`, liczby: `dane/`.

## Praca z telefonu (Claude Code w chmurze)
Działa w aplikacji Claude (zakładka **Code**) albo na claude.ai/code. Sesja startuje w chmurze z repozytorium na GitHubie. `CLAUDE.md`, subagenci z `.claude/agents/` i hook instalujący biblioteki ładują się automatycznie.

Wymagania: plan Claude **Pro lub Max** i konto GitHub.

1. **Własne repo:** otwórz link do repo-szablonu → **Use this template → Create a new repository** → nazwa np. `inwestowanie-xtb`, **Private**. Każdy ma swoją kopię, swój portfel i swój dziennik.
2. **Połącz GitHub z Claude:** aplikacja Claude → Code → przy pierwszym uruchomieniu połącz GitHub i zainstaluj aplikację **Claude** na swoim nowym repo.
3. **Dostęp do sieci (bez tego skrypty nie pobiorą kursów):** domyślne środowisko „Trusted” blokuje Yahoo Finance. Na ekranie nowej sesji otwórz wybór środowiska → ustawienia środowiska → **Network access**:
   - najprościej: **Full**;
   - albo **Custom** z domenami `query1.finance.yahoo.com` i `query2.finance.yahoo.com` + zaznaczone „Also include default list of common package managers”. Pobieranie raportów PDF ze stron spółek wymaga wtedy dopisania ich domen.
   Jeśli w aplikacji nie widać tych ustawień, zrób to raz na claude.ai/code w przeglądarce telefonu. Środowisko jest wspólne dla wszystkich urządzeń.
4. **Start:** nowa sesja → wybierz repo → napisz np. „Sprawdź CDR.PL”. Pierwsza sesja instaluje biblioteki (ok. 1 min).
5. **Wyniki:** Claude zapisuje raporty i wykresy w repo i pushuje je na gałąź sesji. Podgląd: aplikacja GitHub albo github.com → gałąź sesji → `analizy/`.
6. Na początek uzupełnij `portfel.md` (kapitał, ryzyko, pozycje). Możesz poprosić o to Claude w sesji.

**Aktualizacje szablonu** (autor, lokalnie): `bash scripts/export_repo.sh && cd .cache/repo-export && git add -A && git commit -m "opis zmian" && git push`. Eksport zastępuje portfel, dziennik i raporty pustymi szablonami. Kopia zrobiona z szablonu nie aktualizuje się sama: w sesji na telefonie napisz „pobierz zmiany z szablonu Hipas98/inwestowanie-xtb, nie ruszaj mojego portfel.md, dziennik.md i analizy/”.

## Architektura
```
Użytkownik → CEO (główna sesja, CLAUDE.md)
           ├─ skrypty (jedyne źródło liczb): tech · fundamentals · position · portfolio · pdf_text
           ├─ WebSearch/WebFetch: newsy, katalizatory, potwierdzenie w źródle pierwotnym
           ├─ subagent adwokat-diabla (sonnet): najmocniejszy argument przeciw
           └─ subagent weryfikator (opus): każda liczba vs dane/źródła → PASS/FAIL
        → raport w analizy/ → decyzja użytkownika → dziennik.md (uczenie)
```

Zasada konstrukcyjna: **model interpretuje, skrypty liczą, weryfikator sprawdza.** Badania nad LLM w finansach pokazują poważne halucynacje liczb, które spadają, gdy model korzysta z narzędzi i danych zamiast pamięci.

## Co zostało ze speca, co wycięte i dlaczego
| Element speca | Decyzja | Powód |
|---|---|---|
| Agent fundamentalny, raportów, techniczny, makro/sentyment, risk, portfel, strategia wejścia | **Zostaje** jako moduły CEO + skrypty | Rdzeń decyzji |
| Weryfikacja danych, FAKT/INTERPRETACJA/PROGNOZA | **Wzmocnione**: skrypty + weryfikator + źródło pierwotne | Priorytet nr 1 speca |
| Konflikty agentów | **Zostaje** + adwokat diabła jako osobny kontekst | Debata bull/bear (TradingAgents) ogranicza efekt potwierdzenia |
| Confidence 0–100 | **Zmienione** na jawną rubrykę, max 85 | Liczba „z powietrza” to fałszywa precyzja |
| Ocena X/10 | **Usunięte** | Duplikat confidence |
| Portfolio Health/Risk Score 0–100 | **Zastąpione** konkretnymi miarami (koncentracja, efektywna liczba pozycji, waluty, korelacje, flagi) | Mierzalne zamiast wymyślonej skali |
| Osobny agent price action, cykliczności, porównawczy | **Wycięte** jako osobni agenci; elementy w technice i fundamentach | Ten sam kontekst danych, osobny agent = koszt tokenów bez nowej informacji |
| Baza przypadków historycznych, backtest formacji | **Wycięte** | Wymaga płatnych danych i lat pracy; małe próbki dają złudzenie przewagi |
| Opportunity scanner, alerty | **Odłożone** (v2) | Najpierw działający pipeline na 1 spółce |
| Prawdopodobieństwa scenariuszy | **Zgrubne**, kroki co 10% | Oceny, nie wyliczenia |
| Brak w specu: koszty XTB, podatki PL, IKE/IKZE, CFD | **Dodane** | Realnie zmieniają wynik netto |
| Brak w specu: punkt odniesienia (ETF na indeks) | **Dodane** | Inwestorzy indywidualni średnio tracą do rynku; „nie kupuj” to wynik |
| Brak w specu: dziennik decyzji i lekcji | **Dodane** | Bez zapisu decyzji nie ma uczenia się |

## Dane i koszty
| Co | Skąd | Koszt |
|---|---|---|
| Kursy GPW i USA, ETF-y, kursy walut | Yahoo Finance chart API (nieoficjalne, bez klucza) | 0 zł |
| Benchmark | GPW: ETF Beta WIG20TR (Yahoo nie ma historii indeksów GPW), USA: S&P 500 | 0 zł |
| Fundamenty kwartalne i roczne | Yahoo fundamentals-timeseries (agregator) | 0 zł |
| Potwierdzenie wyników | raporty spółek (PDF przez `pdf_text.py`), ESPI, SEC | 0 zł |
| Newsy, katalizatory | WebSearch w Claude Code | w limicie planu |

Odrzucone: XTB API (wyłączone 14.03.2025), stooq (CSV za testem anty-botowym).
Ryzyko: nieoficjalne endpointy Yahoo mogą się zmienić. Wtedy wymieniamy tylko `scripts/common.py`.

## Status
- [x] Skrypty: tech, fundamentals, position, portfolio, pdf_text (testy: XTB.PL, TTWO.US, portfel próbny, raport XTB H1 2026)
- [x] Protokół CEO, rubryka confidence, kontekst XTB/podatki
- [x] Subagenci: weryfikator, adwokat diabła
- [ ] `portfel.md`: kapitał, ryzyko, pozycje (użytkownik)
- [ ] Pierwszy pełny raport dla spółki z portfela, z PASS od weryfikatora

**Kryterium ukończenia v1:** jeden pełny raport z PASS weryfikatora dla realnej spółki z portfela + `portfolio.py` na prawdziwym portfelu.

## Dalej (po v1)
- v2: import CSV z eksportu historii xStation do `portfel.md`, skaner okazji na liście obserwowanych, alerty cenowe (cron/n8n).
- v3: oficjalne fundamenty USA z SEC EDGAR (darmowe, wymaga User-Agent), kalendarz wyników.

## Źródła researchu (2026-10-24)
- [Tabela opłat XTB z 29.05.2026](https://www.xtb.com/pl/pliki/02.-tabela-oplat-i-prowizji_pl_clean.pdf), [XTB: akcje bez prowizji](https://pl.xtb.com/inwestuj-w-akcje-bez-prowizji)
- [XTB: wyłączenie API](https://www.xtb.com/cy/help-center/our-platforms-2/do-you-offer-api-2), [XTB: historia i eksport w xStation](https://www.xtb.com/cy/help-center/our-platforms-2/history-on-the-xstation-platform-2)
- [Limity IKE/IKZE 2026](https://strefainwestorow.pl/emerytura/limit-ike-ikze-2026)
- [W-8BEN i dywidendy USA](https://www.sii.org.pl/17839/analizy/newsroom/xtb-wprowadza-automatyczny-w-8ben-latwiej-o-nizszy-podatek-od-dywidend-z-usa.html), [PIT-38 dla dywidend zagranicznych](https://freenance.io/podatki/podatek-od-dywidend-amerykanskich-2026-w-8ben-15-procent-jak-zlozyc-rozliczyc-pit-38/)
- [Ostrzeżenie CFD (77%)](https://brokerchooser.com/pl/broker-reviews/xtb-review/cfd-risk-warning)
- [TradingAgents (debata bull/bear)](https://arxiv.org/abs/2412.20138), [Halucynacje LLM w finansach](https://arxiv.org/abs/2311.15548v1)
- [Barber & Odean: wyniki inwestorów indywidualnych](https://faculty.haas.berkeley.edu/odean/Papers%20current%20versions/Individual_Investor_Performance_Final.pdf)
- [Subagenci Claude Code](https://code.claude.com/docs/en/sub-agents)
