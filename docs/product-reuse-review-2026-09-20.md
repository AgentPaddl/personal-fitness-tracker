# Produktwiederverwendung: Abschlussreview und Geraetepruefung

Stand: 2026-09-20. Aufbauend auf Messpaket `ed6a59d`. Ausschliesslich lokale
Entwicklung und synthetische Tests; keine Anmeldung, Modellaufrufe, Cloud-
oder Policyaktivierung. Keine Installation und keine Buildnummeraenderung.

## Implementierter Ablauf

- "Produkt vom Etikett" oeffnet den lokalen Editor. "Als Produkt speichern"
  verwendet denselben Editor aus einem vorhandenen KI-Review heraus.
- Bezugsmenge und Einheit (g/ml/Stueck) sind Pflicht. Die Naehrwerte gelten
  genau fuer diese Menge. KI-Werte starten als Schaetzung; Verpackungswerte
  erfordern einen ausdruecklichen Etikettabgleich. Aenderungen entwerten dessen
  Bestaetigung. Produktspeichern erstellt nur ein `FoodPreset`, keinen Eintrag.
- Namenssuche, Produktauswahl, Mengeneingabe, Vorschau und "Heute hinzufuegen"
  arbeiten lokal. Jede Vorschau und Speicherung skaliert von der unveraenderten
  Basis; kein g/ml-Wechsel. Erst der bestaetigte Save erstellt einen `FoodEntry`.
- Isolierte SwiftData-Transaktionen und der bestehende Save-Koordinator sichern
  Rollback, Retry und Doppeltipps im Produkteditor und Portionsdialog ab.
- Optionale Modell-/Backupfelder bewahren alte Presets als feste Portionen.
  Ungueltige neue Produktfelder werden vor dem Import abgewiesen. Historische
  Eintraege behalten ihre eigene Herkunft; freie Wertkorrekturen werden manuell.

## Messung

Der Review hat eine fehlende Messanbindung der lokalen Produktvorgaenge behoben.
Das vorhandene Diagnosearchiv bleibt der einzige Speicher:

- `kind`: `aiCapture`, `productCreation` oder `productReuse`. Alte Datensaetze
  ohne das optionale Feld bedeuten `aiCapture`; das Archiv bleibt Version 1.
- Produkterstellung beginnt beim Oeffnen des Editors. Wiederverwendung beginnt
  bei der ersten nichtleeren Suchaenderung oder direkt bei Produktwahl. Eine
  Suche ohne Auswahl endet beim Leeren, Wechseln des Ablaufs oder Verlassen
  unvollstaendig. Zeiten vor der ersten Eingabe werden nicht behauptet.
- `productSaved` bedeutet Produkt gespeichert, `saved` Ernaehrungseintrag
  gespeichert. Explizites Abbrechen lokaler Dialoge wird `discarded`, Wegwischen
  `incomplete`. Abbruch des KI-Produkteditors laesst den urspruenglichen
  KI-Review offen und erzeugt weder Produkt noch Eintrag.
- Eigene lokale Mess-IDs verhindern, dass Wiederverwendung einen laufenden
  KI-Vorgang beendet. Dessen Wartezeit laeuft weiter, waehrend aktive Zeit der
  lokalen Interaktion zugerechnet wird. Hintergrundzeit wird separat erfasst.
- Manuelle KI-Review-/Produktwertkorrekturen und Mengenanpassungen werden als
  Runden an Save-/Schliessgrenzen erfasst, nicht pro Taste. Erste manuelle
  Produkteingabe ist keine Korrektur. Speicherfehler lassen den Vorgang offen.
- Lokale Produktvorgaenge haben keine KI-Operationen. Bestehende KI-Operationen
  und deren bekannte/unbekannte Kosten bleiben auch bei `productSaved` erhalten.
- Keine Produktnamen, Suchtexte, Mengen, Einheiten, Naehrwerte, Herkunftswerte,
  Fotos, Fehlertexte oder Tokens in Messdatensaetzen. Nur Art, IDs, Zeiten,
  Status, Zaehler und zugeordnete Kosten. Keine automatische Uebertragung.
- Alte Sofort-Favoriten, manuelle Ernaehrungseintraege und Historienwiederverwendung
  bleiben unveraendert und ausserhalb dieser Produktmessung. Aktive Zeit ist
  keine exakte Aufmerksamkeitsmessung; Diagnose- und SwiftData-Save sind nicht
  atomar. Ein Prozessabbruch kann nur unvollstaendige Messwerte hinterlassen.

