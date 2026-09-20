# Produktpilot: Kontingent, lokale Messung und Wiederverwendung

Stand: 2026-09-19, Ausgangspunkt `6eac77e`. Dies ist eine lokale Kalkulation
und Implementierungsbeschreibung, **keine neue Betriebsfreigabe**. Keine
Cloudabfrage, kein Modellaufruf, keine Live-Policy-/Budgetaenderung und kein Deployment.
Die bestehende automatische Grant-Erneuerung bleibt vollstaendig unveraendert.

## Umsetzungsstand 2026-09-20

Das Messpaket wurde als **ed6a59d** getrennt nach `origin/main` gepusht.
Abschliessend behoben: Loeschsperre auch im Messkern und beobachtbarer aktiver
Messzustand; fehlgeschlagener Kostenimport wird nicht teilweise als bekannt
uebernommen. Commit enthaelt ausschliesslich sieben Mess-/Integrations-/Testdateien.
190 Swift-Tests sowie Simulator- und unsigned Device-Build waren vor dem Commit gruen.

**Lokal vorbereiteter, separat versionierter Policy-Diff:** `Coordinator.proposed_owner_quota()`
erzeugt aus einer bestehenden 3/12-Ownerpolicy den expliziten Modus
`owner-100-v1`: 10/UTC-Tag, 100 Owneradmissions insgesamt, **nicht 100 weitere**.
Korrekturen, zugelassene Fehler und bereits verbrauchte Owneradmissions zaehlen mit.
Gemeinsame Countgrenzen werden 26/116 (16 historische Abnahmen plus 10/100).
USD23.43 ist ausschliesslich die kumulierte Bruttoreservierungszaehlung, kein neues
Geldbudget; die USD2.343 Tages-/Monatsgeldgrenzen, USD3.76500465 Periodengrenze,
volle Einzelreserve vor Dispatch, ein gleichzeitiger Vorgang, Originalende,
vier alte Holds und Stop bei neuem Hold bleiben erhalten.

`transition_owner_quota()` ist ein separat aufzurufender, AI-off-geschuetzter
CAS-Uebergang mit ETag und Ledger-/Policyhash. Er veraendert nur die Policybindung,
schreibt ein neues Audit und laesst Ownerverbrauch, Buckets, Altholds sowie das
urspruengliche Migrationsaudit unveraendert. Kein Reset, keine automatische
Migration beim Start. Tests migrieren nach zwei verbrauchten Anfragen und
erreichen genau 100 ueber UTC-/Monatswechsel und Neustarts; 11/Tag und 101 gesamt
werden abgewiesen, ebenso aktive/gesperrte oder konkurrierend geaenderte Daten.
Geld kann weiterhin frueher sperren. Kein Provisionierungsskript/Liveartefakt
wurde geaendert, kein Grant erzeugt, kein Livezugriff ausgefuehrt.

Die **unveraenderte** Erneuerung prueft weiterhin die 3/12-Baseline und den
EUR12-Netto-Stopp. Sie wuerde die neue Policy als Drift ablehnen. Eine spaetere
Aktivierung erfordert deshalb eine gesonderte koordinierte Betriebsfreigabe;
dieser lokale Diff ist ausdruecklich **nicht deploy-/aktivierungsfertig**.

Abschlussreview am 20.09.: 169 gezielte Tests in `test_pilot.py` und
`test_pilot_renewal.py` bestanden mit Mock-Stores/Mock-Cloud. Der bestehende
Policycode musste dabei nicht erweitert werden. Keine Live-Konfiguration,
kein Grant, kein Ledger und keine Erneuerung wurden veraendert.

Produktreview, Messungsergaenzungen und manueller Geraetepruefplan stehen in
[Produktwiederverwendung: Abschlussreview](product-reuse-review-2026-09-20.md).

**Tatsaechlich implementierter Produktablauf:** In Ernaehrung oeffnet
"Produkt vom Etikett" die manuelle Etikettpruefung; alternativ fuehrt der
vorhandene Text-/Foto-KI-Review ueber "Als Produkt speichern" in denselben
Editor. Keine neue OCR-/KI-Pipeline. Fehlende Bezugsmenge und Einheit werden
nicht geraten: beide sind Pflicht. Verpackungswerte erfordern den ausdruecklichen
Abgleich mit dem Etikett; eine Aenderung der Angaben hebt diese Bestaetigung auf.
Aus KI stammende Werte starten als KI-Schaetzung, nicht als Verpackungswerte.

