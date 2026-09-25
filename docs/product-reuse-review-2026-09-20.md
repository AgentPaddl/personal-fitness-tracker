# Produktwiederverwendung: Abschlussreview und Geraetepruefung

Stand: 2026-09-20. Aufbauend auf Messpaket `ed6a59d`. Ausschliesslich lokale
Entwicklung und synthetische Tests; keine Anmeldung, Modellaufrufe, Cloud-
oder Policyaktivierung. Keine Installation und keine Buildnummeraenderung.

## Nachtrag 25.09.2026: Lokaler Etikettscan V1

Implementierter Reviewstand. Im bestehenden Produkteditor fuehrt "Etikett scannen"
zu "Foto aufnehmen", lokaler Erkennung, Spaltenpruefung und "Werte uebernehmen".
Bei mehreren Bezugsspalten ist eine explizite Auswahl erforderlich. Das Foto
bleibt fuer den Vergleich in der Scanpruefung sichtbar. Abbrechen veraendert
die bisherigen Editorwerte nicht; "Manuell fortfahren" kehrt zum Editor zurueck.
Ein erfolgreich uebernommener Scan ersetzt dessen vier Naehrwerte und Basis,
einschliesslich leerer Felder bei fehlenden Werten, nicht den Produktnamen.
Bei vorhandenen Naehrwerten, Menge oder Einheit verlangt die Uebernahme zuerst
"Vorhandene Werte ersetzen?". Abbrechen dieses Dialogs laesst den Editor
unveraendert; erst "Werte ersetzen" gibt den vollstaendigen Austausch frei.
Er speichert noch nichts. Erst "Produkt speichern" schreibt ein `FoodPreset`;
kein `FoodEntry`, keine Aenderung der Tagesbilanz.

Die Herkunft nach Scan ist **manuell/unbekannt**, nicht bestaetigte Verpackung
und nicht KI. Fuer Verpackungswerte bleibt die vorhandene Herkunftswahl mit
ausdruecklichem Abgleich von Werten und Bezugsmenge erforderlich. Jede Aenderung
entwertet die Bestaetigung. Name, kcal, Eiweiss, Kohlenhydrate, Fett, Menge und
Einheit bleiben vor dem Save editierbar; fehlende Pflichtangaben sperren ihn.
Keine Schema-/Backupmigration und keine geaenderte Speicherroutine.

### Getrennte Komponenten und portable Regeln

- Kamera: bestehender `CameraCaptureView`, Berechtigung nur nach Benutzertipp;
  fehlende Hardware, Ablehnung und Einschraenkung zeigen einen lokalen Fehler,
  ohne den manuellen Produkteditor zu sperren. Kein DataScanner-Hardwarezwang.
- OCR: `FoodLabelTextRecognizer`, Apple Vision `VNRecognizeTextRequest` Revision3,
  accurate/de-DE, keine Sprachkorrektur numerischer Zeichen. Orientiertes Bild
  ueber ImageIO, maximal3000 Pixel laengste Seite; Erkennung ausserhalb des
  MainActors. Fehlende deutsche Vision-Unterstuetzung bleibt ein lokaler Fehler.
  Wortrechtecke stammen aus Vision-Substring-Bounding-Boxes, nicht aus
  gleichmaessig geschaetzten Zeichenabstaenden. Kandidaten unter0.5 Confidence
  werden verworfen; diese Schwelle ist keine Qualitaetsgarantie.
- Zuordnung: reines Foundation-Modul `FoodLabelRecognition` in FoodAnalysisKit,
  ohne Vision/UIKit/Netzwerk. Eingabe `FoodLabelText` mit `text,x,y,width,height`;
  Rechtecke auf0...1 normalisiert, Ursprung links oben. Vision-Y wird umgekehrt.
  Maximal2048 Tokens, maximal200 Zeichen pro Token; ungueltige Geometrie
  verwirft die Eingabe. Kein Plattform-OCR-Objekt ist Teil dieses Vertrags.
