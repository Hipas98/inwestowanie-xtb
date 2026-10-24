# Doradca XTB w darmowym Claude (Projekt, bez Claude Code)

Wersja „lite” systemu z tego repo. Działa w zwykłym czacie Claude, także na darmowym planie i w aplikacji na telefonie.

## Co jest w środku
| Plik | Gdzie trafia | Po co |
|---|---|---|
| `INSTRUKCJE-PROJEKTU.md` | wklejasz w pole **Instrukcje** projektu | protokół: zasady danych, routing, kolejność analizy |
| `wiedza.md` | **Pliki** projektu | koszty XTB, podatki, IKE/IKZE, rubryka confidence, szablon raportu, checklista |
| `kalkulator_pozycji.py` | **Pliki** projektu | liczy akcje na transzę, stratę, zysk netto po kosztach XTB i podatku, R:R |
| `portfel.md` | **Pliki** projektu (po uzupełnieniu) | Twój kapitał, limity ryzyka i pozycje |

## Ustawienie (raz, ok. 10 minut)
1. **Włącz narzędzia:** Claude → Ustawienia → Funkcje (Capabilities) → włącz **Wykonywanie kodu i tworzenie plików** (Code execution and file creation) oraz **wyszukiwanie w internecie**. Bez wykonywania kodu kalkulator nie zadziała.
2. **Utwórz projekt:** Projekty → Nowy projekt → nazwa „Doradca XTB”. Jeśli w aplikacji nie ma tej opcji, zrób to na claude.ai w przeglądarce telefonu. Na darmowym planie możesz mieć do 5 projektów.
3. **Instrukcje:** otwórz [INSTRUKCJE-PROJEKTU.md (surowy tekst)](https://raw.githubusercontent.com/Hipas98/inwestowanie-xtb/main/projekt-free/INSTRUKCJE-PROJEKTU.md), skopiuj całość i wklej w pole instrukcji projektu.
4. **Pliki:** pobierz i dodaj do plików projektu:
   - [wiedza.md](https://raw.githubusercontent.com/Hipas98/inwestowanie-xtb/main/projekt-free/wiedza.md)
   - [kalkulator_pozycji.py](https://raw.githubusercontent.com/Hipas98/inwestowanie-xtb/main/projekt-free/kalkulator_pozycji.py)
   - [portfel.md](https://raw.githubusercontent.com/Hipas98/inwestowanie-xtb/main/projekt-free/portfel.md), najpierw uzupełniony

   Na telefonie: otwórz link → udostępnij/zapisz do Plików → w projekcie „Dodaj plik”. Jeśli wgranie pliku nie działa, użyj „Dodaj tekst”: skopiuj treść i nadaj nazwę jak oryginał.
5. **Test:** nowy czat w projekcie → „Sprawdź CDR.PL”. Odpowiedź powinna mieć cenę z datą, źródła z linkami i decyzję.

## Jak używać
- **Najlepsze dane: screenshot z xStation.** Wyślij zrzut wykresu (z widoczną ceną i interwałem) + pytanie, np. „Czy warto kupić? Mam 3000 zł na IKE”.
- „Sprawdź X”: szybki przegląd, oszczędza limit.
- „Czy warto kupić X?” / „Mam N zł, jak wejść w X?”: pełny raport z planem wejścia.
- „X -8%, co się stało?”: wyjaśnienie ruchu.
- „Przegląd portfela”: sprawdzenie pozycji z portfel.md.
- Po transakcji: „Kupiłem 10 CDR po 265 na IKE”. Claude poda nową treść portfel.md, którą podmieniasz w plikach projektu.

## Ograniczenia wobec wersji Claude Code (uczciwie)
| | Claude Code (repo) | Projekt w darmowym Claude |
|---|---|---|
| Kursy i wskaźniki | skrypt pobiera dane z Yahoo, liczy SMA/RSI/ATR i poziomy | z wyszukiwarki lub Twojego screenshota; brak automatycznych wskaźników |
| Wykres z naniesionymi poziomami | generowany automatycznie | brak; Claude czyta Twój screenshot |
| Fundamenty | skrypt + weryfikacja w raporcie spółki | wyszukiwarka + raport spółki |
| Arytmetyka pozycji | skrypt | ten sam kalkulator (w środowisku kodu) |
| Weryfikator i adwokat diabła | osobni subagenci (niezależny kontekst) | sekcje w tej samej odpowiedzi; słabsza niezależność |
| Portfel i dziennik | pliki aktualizowane automatycznie | podmieniasz plik ręcznie |
| Limity | plan Pro/Max | darmowy limit odnawia się co ~5 h; pełny raport z wyszukiwaniem zużywa go szybko |

Najsłabszy punkt tej wersji to aktualność ceny. Zawsze sprawdzaj, czy cena w raporcie zgadza się z xStation.

To narzędzie wspierające decyzje, nie doradztwo inwestycyjne. Decyzja należy do Ciebie.