## Gezielte Verifikation

Erfolgreich am 20.09.2026, ohne erneuten Gesamtsuitenlauf:

- 62 Tests: `FoodCaptureMetricsTests`, `FoodAnalysisViewModelTests`,
  `FoodAnalysisReviewSessionTests`, `FoodProductTests` in FoodAnalysisKit.
- 6 `FoodProductPersistenceTests` im vorhandenen AppPersistence-Harness:
  Null Eintraege beim Produktsave, ein Eintrag trotz Doppelsave, Rollback,
  unveraenderte Basis bei erneuter Portionierung, alte/neue Backups und echte
  SQLite-Lightweight-Migration aus den Modellquellen von `6eac77e`.
- Simulator Debug und Device Release, jeweils unsigniert mit DerivedData
  ausserhalb des Repos. Ein SwiftUI-Typpruefungs-Timeout wurde durch Auslagern
  der Verlassen-Logik behoben. Keine Aenderung der Projektdatei erforderlich.
- Fruehere erfolgreiche Pruefungen unveraenderter Auth-/Aktivitaetsbereiche
  wurden nicht pauschal wiederholt. Builds ersetzen keinen Geraete-UI-Test.

## Nachtrag: Lokales iPhone-Update 1.0 (8)

Separater Buildauftrag nach Produktcommit `6d95cce` und vorbereitetem
Policycommit `a29ff24`. Am 20.09.2026 per reiner App-Metadatenabfrage bestaetigt:
Auf dem gekoppelten iPhone 14 Pro ist 1.0 (7) installiert. Vorhandene lokale
Bundles/Archive reichen bis Build 7; Build 8 ist damit die naechste lokale
Buildnummer. Keine Abfrage oder Reservierung bei App Store Connect.

- Nur `CURRENT_PROJECT_VERSION` in Debug/Release von 5 auf 8 angehoben und
  den lokalen Pilotvalidator samt vorhandenen Tests um Build 8 ergaenzt.
  Build 9 bleibt gesperrt. Keine Produkt-, Datenmodell- oder Policyaenderung.
- Der vorbestehende Xcode-Diff ist nach strukturiertem Plistvergleich reine
  Formatierung. Er bleibt im Arbeitsbaum und wird nicht mitcommitted.
- `Pilot.local.xcconfig`, aufgeloeste Buildsettings und das fertige Bundle
  stimmen mit den bereits geprueften Outputs in
  `infra/pilot/local/20260919/runtime-create.json` ueberein. Keine neuen
  Azure-Abfragen, Anmeldung, Provisionierung oder Modellaufrufe.
- Release mit `Pilot.xcconfig` und `PILOT_ACCEPTANCE`, ARM64 fuer iPhoneOS,
  Version 1.0 (8), Bundle-ID `com.benedikt.Trainingsplan`, Team `2SF7PV3WCD`.
  Apple-Development-Signatur; `codesign --verify --deep --strict` bestanden.
  Entitlements, Callback, Keychain-Gruppe und Profil unveraendert gegen Build 7;
  Profil gueltig bis 04.09.2027. Kein TestFlight-Verteilungsartefakt.
- 40 gezielte Buildvalidator-Tests bestanden. Die zuvor bestandenen Produkt-,
  Messungs-, Migrations- und Policytests wurden nicht pauschal wiederholt.
- Ein erster Build im Dokumente-Ordner scheiterte an vom Dateiprovider gesetzten
  Finder-Metadaten. Der erfolgreiche Build liegt deshalb im lokalen Library-
  Ordner; keine Aenderung an Signierung oder Quellcode fuer diesen Fehler.
- Nicht installiert oder gestartet. Keine persoenlichen Appdaten geoeffnet,
  exportiert oder geloescht. Live-Kontingent und privater CLI-Kontext unveraendert.

Bereitgestelltes, signiertes Bundle (ausserhalb von Git):

```text
/Users/benedikt/Library/Developer/Xcode/DerivedData/pft-iphone-update8-20260920/Build/Products/Release-iphoneos/Trainingsplan.app
```

SHA-256 des signierten App-Executables:
`7dff141ae58f500a59f84abdbcbe8983d2d9281c2cd70b9ea7dd0352d1e31b02`.
Das unvollstaendige Artefakt des ersten Versuchs im Dokumente-Ordner nicht verwenden.