"Produkt speichern" schreibt nur ein `FoodPreset`. Namenssuche in "Produkte
und Favoriten", Produktwahl, frei eingegebene Menge in derselben Einheit,
lokale Decimal-Vorschau und **"Heute hinzufuegen"** bilden den Wiederverwendungspfad.
Keine Modell-/Netzwerkanforderung in Editor, Suche, Skalierung oder Speichern.
Kein g/ml-Wechsel, kein Ueberschreiben der Basis, kein Eintrag bei Abbruch.
Isolierter SwiftData-Kontext, Save-Rollback und Doppelsave-Sperre verhindern
Teilpersistenz und unbeabsichtigtes Mitspeichern fremder Bearbeitungen.

Vorhandene Presets erhalten nur optionale Felder `baseQuantity`, `baseUnit`,
`valueOrigin`, `baseCalories`; letzteres erhaelt Dezimalkalorien, ohne das alte
Integerfeld umzudeuten. Legacy-Favoriten bleiben feste Portionen. Eintraege
erhalten optionale Herkunfts-/Mengen-Snapshots; spaetere freie Wertkorrekturen
entwerten die Verpackungsherkunft. Produktbasis und Herkunft sind sichtbar.
Backups transportieren die optionalen Felder; Altbackups ohne Felder bleiben
lesbar. Ungueltige Produktmengen/Einheiten/Herkunft werden vor der bestehenden
Importbestaetigung abgewiesen. Keine parallele Datenbank, kein Analyticsdienst.
Produktspeichern bekommt `productSaved` als eigenen Messausgang und wird nicht
als erfolgreicher Ernaehrungseintrag ausgewertet; seine Kosten bleiben enthalten.

**Upgrade geprueft:** Das vorhandene AppPersistence-Harness extrahiert die echten
Modellquellen aus `6eac77e` per `git archive`, erstellt damit in einem getrennten
Prozess einen SQLite-Store mit drei Presets, drei Eintraegen und verknuepftem
Training und oeffnet ihn danach mit den neuen Appmodellen. Werte, Zeitpunkte,
Notizen, Trainingsbeziehungen und Marker bleiben erhalten; neue optionale Felder
sind nil. Anschliessendes Produkt-/Portionsspeichern und Backup funktionieren.
Das prueft echte SwiftData-Lightweight-Migration auf macOS, nicht nur JSON-Decoding.
Ein Rueckwaertsstart der alten App auf dem aktualisierten Store wird nicht
versprochen; vor einem spaeteren Geraeteupgrade ein Backup erstellen.

Lokale Pruefbefehle (keine Installation, keine Cloud):

```sh
cd ios/FoodAnalysisKit && DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test
cd ios/EntraAuthKit && DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer swift test
zsh ios/ActivitySummaryKit/Tests/AppPersistence/run-tests.sh
cd ai-gateway && env -u AI_PILOT_ENABLED -u AI_API_ONLY_ENABLED -u APP_ENV .venv/bin/python -m pytest tests/test_pilot.py tests/test_pilot_renewal.py -q
```

Die Befehle jeweils vom Repositorywurzelverzeichnis beginnen. Xcode-Builds:
bestehendes Projekt/Scheme, Debug mit `generic/platform=iOS Simulator`, Release
mit `generic/platform=iOS`, jeweils `CODE_SIGNING_ALLOWED=NO` und DerivedData
ausserhalb des Repos. Keine Buildnummeraenderung. Offen bleiben die manuellen
Geraetepruefungen fuer Kamera/Fotopicker, Tastatur/Suche, verschachtelte Sheets,
Hintergrund, Dateidialoge und Upgrade einer persoenlichen Geraeteinstallation.

Die folgenden Kostenabschnitte sind der unveraenderte Kalkulationsstand vom
19.09., keine erneute Liveabfrage. Abschnitt 3 haelt den damaligen Plan als
Vergleich fest; der oben beschriebene Produktpfad ist inzwischen lokal implementiert.

## 1. Zielkontingent und Kosten

Ziel: hoechstens **10 neue KI-Operationen je UTC-Tag und 100 insgesamt** im
verbleibenden Originalzeitraum bis **2026-10-18T22:19:10Z**. Korrekturen und
zugelassene Fehlversuche sind darin enthalten, nicht zusaetzlich. Das entspricht
bei einer bis vier Operationen je gespeicherter Erfassung hoechstens 100 bis 25
Eintraegen, noch ohne verworfene/fehlgeschlagene Erfassungen. Zehn taeglich sind
eine Spitze, kein Anspruch auf zehn an jedem verbleibenden Tag.