- Regeln V1: Zeilenabstand der Zentren hoechstens0.45 der kleineren Texthoehe;
  sortiert nachY undX. Bezugsueberschriften oberhalb der ersten Naehrwertzeile
  im Abstand unter0.22 Bildhoehen; explizite100g/ml oder pro/je-Menge bzw.
  Portion mit g/ml. Portionsmenge/-einheit ohne eindeutigen Beleg bleiben leer.
  Ueberschriften derselben X-Lage mit widerspruechlichen Mengen/Einheiten
  verwerfen die Zuordnung. Hoechstens6 Spalten, keine Standardauswahl bei mehreren.
- Zahlen werden der eindeutig naechsten Spalte zugewiesen, maximal0.15
  Bildbreiten vom Zentrum; Abstandsvorteil unter0.025 ist mehrdeutig. Doppelte
  Naehrwertzeilen oder mehrere passende Werte derselben Spalte bleiben offen.
  Bei nur einer erkannten Ueberschrift und mehreren Werten einer Naehrwertzeile
  wird diese Zeile nicht stillschweigend auf die erste Spalte reduziert.
- Dezimalkomma/-punkt und explizites0 sind erlaubt. Fehlend ist `nil`, nicht0.
  Ungleichheiten, Prozente, negative/unklare Zahlen und mehrdeutige Tausender-
  Schreibweisen wie1.234 werden nicht geraten. Einheiten muessen am Wert oder
  eindeutig in der Zeilenbeschriftung stehen; benachbarte separate Einheiten
  werden nur bei engem Abstand zugeordnet. Bestehende Wertebereiche bleiben.
- Nur kcal, keine kJ-Umrechnung. Eine separate kcal-Folgezeile muss unmittelbar
  nach einer beschrifteten kJ-Energiezeile stehen (hoechstens3 Texthoehen).
  Frei stehende kcal-Werbung ausserhalb dieses Kontexts wird nicht verwendet.
  Fettzeilen mit gesaettigten Fettsaeuren werden ausgeschlossen; Zucker/Salz/
  Ballaststoffe sind keine gesuchten Makros. Keine g/ml-Umrechnung, keine
  Portionshochrechnung, kein Ableiten fehlender Werte aus anderen Naehrwerten.

Sprachneutrale synthetische Eingabe-/Erwartungsdaten:
[nutrition-label-v1.json](../ios/FoodAnalysisKit/Tests/FoodAnalysisKitTests/Fixtures/nutrition-label-v1.json).
Dezimalwerte sind dort kanonische Strings, Fehlendes ist JSON-null. Der Swift-
Test liest dieselbe Datei; Android kann Vertrag, Regeln und Vektoren spaeter
uebernehmen. Keine Android-Implementierung, kein neues SDK und keine Paywall.

### Datenschutz und Messung

Kein Aufruf von Analyse-ViewModel, Netzwerkservice oder Cloud-Fallback im Scan.
Foto nur im fluechtigen Scan-State, kein Schreiben in Fotomediathek, Dateien,
SwiftData oder Messarchiv. OCR-Text nur waehrend der Zuordnung; Schliessen
verwirft Foto und Ergebnis. Laufende Arbeit wird beim Schliessen verworfen;
eine bereits laufende synchrone Vision-Anforderung kann noch kurz auslaufen.
Fehlertexte sind feste lokale UI-Texte, kein Logging von OCR-, Bild- oder
Produktinhalten. Nur ausdruecklich gespeicherte Produktdaten werden persistent.

Der vorhandene Editor-Messlauf bleibt waehrend des untergeordneten Scans offen.
Scan, Wiederholung und Spaltenwahl erzeugen keine neue KI-Operation. Nach
Uebernahme sind Wertkorrekturen weiterhin messbar; der explizite Produktsave
endet mit `productSaved`. Ein abgebrochener Scan beendet nicht den Editor;
Editorabbruch/-schliessen behaelt die vorhandene discarded/incomplete-Semantik.
Aus einem KI-Review geoeffnete Editoren behalten dessen vorherige KI-Operationen,
der lokale Scan fuegt ihnen keine weitere hinzu.

### Verifikation und Grenzen