## Modellfreier Geraetepruefplan (Noch Offen)

Erst nach gesonderter Installationsfreigabe; vorher persoenliches Datenbackup.
Als Update installieren, nicht zuvor deinstallieren. Flugmodus verwenden;
keine Anmeldung, Kamera, KI-Analyse oder Korrekturanfrage ausloesen.

1. **Bestand:** Nach dem Update bestaetigen, dass vorhandene Trainings-,
  Gewichts- und Ernaehrungsdaten sowie Favoriten erhalten sind.
2. **Produktspeichern:** "Produkt vom Etikett" oeffnen und das synthetische
  `Build8-Testprodukt` manuell anlegen: Basis 100 g, 200 kcal, 10 g Protein,
  20 g Kohlenhydrate, 8 g Fett; Herkunft manuell. Speichern erzeugt nur ein
  Produkt, keinen Ernaehrungseintrag und keine Aenderung der Tagessummen.
3. **Suche und Menge:** Ueber Namenssuche wiederfinden und 150 g waehlen:
  Vorschau 300 kcal, 15 g Protein, 30 g Kohlenhydrate, 12 g Fett. Abbrechen
  oder Wegwischen darf noch keinen Eintrag erzeugen; erneut auswaehlen.
4. **Protokollieren:** Bei 150 g "Heute hinzufuegen" auch rasch doppelt antippen:
  genau ein neuer Eintrag. Produkt erneut oeffnen: Basis weiterhin 100 g mit
  den urspruenglichen Werten. Dialog ohne weiteren Save schliessen.
5. **Messung:** Diagnosen exportieren und `productCreation`/`productSaved`
  von `productReuse`/`saved` unterscheiden. Lokale Vorgaenge enthalten keine
  KI-Operationen, Produktnamen, Suchtexte, Mengen oder Naehrwerte. Abbrueche
  und ein kurzer Hintergrundwechsel muessen getrennt nachvollziehbar sein.
6. **Gezielt bereinigen:** Nur den synthetischen Ernaehrungseintrag und danach
  das `Build8-Testprodukt` einzeln entfernen. Pruefen, dass persoenlicher
  Bestand und urspruengliche Tagessummen unveraendert sind; kein Reset,
  kein Gesamtloeschen und keine Backup-Wiederherstellung fuer diesen Test.

## Build-8-Geraetebefund und Messkorrektur

Build 1.0 (8) wurde anschliessend ausdruecklich als Update ohne Deinstallation
freigegeben, installiert und ueber App-Metadaten bestaetigt. Im Flugmodus mit
WLAN aus bestaetigte der Nutzer Datenerhalt, Produktspeichern ohne Eintrag,
Suche, Skalierung auf 150 g, genau einen Eintrag trotz Doppeltipp sowie die
unveraenderte 100-g-Basis. Testeintrag und Testprodukt wurden danach vom Nutzer
gezielt entfernt; urspruengliche Tagessummen und persoenlicher Bestand sind
laut seiner Sichtpruefung wiederhergestellt.

Die separat freigegebene USB-Pruefung las nur die technische Messdatei aus,
nicht die Appdatenbank oder den gesamten Container. Befund: eine Erstellung
als `incomplete`, eine Wiederverwendung als `saved`, drei als `discarded`;
9.6 Sekunden inaktive Zeit im Hintergrundtest. Keine KI-Operationen oder
Mahlzeiteninhalte. Der manuelle Export gelang, wurde aber nicht separat vom
iPhone kopiert; geprueft wurde sein zugrunde liegendes Messarchiv.

### Ursache und Lifecycle

Die lokale Erstellung startete eine Mess-ID in `localCaptureID`, praesentierte
den Editor aber ueber das separate Bool `showsProductEditor`. Der Sheet-Inhalt
las die optionale ID aus dem View-Zustand statt aus seinem Praesentationsobjekt.
Damit war bei SwiftUIs erster Sheet-Auswertung keine aktuelle ID garantiert;
der Editor konnte ohne ID speichern und den Messaufruf still ueberspringen.
Das anschliessende `onDismiss` schloss die noch offene Messung als `incomplete`.
Ein zuvor erfasstes `productSaved` haette der vorhandene Terminalstatus-Guard
nicht ueberschrieben. Die Diagnose belegt den fehlenden Erfolgsabschluss;
der konkrete optionale SwiftUI-Wert wurde auf dem Geraet nicht per Debugger
ausgelesen.