### Unveraenderte Ausgangslage

Quelle: [Pilotfreigabe und Budget](../infra/pilot/README.md).

- Zeitraum seit 2026-09-18T22:19:10Z; kein neuer 30-Tage-Zeitraum.
- 16 historische Admissions, kumuliert USD3.7488 reserviert; keine Zaehlererstattung.
- Bekannte historische Modellkosten USD0.01620465 plus **vier unbekannte Holds
  USD0.9372** = USD0.95340465. Holds bleiben voll erhalten und ungeklaert.
- Zuletzt dokumentiert: EUR0.104338845268762 netto gebucht am 19.09., mit
  unbekanntem Rechnungsnachlauf. Das ist kein frischer Kostenabruf. Gebuchte
  Kosten ueberlappen Modell-/Hostingpositionen; nicht nochmals obenauf addieren.
- Owner-Zaehler zuletzt 0; live weiterhin **3/Tag, 12 insgesamt**, eine Admission
  pro Minute, eine laufende Operation, USD0.2343 Vollreserve je neuer Operation.
- Kumulierte Owner-Vollreserve USD2.8116, taeglich USD0.7029; bekannte Kosten
  plus aktive/unbekannte Reserven der Originalperiode hoechstens USD3.76500465.
- Gemeinsame Tages-/Monats-Geldgrenze USD2.343 und gemeinsame Tages-/Monatszaehler
  19/28 gelten zusaetzlich mit historischer Belegung. Oktober setzt weder das
  Owner-Gesamtkontingent noch die Periodengrenze zurueck.
- EUR20 Betrieb, davon EUR18 Arbeitshuelse und EUR2 Notpuffer; separate EUR5
  Setup/Abnahme sind kein Nutzungsbudget. EUR2.19 Korrektur- und EUR1.35
  iPhone-Reserve bleiben gebunden. Insgesamt EUR21.54 gebunden, EUR3.46 Restpuffer
  innerhalb der getrennten EUR20+5; keine automatische Umwidmung.
- EUR12 netto kumulierter Betriebsstopp und alle frueheren Teilgrenzen bleiben
  bestehen. Neue unbekannte Kosten/zusatzlicher Hold bedeuten Stopp und Klaerung;
  die vier eingefrorenen Alt-Holds sind keine Erlaubnis fuer weitere Holds.

### Erwarteter Verbrauch, nicht garantierte Istkosten

Bestehendes [Preisprofil](../ai-gateway/app/providers/pricing.py): USD0.825 je
Million ungecachte Eingabetokens, USD4.95 je Million Ausgabetokens. Annahme:
durchschnittlich 4000 Eingabetoken-Aequivalente einschliesslich Bildanteil und
1000 Ausgabetokens **ueber alle Erstanalysen und Korrekturen**. Kein Cache-Rabatt,
kein Free Tier; groessere Bilder/Korrekturkontexte koennen den Mittelwert erhoehen.
Der niedrige einzelne Abnahmewert USD0.0015279 ist keine belastbare Prognose.
USD-Betraege werden planerisch mit 1.50 EUR/USD einschliesslich Puffer bewertet,
nicht mit einem beobachteten Wechselkurs.

| Erwartungsposition | USD | EUR mit Faktor 1.50 |
| --- | ---: | ---: |
| Modell je Anfrage: (4000 x 0.825 + 1000 x 4.95) / 1000000 | 0.00825 | 0.012375 |
| Modell fuer 10 Anfragen | 0.08250 | 0.123750 |
| Modell fuer 100 Anfragen | 0.82500 | 1.237500 |
| ACA fuer 100 isolierte Starts/Anfragen, einschliesslich Requests | 0.25129 | 0.376935 |
| Functions fuer 100 Anfragen | 0.04554 | 0.068310 |
| **100 Anfragen, Modell + direktes Hosting** | **1.12183** | **1.682745** |
| Erneuerungsjob einschliesslich Gateway-Nachlauf, bis zu 64 Laeufe | 0.23760 | 0.356400 |

