# Doradca XTB w darmowym Claude (Projekt na telefonie)

Cały system z tego repo skompresowany do 4 plików. Działa w zwykłym czacie Claude, na darmowym planie, w aplikacji na telefonie.

## Pliki
| Plik | Gdzie trafia | Co daje |
|---|---|---|
| `INSTRUKCJE-PROJEKTU.md` | wklejasz w pole **Instrukcje** projektu | protokół zespołu: zasady danych, routing, kolejność analizy |
| `wiedza.md` | **Pliki** projektu | koszty XTB, podatki, IKE/IKZE, skąd brać dane, adwokat diabła, weryfikacja, rubryka, szablon raportu |
| `doradca.py` | **Pliki** projektu | wskaźniki, wsparcia/opory i wykres z pliku notowań; wielkość pozycji po kosztach XTB i podatku; przegląd portfela |
| `portfel.md` | **Pliki** projektu (najpierw uzupełnij) | kapitał, limity ryzyka, pozycje, dziennik, lekcje |

## Ustawienie (raz, ok. 10 minut)
1. **Pobierz paczkę:** [doradca-xtb.zip](https://github.com/Hipas98/inwestowanie-xtb/raw/main/projekt-free/doradca-xtb.zip) → w aplikacji Pliki stuknij ZIP, żeby go rozpakować (powstanie folder z 4 plikami).
2. **Włącz narzędzia:** Claude → Ustawienia → Funkcje → włącz **Wykonywanie kodu i tworzenie plików** oraz **wyszukiwanie w internecie**.
3. **Utwórz projekt:** Projekty → Nowy projekt → „Doradca XTB”. Jeśli aplikacja nie ma tej opcji, zrób to na claude.ai w przeglądarce telefonu.
4. **Instrukcje:** otwórz `INSTRUKCJE-PROJEKTU.md`, skopiuj całość, wklej w pole **Instrukcje** projektu. Ten plik wklejasz, nie wgrywasz.
5. **Pliki:** w projekcie „Dodaj plik” → `wiedza.md`, `doradca.py`, `portfel.md`. Jeśli plik .py się nie wgrywa: „Dodaj tekst”, wklej treść i nazwij `doradca.py`.
6. **Portfel:** uzupełnij `portfel.md` przed wgraniem albo napisz w czacie projektu „Uzupełnij ze mną portfel”, a potem podmień plik.
7. **Test:** nowy czat w projekcie → „Sprawdź CDR.PL”. Claude poda linki do pobrania notowań. Pobierz plik, dołącz go do czatu, a odpowiedź powinna zawierać wykres z poziomami.

## Jak używać na co dzień
- **Analiza spółki:** otwórz w przeglądarce `https://stooq.pl/q/d/l/?s=cdr&i=d` (zamień `cdr` na ticker; spółki z USA: `ttwo.us`) oraz benchmark `https://stooq.pl/q/d/l/?s=wig20&i=d` (USA: `s=^spx`). Dołącz oba pliki do czatu i napisz „Czy warto kupić? Mam 3000 zł na IKE”.
- Do tego **screenshot z xStation** z aktualną ceną: najlepsze źródło bieżącej ceny.
- „Sprawdź X”: szybki przegląd, oszczędza limit.
- „X -8%, co się stało?”: wyjaśnienie ruchu.
- „Przegląd portfela” + screenshot listy pozycji z xStation: flagi przebitych poziomów, koncentracja, waluty.
- Po transakcji: „Kupiłem 10 CDR po 265 na IKE”. Claude poda nowy `portfel.md` do podmiany w plikach projektu.

## Co działa jak w pełnej wersji, a co słabiej
| Element | Status |
|---|---|
| Wskaźniki, poziomy, siła względna, wykres | jak w pełnej wersji, pod warunkiem że dołączysz plik notowań |
| Wielkość pozycji, koszty XTB, podatek, R:R | jak w pełnej wersji |
| Przegląd portfela | jak w pełnej wersji, ceny podajesz Ty (screenshot) |
| Koszty, podatki, rubryka, szablon raportu | jak w pełnej wersji |
| Adwokat diabła i weryfikator | te same procedury, ale w tym samym czacie (mniej niezależne niż osobni agenci) |
| Fundamenty | z wyszukiwarki zamiast skryptu; wolniej i mniej systematycznie |
| Portfel i dziennik | podmieniasz plik ręcznie |
| Limity | darmowy limit odnawia się co ~5 h; pełny raport zużywa go szybko |

Gdy stooq pokazuje komunikat o limicie zamiast pliku, użyj zapasowego linku z `wiedza.md` (Yahoo).

To narzędzie wspierające decyzje, nie doradztwo inwestycyjne. Decyzja należy do Ciebie.