- 17 synthetische Parsertests, darunter4 portable JSON-Faelle: Spalten/Portionen,
  Dezimalkomma, ml/g, kJ/kcal, fehlende Felder, explizite Auswahl, Duplikate,
  Grenzpositionen, unklare Einheiten, Prozentwerte und Wertebereichsgrenzen.
- 12 Produktpersistenztests im bestehenden SwiftData-Harness bestanden,
  einschliesslich Scan -> Produkt, null Ernaehrungseintraege, manuelle Herkunft,
  genau ein lokaler Messabschluss und null KI-Operationen. Bestehende
  Abbruch-/Doppelsave-/Rollback-/Migrationspruefungen bleiben gruen.
- Vorgeschriebene Paketregressionen:184 FoodAnalysisKit-Tests und28
  EntraAuthKit-Tests bestanden; ausschliesslich lokale Testdoubles.
- Simulator Debug und Device Release (`generic/platform=iOS`) gebaut mit
  `CODE_SIGNING_ALLOWED=NO`, DerivedData ausserhalb des Repos. Keine Installation,
  Buildnummeraenderung oder Bearbeitung der vorbestehenden Xcode-Formatierung.

Gezielter Abschlussreview am 25.09.: Der einzige konkret gefundene Fehler war
die fehlende ausdrueckliche Ersetzungsfrage fuer vorhandene Editorwerte. Behoben
durch einen Dialog mit unveraenderlichem Snapshot der gewaehlten Spalte.
Spaltenwechsel liest immer ein komplettes Spaltenergebnis; neue Aufnahmen
leeren Ergebnis und Auswahl vor der OCR. Fehlende Felder ersetzen alte Werte
durch leer, nicht durch null oder Werte einer anderen Spalte. Kein Callback
bei Scan-/Kamera-/Dialogabbruch, kein Speichern im OCR- oder Kamerapfad.
Herkunft wird erst bei bestaetigter Uebernahme manuell/unbestaetigt, der
vorhandene Messlauf endet erst am Editorabschluss. Kamera und Vision verwenden
keinen Netzwerkclient und schreiben keine Bilder/OCR-Texte in lokale Archive.

Nach dem Review nur die beiden neuen Tests fuer Spaltenwechsel (einschliesslich
null gegen fehlend) und zweite Erkennung ausgefuehrt: beide bestanden. Der
inkrementelle Simulator-Build mit Ersetzungsdialog bestand ebenfalls. Die zuvor
erfolgreichen Gesamtsuiten und Persistenzpruefungen wurden nicht pauschal
wiederholt. Die Dialogbedienung selbst ist nicht durch diese Parsertests belegt.

**Keine Abnahme echter Kameraqualitaet:** Tests liefern synthetischen OCR-Text
mit Rechtecken, keine real fotografierten Verpackungen. Reflexionen, Rundungen,
kleine Schrift, schraege Perspektive, verbundene Zellen, umgebrochene Beschriftung
und ungewoehnliche Tabellen koennen zu offenen Feldern oder falscher OCR fuehren.
Eine Portion ohne Masse/Volumen wird nicht als ein Stueck interpretiert.
Keine automatische Produkterkennung aus Werbetext oder Namensuebernahme.
V1 arbeitet konservativ; alle Werte muessen gegen das sichtbare Etikett geprueft
werden. Vollstaendige UI-/Kamera-/Lifecyclepruefung am Geraet bleibt offen.

### Kurzer Geraetepruefplan (nach separater Installationsfreigabe)

1. Im Flugmodus eine gut beleuchtete flache Verpackung mit100g-Spalte scannen.
   kcal gegen kJ, Eiweiss/Dezimalkomma und Gesamtfett gegen gesaettigte Fettsaeuren
   abgleichen; Werte bearbeiten. Herkunft bleibt ungeprueft bis zur eigenen
   Verpackungsbestaetigung, jede nachfolgende Aenderung hebt sie auf.
2. Getraenk mit100ml und Portion250ml scannen: ohne Spaltenwahl keine Uebernahme;
   beide Spalten getrennt pruefen, keine Umrechnung in g. Verpackung mit
  100g/Portion30g und RI%-Spalte ebenso pruefen.