Hostingannahmen: je Anfrage 335 ACA-Sekunden (5 Start + 30 Anfrage + 300 Nachlauf)
bei 0.25 vCPU/0.5 GiB, USD0.000024/vCPU-s und USD0.000003/GiB-s, Requests
USD0.40/Million. Functions: 0.5 GB x 35 s, USD0.000026/GB-s plus
USD0.40/Million Ausfuehrungen. Erneuerung: 64 x (180 Job + 315 Gateway) Sekunden
bei denselben ACA-Ressourcen. Langsame/haeufige Starts, KV, Table, Netzwerk und
sonstiger Verkehr sind keine Nullkosten und bleiben in der folgenden Betriebshuelse.

### Konservative Reservierung und freigegebene Ueberschuesse

Die Vollreserve USD0.2343 basiert auf dem gesamten erlaubten Profil, nicht auf
dem Durchschnitt. Fuer 100 Admissions ergeben sich **USD23.43 = EUR35.145
kumulierte Bruttoreservierungen**, fuer zehn pro Tag USD2.343 = EUR3.5145.
Das ist weder der erwartete Verbrauch noch bei Parallelitaet eins gleichzeitig
gebundenes Geld. Eine Garantie fuer 100 maximal teure Operationen passt nicht
in EUR20 Betrieb.

Bei bekanntem Settlement zum erwarteten Preis werden je Erfolg USD0.22605
freigegeben. Nach 99 solchen Settlements sind das USD22.37895. Direkt vor dem
100. Dispatch sind damit konservativ noch
`0.95340465 + 99 x 0.00825 + 0.2343 = USD2.00445465`
gebunden: historische Kosten **mit allen vier Holds**, 99 bekannte neue Kosten
und eine neue volle Reserve. Nach allen 100: USD1.77840465. Bei zehn sequentiellen
Durchschnittsanfragen betraegt der neue Tagesanteil vor der letzten Admission
USD0.30855, zuzueglich eventuell vorhandener Tagesbelegung.

| Sicht fuer den gesamten Originalzeitraum | EUR |
| --- | ---: |
| Registry, bisher und verbleibend, unveraenderte Reserve | 6.45 |
| Sonstiger Betrieb, bisher und verbleibend | 4.30 |
| Cleanup und begrenzter Nachlauf, nicht fuer KI verfuegbar | 1.50 |
| Historische Modellkosten + vier Holds, ungerundet | 1.430106975 |
| Erwarteter neuer Modellverbrauch fuer 100 | 1.237500000 |
| **Erwartungsmodell innerhalb konservativer Hosting-/Cleanuphuellen** | **14.917606975** |
| **Dasselbe vor letztem Dispatch inklusive dessen Vollreserve** | **15.256681975** |
| **100 maximal teure Operationen statt Erwartungsmodell** | **48.825106975** |

Registry: bestehender EUR-Listenwert 4.293 netto x 1.50 Sicherheitsfaktor,
auf EUR6.45 gerundet. Die EUR4.30 enthalten bereits die obigen Anfrage-Hostingkosten
und **EUR0.50 fuer Erneuerung** (EUR0.3564 Rechenannahme plus kleine KV/Tablekosten).
Diese Positionen nicht nochmals addieren. Die historische Budgetreserve EUR1.50
bleibt bestehen; die ungerundete Zeile erklaert nur die Rechnung. EUR2 Notpuffer
und Setupreserven bleiben ausserhalb dieser Tabelle unangetastet. EUR14.92 sind
eine gemischte Planungs-/Risikosicht, keine erwartete Azure-Rechnung und keine
Entwarnung gegenueber dem EUR12-Netto-Stopp.

**Empfehlung:** 10/100 ist als spaeteres Zielkontingent bei rollierender voller
Vorabreserve und bekanntem Settlement plausibel, nicht als garantiertes Volumen.
Auch Geldgrenzen koennen vorher greifen: Laegen alle 100 im gleichen Monatsbucket
mit der historischen Baseline, duerften die ersten 99 im Mittel hoechstens
USD0.01166965 kosten, damit vor der letzten Admission USD2.343 eingehalten wird.
Der reine Periodendeckel erlaubte hier USD0.02603333; die Monatsgrenze ist enger.
Bei jedem Dispatch muessen trotzdem alle Grenzen einzeln passen.