Die Korrektur bindet `.sheet(item:)`, Editor und Messung an dieselbe
`FoodProductEditorSession` mit fester ID. Der Editor haelt diese Session in
`@State`; lokale Erstellung verlangt eine Messinstanz. Die Session koordiniert
den echten isolierten SwiftData-Save und meldet `productSaved` erst nach dessen
erfolgreicher Rueckkehr. Wiederholte Saves und nachfolgendes `onDisappear`
bleiben nach Erfolg wirkungslos. Fehler lassen den Vorgang offen und erlauben
Retry; Abbrechen meldet `discarded`, unbestaetigtes Schliessen `incomplete`.
Der uebergeordnete View schliesst keine Produkterstellung mehr ueber die
Such-/Wiederverwendungs-ID. Seine Lifecycle-Sperre beruecksichtigt die Session.

Der KI-Produkteditor verwendet weiterhin die bestehende Review-ID und darf
auch ohne Instrumentierung laufen. Sein Abbruch laesst den KI-Review offen;
es wird kein neuer KI-Aufruf und keine zweite Messung angelegt. Vorhandene
Messdaten werden nicht nachtraeglich als Erfolg umgeschrieben.

### Gezielte Nachweise

- Fuenf neue AppPersistence-Tests mit echter isolierter SwiftData-Persistierung:
  Erfolg erst nach Save, feste ID auch nach Zuruecksetzen der Praesentation,
  mehrfaches Schliessen/Doppelsave ohne zweites Ergebnis, Fehler mit Rollback
  und Retry, Abbruch/Wegwischen vor oder nach Fehler, KI-Review-Kompatibilitaet.
- Elf betroffene FoodAnalysisKit-Tests bestanden: neun Messungstests und die
  beiden Produktreview-Tests mit Stub-Service, ohne Modellaufrufe.
- Debug-Simulator-Build erfolgreich. Keine allgemeine Wiederholung der bereits
  abgenommenen Produkt-, Migrations- oder Policyfunktionen.
- Der korrigierte SwiftUI-Lifecycle ist noch nicht auf dem iPhone nachgetestet.
  Nach gesonderter Installationsfreigabe genuegt eine neue synthetische
  Produkterstellung mit Save, anschliessendem Schliessen und Diagnoseexport:
  genau eine `productCreation` mit `productSaved`, keine KI-Operationen und
  kein Ernaehrungseintrag. Alte fehlerhafte Messung unveraendert lassen.

## Korrigiertes Update 1.0 (9), Noch Nicht Installiert

Messkorrektur separat als `7b4e846` committed und regulaer gepusht. Danach
installierten Build 1.0 (8) ausschliesslich ueber App-Metadaten bestaetigt;
auch lokale Bundles und Archive reichen bis Build 8. Naechste lokale Nummer
ist 9, ohne App-Store-Connect-Abfrage oder Reservierung.

Buildnummer 8 -> 9 in Debug/Release; lokale Pilotfreigabe um 9 erweitert,
unfreigegebener Build 10 bleibt gesperrt. 50 gezielte Validator-Tests bestanden.
Release/Pilot mit `PILOT_ACCEPTANCE` signiert fuer ARM64/iPhoneOS gebaut.
Bundle-Version 1.0 (9), `com.benedikt.Trainingsplan`, Team `2SF7PV3WCD`;
`codesign --verify --deep --strict` bestanden. Oeffentliche Pilotwerte gegen
die bereits geprueften lokalen Deployment-Outputs und Build 8 abgeglichen.
Entitlements, Callback, Keychain-Gruppe und Entwicklungsprofil unveraendert;
Profil weiterhin bis 04.09.2027 gueltig. Keine neue Provisionierung.

```text
/Users/benedikt/Library/Developer/Xcode/DerivedData/pft-iphone-update9-20260920/Build/Products/Release-iphoneos/Trainingsplan.app
```

SHA-256 des signierten App-Executables:
`db49de28919455fbd355b0f1d5bf9ebcaed9b5bb606d2aa707ca1985fd063895`.

Build 9 wurde nicht installiert oder gestartet. Keine persoenlichen Appdaten,
Diagnosehistorien, Cloudkonfiguration, Kontingente, Policys oder CLI-Kontexte
veraendert. Kein Modellaufruf und kein Upload. Der Buildnummercommit enthaelt
nur die zwei Versionszeilen der Projektdatei; der vorbestehende reine
Formatierungsdiff bleibt erhalten und uncommitted.