3. Unscharfes/glitzerndes Etikett, verdeckten Makrowert, kJ ohne kcal und
   "<0,5g" pruefen: fehlende Werte nicht0, keine geschaetzten Einheiten.
   Bei Misserfolg manuell fortfahren; keine Cloudaktion anbieten/ausloesen.
4. Kamera ablehnen, Kamera abbrechen, Scan wegwischen, erneute Aufnahme sowie
   Hintergrundwechsel pruefen. Editorwerte bei Abbruch unveraendert, Messlauf
   offen bis Editorabschluss. Ohne Kamera im Simulator bleibt manuell verfuegbar.
  Vorhandene manuelle Werte und einen zweiten Scan pruefen: Ersetzungsfrage
  abbrechen laesst alles unveraendert; bestaetigen ersetzt die gesamte Basis
  samt Naehrwerten, auch wenn im zweiten Ergebnis Angaben fehlen.
5. Ein Testprodukt ausdruecklich speichern: genau ein Produkt, kein Eintrag,
   Tagessumme unveraendert; Messung `productCreation/productSaved`,0 KI-Vorgaenge,
   keine Fotos/Texte/Werte im Messarchiv. Nur das Testprodukt danach entfernen.
   Keine neue Modellanalyse, persoenlichen Daten nicht zuruecksetzen.

## Signiertes Scannerupdate 1.0 (10), Noch Nicht Installiert

Am 25.09.2026 Scanner samt Abschlussreview separat als `fc4235e` committed und
regulaer nach `origin/main` gepusht. Installierte Trainingsplan-App ausschliesslich
ueber App-Metadaten geprueft: 1.0 (9). Vorhandene lokale iPhone-Bundles und
Xcode-Archive reichen ebenfalls bis Build 9. Damit ist 10 die naechste freie
lokale Nummer; keine App-Store-Connect-Abfrage oder globale Reservierung.

- Debug/Release nur von 9 auf 10 erhoeht. Lokale Pilot-Buildfreigabe um 10
  erweitert; Build 11 bleibt gesperrt. Alle 60 gezielten Validatorfaelle bestanden.
  Keine Gateway-Laufzeit-, Cloud-, Quoten- oder Policyaenderung.
- Bestehende Pilotdatei bytegenau gegen den vorhandenen Generator und die schon
  geprueften lokalen Deploymentoutputs abgeglichen. Aufgeloeste Buildsettings
  und finale Bundlewerte stimmen damit und mit Build 9 ueberein. Keine neue
  Provisionierung, Paketaktualisierung oder Aktivierung einer anderen Umgebung.
- Release/Pilot mit `PILOT_ACCEPTANCE`, ARM64/iPhoneOS, 1.0 (10), Bundle-ID
  `com.benedikt.Trainingsplan`, Team `2SF7PV3WCD`. Apple-Development-Signatur;
  `codesign --verify --deep --strict` bestanden. Entitlements, Keychain-Gruppe
  und Callback unveraendert. Entwicklungsprofil bytegleich zu Build 9:
  `7423a2df-47ea-4cf0-be4f-7aa4bd207a98`, gueltig bis 04.09.2027 19:20:25 UTC.
  Lokales Entwicklungsupdate, kein TestFlight-Verteilungsartefakt.

App-Bundle ausserhalb von Git:

```text
/Users/benedikt/Library/Developer/Xcode/DerivedData/pft-iphone-update10-20260925/Build/Products/Release-iphoneos/Trainingsplan.app
```

SHA-256 des signierten App-Executables:
`2eee679f980368ea40488e06c819de46faed4deca22983f792c2ece9e1a97a40`.

Nicht installiert oder gestartet. Keine persoenlichen Appdaten gelesen,
exportiert oder veraendert, kein Modellaufruf und keine Aenderung am CLI-Kontext.
Die reale Kamera-/Dialogabnahme steht weiterhin aus. Der separate
Buildnummercommit umfasst die Freigabe, Tests und diesen Nachweis; aus der
Projektdatei nur die zwei Versionszeilen. Die vorbestehende Xcode-Formatierung
bleibt uncommitted erhalten.

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