**Heute nicht nutzbar:** Settlements entlasten aktive/shared Kosten und
`period_cost`, niemals Admissions oder kumulierte `reserved`-Zaehler. Die
3/12-Grenzen, Zaehler 19/28, Tages-/Bruttoreservegrenzen und die an 3/12 gebundene
Erneuerungspruefung blockieren 10/100 weiterhin. Insbesondere reserviert deren
Prognose alle verbleibenden Vollreserven. Eine spaetere Umsetzung erfordert eine
separat genehmigte, koordinierte Aenderung dieser Grenzen und Prognose mit
historischer Zaehlerfortfuehrung. Live wurde nichts davon veraendert.

## 2. Lokale Produktmessung

Implementiert fuer den bestehenden **KI-Erfassungs-/Reviewpfad** sowie lokale
Produkterstellung/-wiederverwendung, nicht fuer manuelle Ernaehrungseintraege,
alte Sofort-Favoriten oder Historienwiederverwendung. Kein Analytics-Dienst,
kein API-Vertragswechsel, keine SwiftData-Modell-/Backupmigration fuer Messdaten.
`kind` unterscheidet `aiCapture`, `productCreation`, `productReuse`; alte
Messdatensaetze ohne Feld sind KI-Erfassungen. Der verlinkte Abschlussreview
definiert die lokalen Such-/Dialoggrenzen, Zeitzuordnung und Abbruchausgaenge.

- Beginn: erste nichtleere Texteingabe oder explizites Oeffnen der Fotoauswahl/
  Kamera. Der Messlauf verwendet dieselbe UUID wie sein spaeterer Review.
- Ende `saved`: erst nach erfolgreichem bestehenden Insert/Save. Fehlgeschlagene
  Saves zaehlen separat und beenden die Erfassung nicht; Doppelspeichern bleibt
  gesperrt. Dauer schliesst Eingabe, Pruefung, Korrekturen und Save ein.
- `activeSeconds` und `inactiveSeconds` trennen aktive App-Zeit von inaktivem/
  Hintergrundzustand. Navigation weg von einer laufenden Analyse pausiert die
  aktive Messzeit, nicht die Anfrage. Monotone, auch im Schlaf fortlaufende Uhr; keine Differenz
  veraenderbarer Kalenderzeiten. Aktive Zeit ist keine praezise Aufmerksamkeitsmessung.
- Jede Operations-ID hat separat `waitSeconds` inklusive Hintergrund und
  `activeWaitSeconds`. Wartezeit misst den Client-Serviceaufruf einschliesslich
  Auth/Netzwerk, nicht nur Modelllaufzeit. Aktive Erfassungszeit enthaelt diese
  Wartezeit; nicht addieren. `activeSeconds - Summe(activeWaitSeconds)` ergibt
  beobachtete aktive Zeit ausserhalb der Analyse.
- KI-Korrekturen: Anzahl unterschiedlicher `isCorrection`-Operations-IDs.
  Wiederholungen derselben ID erhoehen `sends`, nicht die Korrekturzahl. Manuelle
  Aenderungen zaehlen als `manualCorrectionRounds` zwischen Refine/Save/Verwerfen/
  Schliessen, nicht pro Tastendruck. Rueckgaengig gemachte Aenderungen ohne
  verbleibende Draft-Differenz zaehlen nicht.
- Servicefehler und explizites Anfrage-Abbrechen zaehlen `technicalAborts` pro
  Operation; Retry bleibt im gleichen Messlauf. `sends` bezeichnet Clientversuche,
  keine bestaetigten Server-Admissions oder garantiert kostenpflichtigen Aufrufe.
- `discarded` bei ausdruecklichem **Verwerfen** im KI-Review beziehungsweise
  **Abbrechen** im lokalen Produktdialog. Sheet-Wegwischen,
  implizites Schliessen/Ersetzen oder Verlassen einer offenen Eingabe werden
  `incomplete`, nicht als bewusstes Verwerfen behauptet. Verlassen nach einem
  initialen Analysefehler sowie Bildverarbeitungs-/Konfigurationsfehler koennen
  als `technicalAbort` enden. Operationsfehler bleiben auch bei spaeterem Save sichtbar.
- Fuer Zeit-bis-Speichern nur `outcome == saved && timingComplete` verwenden;
  andere Ausgaenge und unvollstaendige Saves separat ausweisen. In-Progress-
  Exporte sind Zwischenstaende, keine abgeschlossenen Messungen.
