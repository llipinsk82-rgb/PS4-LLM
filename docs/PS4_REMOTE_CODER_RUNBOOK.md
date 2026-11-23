# PS4 Garlic Coder — plan uruchomienia zdalnego laboratorium
Data: 2026-11-23. Tryb: CTO/minimal, PS4 = poligon, jedna aplikacja testowa. Ten dokument to plan, NIE potwierdzenie wdrożenia.

## 0. Zweryfikowany punkt startowy
- Dell/Windows, dostep przez SentinelX: host_a711939dc741ef09, IPv4 192.168.1.108.
- PS4/GoldHEN: ostatnio potwierdzony adres 192.168.1.120; FTP TCP 2121 PASS, Remote Package Installer 12800 FAIL. BinLoader 9090 byl osiagalny, ALE jest jednopolaczeniowy — NIGDY nie testuj go proba polaczenia TCP, bo mozna zuzyc sesje.
- Konto PS4: tylko lokalne; firmware podany jako 10.01 (numer jeszcze do potwierdzenia w interfejsie).
- Repo Dell D:\BlackServ_Coder\garlic-llm, GitHub llipinsk82-rgb/PS4-LLM, branch blackserv/coder-experiments, start HEAD c1d8b07 (clean).
- Gotowe oryginalne PKG w D:\BlackServ_Coder\packages: Garlic-LLM-1.20-experimental.pkg 5662638080 B (dzialal), Garlic-LLM-1.21-experimental.pkg 6022889472 B (CE-41839-5).
- Nasze wagi na PS4: /data/garlic/models/QwopusFlash/qwen3.5-9b-q4s.bin, model.idx, qwen3.5-9b-mtp.bin, mtp.idx. Zgodne kopie na Dellu w models/QwopusFlash.
- DELL Python 3.13 i Zig 0.14.1; brak gotowego OpenOrbis w lokalnym toolchain; brak potwierdzonego Chiaki. Polecenie winget niedostepne na DELL.
- Weryfikacja modelu: model.idx QwopusFlash jest identyczny z chat/assets_9b/model.idx (sha256 a941bdaf4d031af36f8010...); model.idx wskazuje /data/qwen3.5-9b-q4s.bin, gpu_size/weights_size = 4068630528 B. Pelny plik wag Qwopus = 4641752088 B, a metadane JSON maja size=4641752088 i gpu_size=4068630528. To celowe: dodatkowe dane odczytywane sa z pliku (CPU embeddings), NIE dowod bledu indeksu. Kompatybilnosc generowanych odpowiedzi nadal nieprzetestowana.

## 1. Priorytet nr 1: pierwszy dostep do ekranu i kontrolera BEZ drabiny w kolejnych iteracjach
1. CTO na Dellu: pobierze Windows x64 portable Chiaki-ng WYŁACZNIE z https://github.com/chiaki-ng/chiaki-ng/releases , sprawdzi wydawce/archiwum/hash i przygotuje katalog narzedzi. Nie korzystac z chiaki-ng.com (nie jest domena tworcow); nie wymagac winget.
2. Uzytkownik raz przy PS4: sprawdzi firmware/wersje GoldHEN i czy widzi ekran (HDMI/monitor). Sprawdzi, ze GoldHEN dziala. Settings > Remote Play Connection Settings > Enable Remote Play. Dodatkowa opcja PSVita/PSTV, jesli obecna i wymagana.
3. CTO w Chiaki-ng ustawi reczna rejestracje IPv4 192.168.1.120 i PS4, konto lokalne z GoldHEN: sprobowac Account-ID fffffffffff= (11 liter f i znak =), bez logowania PSN. Na PS4 Settings > Remote Play Connection Settings > Add Device. Uzytkownik przekaże jednorazowy osmiocyfrowy PIN widoczny na PS4; nie zapisac PIN w publicznym Git.
4. PASS: na Dellu widac obraz PS4, da sie przejsc do Settings, wrocic Home, sterowac kierunkami i X/O, wyjsc z sesji i polaczyc ponownie dwa razy bez dotykania PS4.
5. Jesli konsola nie ma dostepnego obrazu i nie widac PIN-u: REAL_BLOCKER pierwszego parowania. Potrzeba tymczasowo HDMI do monitora, capture lub obrazu dostepnego z dolu. Nie zgadywac PIN-u. Jesli konto lokalne nie paruje: sprawdzic opcje GoldHEN Remote Play Enabler; offline aktywacja Apollo tylko po zbadaniu ryzyka dla save'ow i wyraznej zgodzie.