- Ein spaeterer Dispatch ohne beobachteten Eingabestart wird `timingComplete=false`.
  Nach Prozessabbruch werden offene Archive beim Neustart `incomplete`; keine
  Endzeit oder fehlende Dauer wird erfunden. Nur letzte gespeicherte Checkpoints
  sind Untergrenzen; `waitComplete=false` kennzeichnet eine unvollstaendige
  Analysewartezeit. Es gibt keine atomare Transaktion zwischen SwiftData und
  Diagnosearchiv: ein Crash dazwischen darf keinen vermeintlichen Save erzeugen.

Lokal: `Application Support/LocalProductMetrics/captures-v1.json`, atomare Writes,
iOS-Dateischutz, Verzeichnis vom OS-Backup ausgeschlossen. Nicht im bestehenden
Ernaehrungsbackup enthalten. Gespeichert werden nur IDs, Zeitpunkte/Dauern,
Status, Zaehler und zugeordnete Kosten, **keine Texte, Fotos, Naehrwerte,
Fehlertexte, Tokens oder Nutzeridentitaeten**. Keine automatische Uebertragung.
Zeitpunkte/IDs bleiben persoenliche Metadaten: nur bewusst exportieren/weitergeben.

Im Statistik-Symbol der Ernaehrungsansicht: JSON exportieren, Kostenbeleg
importieren, nach Bestaetigung Messdaten loeschen (nicht bei laufender Erfassung).
Keine automatische Loeschfrist; der Nutzer loescht bewusst. SwiftData-Eintraege
bleiben dabei unangetastet. Speicher-/Lesefehler werden sichtbar, ein defektes
Archiv nicht still ersetzt oder als leer exportiert. Die Messung darf keinen
bereits gelungenen Ernaehrungs-Save rueckgaengig machen.

### Bekannte und unbekannte Kosten

Die bestehende API liefert **keine Kostenquittung**. Erfolg bedeutet daher nicht
automatisch bekannte Kosten, Abbruch/Verwerfen niemals kostenlos. Der Export
enthaelt `costSummary.knownUSD`, `knownOperations` und `unknownOperations` ueber
**alle** Messlaeufe, auch nicht gespeicherte. IDs werden global dedupliziert;
`sends` bleibt fuer die Interpretation wiederholter Clientversuche erhalten.
Unbekannt ist eine Anzahl von Operationen, kein Betrag von null. Lokale unbekannte
Kosten sind nicht gleichbedeutend mit den vier serverseitigen historischen Holds.

Ein belegter Gesamtbetrag je Operations-ID kann lokal importiert werden:

```json
{
  "schemaVersion": 1,
  "costs": [{
    "operationID": "00000000-0000-0000-0000-000000000001",
    "knownUSD": 0.00825
  }]
}
```

Die Beispiel-ID muss durch eine vorhandene exportierte Operations-ID ersetzt
werden. Betrag ist USD-Modellkosten, keine Hosting-/Rechnungssumme. Import nur
fuer vorhandene IDs, nichtnegative Decimal-Werte, ohne Duplikate im Beleg;
identischer Wiederimport ist idempotent, Widersprueche werden abgewiesen.
Zusaetzliche Inhaltsfelder werden weder uebernommen noch gespeichert.
Dies ist ein **operatorseitig belegter, nicht kryptografisch verifizierter**
Abgleich. Eine automatische Belegerzeugung fehlt bewusst: Gateway-Ledgerkeys
sind abgeleitet, kein direktes UUID-Verzeichnis; Zuordnung muss ausserhalb der
App mit bestehenden Operatorbelegen erfolgen. Keine Schluessel in App/Export.
Ohne eindeutigen Beleg bleibt die Operation unbekannt. Bei mehrfach kostenpflichtig
ausgefuehrter ID muss der Beleg den gesamten Betrag abdecken, nicht nur einen Send.

## 3. Urspruenglicher Wiederverwendungsplan

Bestehendes Verhalten geprueft:

- [FoodPreset](../ios/Trainingsplan/FoodPreset.swift) speichert Name, feste
  Portionsnaehrwerte und Erstellzeit, aber keine Basismenge/Einheit/Herkunft.
- [NutritionView](../ios/Trainingsplan/NutritionView.swift) erzeugt Favoriten erst
  aus protokollierten Eintraegen; Antippen eines Favoriten protokolliert sofort.
- [Historie](../ios/Trainingsplan/NutritionHistoryView.swift) sucht Eintragsnamen
  und Notizen, nicht Produkte. Der Tagesdetail-Plusknopf oeffnet bereits
  [ReuseFoodEntryView](../ios/Trainingsplan/ReuseFoodEntryView.swift): lokale
  Faktoren 0.5/0.75/1/1.25/1.5 und explizites "Heute hinzufuegen", ohne KI.
- [BackupModels](../ios/Trainingsplan/BackupModels.swift) und
  [BackupService](../ios/Trainingsplan/BackupService.swift) exportieren/importieren
  Presets samt festen Werten; kein Basismengen-/Herkunftsvertrag vorhanden.

Damals vorgeschlagene, inzwischen lokal beauftragte Erweiterung:

1. Bestehendes `FoodPreset` additiv um optionale Basismenge, Einheit (g/ml/Stueck)
   und Herkunft erweitern; vorhandene Werte bleiben Werte dieser Basisportion.
   Legacy-Presets bleiben feste Portion mit unbekannter Herkunft, niemals erfundene
   100-g-Produkte. SwiftData-Migration zuerst mit vorhandenen Daten pruefen.
2. Eigener Produktspeicher-Zweig im vorhandenen Review: **Etikett -> pruefen ->
   Produkt speichern**, ausschliesslich Preset-Insert/Save, kein `FoodEntry` und
   keine Tagessummenaenderung. Verpackungsbasis explizit bestaetigen; aktueller
   Estimate-DTO liefert keine verlaessliche Etikett-/Basismengeninformation.
   Keine zweite KI-Pipeline noetig, Mengen-/Herkunftsangaben zunaechst manuell.
3. Herkunft sichtbar unterscheiden: bestaetigte Verpackungswerte, KI-Schaetzung,
   manuell/unbekannt. Eine bestaetigte KI-Schaetzung wird dadurch nicht zum
   Verpackungswert. Spaetere freie Wertkorrektur muss Herkunft neu klaeren.
4. Vorhandene Favoritenansicht um Produktsuche nach Namen erweitern; Auswahl
   oeffnet Mengenreview statt sofort zu protokollieren. Bestehende Legacy-
   Favoritenkompatibilitaet erhalten; den neuen Produktpfad klar unterscheiden.
5. Wiederverwendungsformular fuer Produktquelle adaptieren: Menge waehlen,
   Vorschau lokal per `Basiswert x Wunschmenge / Basismenge`. Decimal, positive
   endliche Mengen, kompatible Einheiten, keine g/ml-Umrechnung ohne Dichte;
   nur Anzeige/Eintrag runden, nie die gespeicherte Basis mehrfach skalieren.
   Erst **"Heute hinzufuegen"** erzeugt genau einen Eintrag mit Save-Rollback.
6. Optionale Backupfelder mit Legacy-Decoding und Roundtrip ergaenzen; alter
   Backupimport behaelt feste Portionen/ungeklaerte Herkunft. Herkunft fuer einen
   protokollierten Produkteintrag als eigener Snapshot erhalten, nicht per spaeter
   veraenderlichem Preset oder Freitextnotiz ableiten. Keine inhaltlichen Daten
   in Produktmessung verschieben; keine Barcode-/Cloud-/Katalogdienste.

Abnahme fuer diesen spaeteren Schritt: Produkt speichern erzeugt null Eintraege;
Wiederfinden/Mengenwechsel erzeugt null KI-Aufrufe; explizites Protokollieren
genau einen Eintrag; Basis/Quelle bleiben nachvollziehbar; Abbruch/Savefehler
und alte/neue Backups verlieren keine Daten. Umsetzung und Nachweise stehen oben.

## Lokale Verifikation

FoodAnalysisKit: Zeitaufteilung, Retry-/Review-/Operations-IDs, Savefehler und
Doppelsave, Verwerfen/Abbruch, Wiederaufnahme ohne Eingabestart, Crash-Recovery,
defektes Archiv, Kosten aller Ausgaenge, idempotenter/ungueltiger Kostenimport
und inhaltsfreier Export. Bestehende Tests fuer spaete Antworten bleiben aktiv.
Zusaetzlich EntraAuthKit-Regression und Simulator-Build der vorhandenen App,
Signing aus, DerivedData ausserhalb des Repos. Keine Geraeteinstallation.

Offen bleibt ein manueller UI-Durchlauf mit Kamera/Photos, Sheet-Wischen,
Hintergrund/Prozessbeendigung und Dateien-App auf einem Geraet. Package-Tests und
Build ersetzen diesen Plattformtest nicht. Keine Live-Analyse fuer diesen Diff.