Dokumentacja: https://consolemods.org/wiki/PS4:Remote_Play ; https://github.com/GoldHEN/GoldHEN ; https://chiaki-ng.github.io/chiaki-ng/setup/configuration/

## 2. Test trwalosci dostepu bez fizycznej obslugi
1. Odczyt po WiFi/Ethernet na tej samej sieci, brak guest isolation. Zapisac aktualny IP. Zalecana rezerwacja DHCP na routerze, nie wprowadzac bez potrzeby statycznego IP.
2. Przetestowac w Chiaki bezpieczna nawigacje, sesje 10-15 min i ponowne polaczenie.
3. Dopiero po PASS polaczenia: PS4 Settings > Power Save Settings > Set Features Available in Rest Mode > Stay Connected to the Internet i Enable Turning On PS4 from Network (jesli dostepne); test wejscia w Rest Mode i wybudzenia, z uzytkownikiem w domu.
4. Pelny restart PS4 NA KONCU dnia, nie na poczatku: moze zdezaktywowac GoldHEN i wymusic ponowny jailbreak. Brak zdalnego exploita = dokumentowany ogranicznik autonomii.
5. Brak streamu/zawieszenie: najpierw ping/FTP i log Chiaki, potem lokalna diagnostyka. Bez aktualizacji firmware i PSN.

## 3. Zdalne instalowanie PKG, bez jednopolaczeniowego BinLoader
1. Sprawdzic dostepna w GoldHEN opcje Remote Package Install. Nie zakladac, ze to to samo co HTTP API flatz. Jezeli brak kompatybilnej, wybrac niezalezna aplikacje Remote Package Installer skompilowana OOSDK (sprawdzic pochodzenie i kompatybilnosc z FW 10.01).
2. CTO pobierze zweryfikowany PKG instalatora i wgra przez juz dzialajacy FTP do /data/pkg/. Uzytkownik przez Chiaki (lub jednorazowo z kontrolera) zainstaluje go z GoldHEN Package Installer. To ostatni przewidywany reczny krok.
3. Uruchomic RPI zdalnie przez Chiaki i DOPIERO wtedy sprawdzic API HTTP 192.168.1.120:12800. Nie opierac PASS na otwartym porcie: zrobic faktyczne zapytanie statusowe.
4. CTO wystawi z Della plik PKG na lokalnym serwerze HTTP pod 192.168.1.108 (bez Internetu, ograniczenie firewalla do LAN), zleci instalacje przez API i odczyta wynik. Najpierw niewielki bezpieczny pakiet testowy, nie zepsuty 1.21.
5. UWAGA: klasyczny RPI odbiera nowe polecenia tylko gdy aplikacja jest aktywna/na pierwszym planie. Najpierw otworz RPI, potem wyslij instalacje, poczekaj az job zostanie zaakceptowany, dopiero pozniej zmien ekran. Po instalacji uruchomienie Garlic przez Chiaki/sterowanie to OSOBNY krok. Nie weryfikowac dostepnosci przez BinLoader 9090.

Zrodla: https://github.com/flatz/ps4_remote_pkg_installer ; https://consolemods.org/wiki/PS4:Remote_PKG_Installer

## 4. Zdalne uruchamianie z ChatGPT (osobny dowod, nie obietnica)
1. Chiaki daje UZYTKOWNIKOWI ekran i sterowanie Dell->PS4. Nie oznacza, ze SentinelX ma interaktywny dostep do okna GUI; agent Dell dziala jako usluga.
2. Rozwazyc programowalny protokol Remote Play: pyremoteplay lub playdirector (API emulujace DualShock, bez GUI); najpierw audyt kodu i zaleznosci w osobnym venv. Nie zakladac zgodnosci identyfikatorow parowania z Chiaki.
3. Testy stopniowe: polaczenie i stan, bezpieczny przycisk, Home, uruchomienie istniejącej aplikacji, obserwacja skutku przez stream/log; brak zdalnego wyboru programu po TITLE_ID w samym RPI.
4. PASS 'ChatGPT uruchamia aplikacje' dopiero gdy SentinelX wykona kontrolowane polecenie przycisku i stan PS4 sie zmieni. Jezeli API niedzialajace, fallback: uzytkownik 1 raz klika w Chiaki na Dellu; drabina zbedna.
5. Bezpieczniki: brak makr kasujacych dane/system; brak publicznego serwera sterowania, tokeny parowania poza repo.

Kandydat: https://pyremoteplay.readthedocs.io/en/stable/readme.html

## 5. Garlic Coder: minimalna wersja oparta na dzialajacym 1.20
1. Po PASS sterowania: oryginalny Garlic 1.20 commit upstream 49f08c6 jako wyjsciowy silnik; osobny worktree Dell w D:\BlackServ_Coder\workspace aby nie mieszac z branch 1.21. Jeden finalny TITLE_ID / jedna aplikacja Coder; brak menu wielu modeli.
2. Preferowany maly PKG 'app-only' BEZ --full. W 1.20 chat/engine.c: weights_locate najpierw wybiera /app0/models/<nazwa> jesli taki plik istnieje; w app-only bierze sciezke model.idx z /data. Model.idx identyczny dla obu wag.
3. Najmniejsza adaptacja: poprawic sciezki wag w model.idx/mtp.idx wewnatrz assetow nowego PKG na juz istniejace pliki /data/garlic/models/QwopusFlash/ (bez ponownego kopiowania 4.64 GB). Alternatywa: bez zmian indeksu przeniesc pliki do sciezek oryginalnych; nie robic obu rzeczy naraz. Dodatkowy /data /app0 fallback sprawdzic.
4. Zweryfikowac wymagane kernels.bin, tokenizator, formaty q4s/q3s, CPU embedding, MTP, RAM / GPU memory; liczyc typy tensora i sprawdzic zakresy offsets w model.idx (max konca 4641752088 B = rozmiar wag). Brak pelnego PASS az do wykonania inferencji PS4.
5. Build wymaga OpenOrbis/PS4 toolchain i create-fself; Zig sam nie wystarczy. Zainstalowac dopiero oficjalne, audytowalne wersje narzedzi na Dellu; build/test w workspace; git diff/check/status, commit/push po PASS. Pkg startuje bez oryginalnych wag /all-in-one.
6. Zdalnie zlecic instalacje Coder, zobaczyc instalacje i uruchomic Garlic przez Chiaki (lub API kontrolera po PASS). Nie testowac kolejnych wariantow 1.21 bez konkretnej hipotezy.

## 6. Kryteria E2E akceptacji i regresji
- RP-01: bez PSN lokalne konto sparowane, stream i wejscie do menu PASS;
- RP-02: powtorne polaczenie x2 oraz opcjonalne wybudzenie z Rest Mode PASS;
- PKG-01: zdalny instalator odbiera zlecenie i instaluje niewielki PKG bez BinLoader PASS;
- CTRL-01: uzytkownik uruchamia program z Chiaki PASS; osobno AUTO-01: ChatGPT przez SentinelX podaje INPUT i uruchamia program PASS albo BLOCKED (nie udawac);
- MODEL-01: Coder bootuje, brak CE-41839-5, nowy log lub ekran aplikacji;
- MODEL-02: /health gdy API aktywne oraz 3 prompty, w tym dwa kodujace, poprawna odpowiedz i potwierdzenie faktycznego modelu;
- MODEL-03: pomiar first-token i token/s, kod sprawdzony na Dellu lokalnymi testami (bez samowolnego SSH);
- MODEL-04: zamknij/otworz ponownie 2x bez utraty modelu;
- KONIEC: spis stanu: firmware/GoldHEN/Chiaki/IP/wersja PKG/SHA/repo commit, PASS/FAIL i znane ograniczenia.

## 7. Minimalne zadania do podzialu
- CTO teraz: dokumentacja, repo/host audyt, weryfikacja indeksu, przygotowanie bezpiecznego narzedzia Windows (bez naruszania PS4).
- Uzytkownik po 16:30: zapewnic jednorazowy dostep do menu i do kodu parowania PIN; aktywowac GoldHEN; reszte testow wykonywac po Dell/Chiaki.
- CTO po parowaniu: konfiguracja RPI+HTTP, ewentualne API kontrolera, build Coder 1.20, testy i diagnostyka, commit/push.
- Stop tylko przy realnym braku zdalnego obrazu/PIN-u, naruszeniu stanu konta, prawdziwym ryzyku dla danych, firmware lub ograniczeniu narzedzi.
