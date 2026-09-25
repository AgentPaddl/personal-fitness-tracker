# Produktwiederverwendung: Abschlussreview und Geraetepruefung

Stand: 2026-09-20. Aufbauend auf Messpaket `ed6a59d`. Ausschliesslich lokale
Entwicklung und synthetische Tests; keine Anmeldung, Modellaufrufe, Cloud-
oder Policyaktivierung. Keine Installation und keine Buildnummeraenderung.

## Pruefbare Scanner-Zwischenversion 25.09.2026

Nach gesonderter Nutzerfreigabe wird der aktuelle Scannerstand committed und
gepusht; die naechste Buildnummer und das signierte Pilotupdate werden separat
vorbereitet. Keine Installation, kein Appstart, kein Cloud-/Modellaufruf.

Der abschliessende Diffreview fand zwei konkrete Sicherheitsluecken im neuen
vertikalen Panelpfad. Gegenproben im bestehenden Test schlugen jeweils vor der
Korrektur fehl: ein Fat-Wort innerhalb von Saturated Fat konnte als Gesamtfett
gelten, und eine zusaetzliche nackte 100-g-Ueberschrift konnte neben der
Portionsbasis uebersehen werden. Beide Faelle sperren nun die betreffende
Zuordnung. Keine weiteren Parsererweiterungen ohne neuen konkreten Befund.

208 Pakettests und 13 Produktspeichertests bestanden, ein Test fuer das fehlende
IMG_1288 wurde uebersprungen. Die sechs vorhandenen Original-/JPEG-Durchlaeufe
haben weiterhin genau den unten dokumentierten Feldstatus. Simulator-Build
erfolgreich. Vorbestehende Xcode-Formatierung bleibt unveraendert und ausserhalb
der beiden Commits.

Review zeigt nil als "Offen", echte Null bleibt eine Zahl. Teilwerte sind
uebernehmbar; unbekannte Werte und Basis werden im Editor leer und ergaenzbar.
Vorhandene Werte werden nur nach expliziter Ersetzungsbestaetigung geloescht oder
ersetzt; der Name bleibt erhalten. Ungleichheiten erscheinen direkt als Hinweis
zur manuellen Pruefung. Kein automatisches Speichern, kein FoodEntry durch Scan.
Diese UI-Pfade sind im Code geprueft, aber mit dem neuen Bundle noch nicht am
Geraet bestaetigt: Teiluebernahme, manuelle Ergaenzung, Null/offen, Spaltenwechsel,
Abbruch, Ersetzungsdialog und anschliessendes ausdrueckliches Produktspeichern.

IMG_1288 und ein noch nicht zur Anpassung verwendetes unabhaengiges Etikett
bleiben offene Bildpruefungen. Weder bestandene Tests noch ein signiertes Bundle
sind eine vollstaendige Erkennungs- oder Geraeteabnahme.

## Falluebergreifender Scannerreview 25.09.2026: Zwischenstand nach Build 11

Build 11 wurde nach ausdruecklicher Freigabe als Update ueber WLAN installiert;
Zielgeraet und Version 1.0 (11) wurden danach geprueft. Dieser anschliessende
Review bereitet **kein weiteres Geraetebuild** vor. Aenderungen bleiben
uncommitted. Kein Cloud-/Modellaufruf und keine CLI-Kontextaenderung.

### Belegarten und Referenzen

Drei iPhone-Diagnosen dokumentieren zwei globale Eingabeabbrueche sowie einen
Teiltreffer. Die zuerst genannten Dateien mit Endungen 91/93/95 sind Screenshots
mit Wortrechtecken, keine unveraenderten OCR-Eingaben. Sie wurden nicht als
Originale erneut durch OCR geschickt. Neue, vom Nutzer bereitgestellte HEICs
mit Endungen 97/98/99 sind **Reproduktionsaufnahmen**, nicht dieselben frueheren
Kamera-Bytes. 97/98 zeigen abfotografierte Bildschirmetiketten, 99 eine direkte
Verpackungsaufnahme. Alle Originale bleiben ausserhalb des Repositories und
unveraendert. Temporaere Vorschauen werden nach der lokalen Sichtung entfernt.

Referenzen werden nur im Test verglichen, niemals dem Produktionsparser
uebergeben. Rohtexte und Bilder werden weder in Tests eingebettet noch exportiert.
Der bestehende AppPersistence-Harness ruft den echten App-Vision-Adapter und
den echten Parser auf; je HEIC wird zusaetzlich eine JPEG-Variante nur im Speicher
erzeugt. macOS-Vision ist kein Nachweis identischer iPhone-OCR.

| Fall / neue Datei in Downloads | Referenz | Ausgangszustand neue Aufnahme | Aktueller lokaler Stand, HEIC und JPEG |
| --- | --- | --- | --- |
| 1 / IMG_1298.heic | 100 ml; 26 kcal; Fett <0,1 g; KH 6 g; Eiweiss 0,12 g | keine Spalte: invalidInput | Basis, kcal, KH und Eiweiss korrekt; Fett bewusst offen: nonExactValue |
| 2 / IMG_1297.heic | Portion 125 g; 119 Calories; Fett 2,1 g; keine KH-/Eiweissmenge angegeben | keine Spalte: missingOrConflictingHeader | Portionsbasis und kcal korrekt; Fett fehlt; KH/Eiweiss mangels Mengenangabe offen |
| 3 / IMG_1299.HEIC | 100 g; 577 kcal; Fett 41,1 g; KH 37,4 g; Eiweiss 14,3 g | 100 g korrekt, alle Naehrwerte offen | Basis, kcal und KH korrekt; Fett/Eiweiss fehlen |

Keine falsch zugeordneten angebotenen Felder in den sechs abschliessenden
Durchlaeufen. Das ist **keine vollstaendige Erkennungsabnahme**. Der Test verlangt
die oben genannten korrekten Felder ausdruecklich, nicht bloss das Ausbleiben
falscher Werte. Bekannte Luecken bleiben sichtbar. Der Vergleich mit frueheren
iPhone-Diagnosen ist kein Vorher-/Nachher-Vergleich identischer Eingaben.

### Fortsetzung: Feldstatus und Verbleibende Ursachen

Jeweils gleicher Endstatus fuer Original und JPEG; "fehlend" bedeutet nicht null.
Die opt-in Diagnose bestaetigt die Referenzziffern auch fuer die fehlenden
Fett-/Eiweisswerte. Daraus allein folgt noch keine sichere Feldzuordnung.

| Fall | Feld | Ergebnis | Ursache / Zuordnung |
| --- | --- | --- | --- |
| 1 | Basis | korrekt | explizite 100-ml-Ueberschrift mit Doppelpunkt |
| 1 | kcal | korrekt | getrennte kJ/kcal-Token und gebogene Beschriftungs-/Wertzeile |
| 1 | KH | korrekt | beschriftete Grammzelle |
| 1 | Eiweiss | korrekt | gebogene Beschriftungs-/Wertzeile, explizite Grammangabe |
| 1 | Fett | fehlend, bewusst | lesbare Ungleichheit; nonExactValue, kein exakter speicherbarer Wert |
| 2 | Basis | korrekt | explizite serving-Masse, keine Umrechnung auf 100 g |
| 2 | kcal | korrekt | Calories ueber dem Wert, gemeinsame geneigte Beschriftungsreihe |
| 2 | Fett | fehlend | Zielzahl vorhanden, primaeres Fat-Label fehlt; siehe OCR-Grenze unten |
| 2 | KH | fehlend, korrekt offengelassen | nur Sugar-Menge sichtbar; kein Gesamt-KH-Feld |
| 2 | Eiweiss | fehlend, korrekt offengelassen | Werbehinweis ohne Eiweissmenge |
| 3 | Basis | korrekt | explizite 100-g-Ueberschrift |
| 3 | kcal | korrekt | vollstaendige Energiezeile wird nicht in die Ueberschrift erweitert |
| 3 | KH | korrekt | exakt erkannte Beschriftungsalternative; JPEG benoetigt lokalen Wortausschnitt |
| 3 | Fett | fehlend | Zahl/Grammangabe vorhanden, keine belastbare Fett-Beschriftung; missingRow |
| 3 | Eiweiss | fehlend | keine belastbare Eiweiss-Beschriftung; zusaetzlich Einheitenfragment als Ziffer erkannt; missingRow |

Bei Fall 2 liefert der begrenzte Ausschnittversuch im JPEG einen Fat-Treffer mit
Confidence 1,0, dessen Rechteck aber nur ca. 0,662 Intersection-over-Union mit
dem Ausgangswort erreicht. Der unveraenderte Uebernahmegrenzwert 0,8 sperrt ihn;
das Original liefert dort keinen unterstuetzten Beschriftungstreffer. Dies ist
eine verbleibende OCR-/Geometriegrenze, nicht eine unlesbare Fettzahl. Bei Fall 3
liefern weder Vollbild- noch lokale Beschriftungserkennung belastbare Fett- oder
Eiweisslabels. Daraus wird nicht behauptet, dass diese Aufdrucke fuer Menschen
unlesbar seien. Es bleiben echte Erkennungsdefizite; keine geratenen Aliasregeln.

Ein gesonderter lokaler Vision-Lauf mit festem deutschem/englischem
Naehrwertvokabular kann nur nichtnumerische, bisher nicht erkannte Beschriftungen
ergaenzen. Zusaetzliche Wortausschnitte sind auf 32 begrenzt und bleiben im
Speicher. Treffer benoetigen Confidence >= 0,8 und Boxueberlappung >= 0,8;
widerspruechliche Labels werden nicht uebernommen. Bereits erkannte Sugar-/Fat-
Labels werden nie umgedeutet. Zahlen und Einheiten stammen weiter ausschliesslich
aus dem primaeren unkorrigierten Lauf. Optionale OCR-Fehler verwerfen keine
primaeren Ergebnisse; keine automatische Sprachdetektion hinzugefuegt, da der
lokale Versuch keinen Zusatznutzen zeigte. Der reine Versuchscode wurde entfernt.

Die Beschriftungswiedergewinnung deckte zwischenzeitlich eine falsche KH-Zuordnung
in Fall 3 auf: aufeinanderfolgende Vision-Beobachtungen sind keine garantierte
Tabellenreihenfolge. Eine oberhalb liegende Wertzeile darf nicht ueber diese
Paarregel gebunden werden. Nachweislich flache, vollstaendige geometrische Zeilen
haben Vorrang; gekruemmte Zeilen werden separat behandelt. Beide Konflikte sind
synthetisch und anschliessend mit allen sechs Bildvarianten abgesichert.

Englische Tabellen und vertikale Portionsfelder werden ueber allgemeine
Beschriftungen, gemessene Textneigung und eindeutige Zellnachbarschaften gelesen.
Sugar/Saturates/Salt, Prozentangaben und Protein-Werbeaussagen bleiben ausgeschlossen.
Pro-100-g/ml- und Portionsspalten werden nicht vermischt. Fehlende Portionsmasse
bleibt leer; widerspruechliche Bezugsangaben sperren die Zuordnung.

Ungleichheiten werden pro Zelle als nonExactValue diagnostiziert, niemals als
exakte Null oder Grenzzahl gespeichert. Der unveraenderte Speichervertrag kennt
keine Obergrenze. Deshalb erscheint der Hinweis direkt im Review, nicht erst in
der aufgeklappten Diagnose, und verlangt manuelle Pruefung/Ergaenzung im Editor.

### Nachgewiesene Ursachen und Begrenzte Korrekturen

- Fall 1: Ein peripheres Wortrechteck endet bei Y ca. 1,00225 (JPEG ca. 1,00159).
  Ein einziger Randtoken loeste bisher die globale Eingabeablehnung aus. Der
  Adapter schneidet nun teilweise sichtbare Boxen an den Bildgrenzen ab, statt
  allgemeine Geometrie-/Confidence-Schwellen zu lockern. Vollstaendig ausserhalb
  liegende, nichtendliche oder leere Boxen werden weiterhin abgelehnt. Angeschnittene
  Zahlen und Einheiten bleiben unsicher; Anzahl begrenzter Woerter in der
  ausschliesslich fluechtigen Diagnose. Keine stillschweigend geloeschten Tokens.
- Danach belegte Fall 1 einen Doppelpunkt hinter der expliziten Bezugsangabe
  sowie ein verbundenes kJ/Zahl-Token. Satzzeichen nach Einheiten werden akzeptiert;
  der Adapter trennt am kJ/Zahl-Uebergang mit echten Vision-Substring-Boxen.
  Referenzspalte und Kohlenhydrate werden dadurch pruefbar. Energie/Eiweiss waren
  im ersten Zwischenstand trotz vorhandener Zahlen und Beschriftungen offen;
  die oben beschriebene Fortsetzung loest diese geschwungene Tabellenzuordnung.
  Fett hat eine echte Ungleichheit und darf nicht als exakter Wert erscheinen.
- Fall 2: Die neue Aufnahme reproduziert den frueheren invalidInput-Abbruch nicht.
  Bezugszahl und Zielzahlen sind im OCR-Ergebnis vorhanden. Englische
  serving/Calories-Beschriftung, fehlende exakte Fat-Beschriftung und vertikale,
  schraeg nebeneinander angeordnete Felder passen nicht zur bisherigen deutschen
  Zeilentabellenlogik. Keine erfundene Gramm-/kcal-Einheit, keine Uebernahme von
  Sugar als Kohlenhydrate und keine Ableitung einer Eiweisszahl aus einem Werbehinweis.
- Fall 3: Eine vollstaendige Energiezeile wurde durch die Nachbarschaftserweiterung
  mit der nahen Bezugsueberschrift vermischt. Eine neue synthetische Pruefung
  schlug vor der Korrektur fehl und besteht danach. Vollstaendige Zeilen werden
  nicht mehr erweitert. Das echte Foto liefert nun korrekt kcal. Die drei
  Makrozahlen sind vorhanden, ihre exakt unterstuetzten Beschriftungen fehlen
  im primaeren OCR-Lauf. Die Fortsetzung gewinnt KH als beobachtete Alternative
  zurueck. Keine unscharfen produktspezifischen Aliasregeln eingefuehrt.
- Allgemein: Beschriftete, explizit bezifferte Teilwerte einer eindeutig
  ausgerichteten einzelnen Spalte koennen ohne Header zur Pruefung erscheinen.
  Bezugsmenge UND Einheit bleiben leer und muessen im bestehenden Editor ergaenzt
  werden. Mehrspaltenhinweise, numerische ungeklaerte Header sowie widerspruechliche
  Header sperren diesen Fallback. Keine Vorgabe von 100 g oder Portionsrechnung.

### Verifikation und Noch Fehlende Gegenpruefung

- 208 FoodAnalysisKit-Tests bestanden, darunter 39 Parserfaelle inklusive alter
  portabler Fixtures, englischer Tabellen/Portionsfelder, Ungleichheiten,
  widerspruechlicher Labelalternativen und Zeilenreihenfolge-/Geometrieregressionen.
- Sechs echte Bilddurchlaeufe im opt-in Korpustest bestanden mit explizit
  geforderten Teiltreffern fuer alle drei Faelle sowie Verbot falscher Werte und
  geprueften Ablehnungsgruenden fuer die verbleibenden Luecken.
- FoodProductPersistenceTests: 14 Faelle, davon 13 bestanden und ein fehlendes
  Referenzbild uebersprungen. Scan-Produktspeichertest: kein FoodEntry, keine KI-Operation.
  Manuelle Ergaenzbarkeit wurde am Geraet angefragt, aber noch nicht bestaetigt.
- Simulator Debug erfolgreich gebaut; geaenderte Dateien ohne gemeldete Diagnostik.
- Frueheres Referenzfoto IMG_1288.HEIC liegt nicht mehr am bekannten Downloads-Pfad.
  Der bestehende opt-in HEIC/JPEG-Test blieb unveraendert und wurde ausdruecklich
  uebersprungen; ein neuer Dateipfad ist fuer die erneute Bildregression erforderlich.
- Ein weiteres, bisher nicht zur Anpassung verwendetes Etikett fehlt noch fuer
  die unabhaengige Gegenpruefung. Keine Gesamtfreigabe vor diesem Test.

Aufruf im bestehenden Harness: `PFT_LABEL_CASES` enthaelt ein JSON-Array aus
`id`, absolutem lokalem `file`, `expected` (kanonische Dezimalstrings fuer
`basis/calories/protein/carbs/fat` und `unit`) und `required` (erforderliche
Teiltreffer). Optional `expectedIssues` ordnet Feldern erwartete Reason-Rohwerte
zu. Fehlende Referenzfelder verbieten eine erfundene Zahl. Optional
`PFT_LABEL_TRACE=YES` gibt ausschliesslich Kategorien, Koordinaten und boolesche
Referenz-Praesenz aus, niemals OCR-Rohtext. Ohne explizite Faelle wird uebersprungen.

```sh
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
zsh ios/ActivitySummaryKit/Tests/AppPersistence/run-tests.sh \
  --filter FoodProductPersistenceTests.testLocalLabelCorpusWithExplicitPrivateImages
```

## Fehlerreview 25.09.2026: Echter Mehrsprachiger Etikettenfall

Build 10 wurde nach gesonderter Freigabe als Update ueber WLAN installiert.
Anschliessender Nutzerbefund: Scanner oeffnet, liefert auf mehreren Verpackungen
aber keine eindeutigen Naehrwerte. Dieser Fehlerreview basiert auf einem vom
Nutzer explizit freigegebenen Original-HEIC ausserhalb des Repositories und
dessen manuell abgelesener Referenz. Keine Produktnamen oder OCR-Rohtexte im
Reviewprotokoll; Originalbild und erkannte Texte wurden nicht exportiert.

### Nachgewiesene Verluststellen

Der unveraenderte Build-10-Adapter wurde lokal unter macOS mit Apple Vision
Revision 3/de-DE und dem echten HEIC ausgefuehrt, nicht durch simulierten
OCR-Text ersetzt. ImageIO verarbeitet EXIF-Orientierung 6 zu einem aufrechten
2250-x-3000-Bild; kein Ausschnitt und keine Perspektiventzerrung. Die Wortboxen
werden von Vision links unten nach links oben normalisiert. Alle 73 zunaechst
uebergebenen Wortrechtecke waren gueltig. Ein Orientierungsfehler ist fuer
diesen Durchlauf nicht belegt.

- Vision lieferte 94 Textbereiche und erkannte bereits alle vier Referenzzahlen.
  66 Bereiche wurden jedoch durch die Confidence-Grenze 0.5 verworfen, darunter
  alle erkannten 100-g-Angaben und die Fettbeschriftung mit Confidence 0.3.
  Folge: keine Bezugsspalte, obwohl Text und Zahlen vorhanden waren.
- Ohne diesen Filter gelangen 313 Woerter zum Parser und eine Bezugsspalte
  entsteht. Noch kein Wert: globale Zeilengruppierung trennt Zellteile bei
  unterschiedlichen Texthoehen und schraegem Druck. Energiezahl und kcal stehen
  untereinander; Fett/Einheit sowie Kohlenhydratbeschriftung/Zahl landen getrennt.
- Mehrsprachige Grammfragmente mit Schraegstrichen und kyrillischem Grammzeichen
  vor lateinischem g wurden nicht als explizite Einheit akzeptiert.
- Eine benachbarte Zuckerbeschriftung sperrte den erweiterten Bereich der hohen
  Kohlenhydratbeschriftung pauschal. Begrenzung an der jeweils naeheren anderen
  Beschriftung loest diese Sperre, ohne Zuckerwerte zu Kohlenhydraten zu machen.

### Korrektur und Ergebnis

OCR verwirft Kontext nicht mehr allein aufgrund der Confidence. Niedrige
Sicherheit wird in der lokalen Diagnose gezaehlt, nicht als Verlaesslichkeit
behauptet. Der Parser bildet eng begrenzte Zellnachbarschaften um erkannte
Beschriftungen und begrenzt sie gegen andere Naehrwert-/Ausschlussbeschriftungen.
Explizite g-/kyrillische Grammzeichen werden gleich behandelt; mg/g und andere
unklare Einheiten bleiben offen. Keine unscharfe Korrektur von Nahrungsmitteln,
Zahlen oder Beschriftungen und keine produktspezifische Erkennungsregel.

Beim Original-HEIC stimmen nun **100 g, 381 kcal, 4.9 g Fett und 71.6 g
Kohlenhydrate** mit der manuellen Referenz ueberein. Eiweiss bleibt offen:
seine Zahl ist vorhanden, aber keine unterstuetzte eindeutige Beschriftung.
Eine nur im Speicher erzeugte JPEG-Variante liefert korrekt kcal und
Kohlenhydrate; dort fehlt auch die erkannte Fettbeschriftung. Fehlende Werte
werden nicht aus der bekannten Referenz 12.7 g Eiweiss oder anderen Werten
eingesetzt. Unterschiede zwischen HEIC und JPEG sind damit nachgewiesen.

Die bestehende Uebernahme erlaubt Teilresultate, verlangt bei vorhandenen
Editorwerten weiterhin die Ersetzungsbestaetigung und setzt fehlende Felder leer.
Erst der vollstaendig gepruefte Editor darf ausdruecklich ein Produkt speichern.
Herkunft, Messabschluss, Produkt-/Eintragstrennung und Cloudpfad unveraendert.

Die aufklappbare **Lokale Erkennungsdiagnose** zeigt ausschliesslich fluechtig:
das tatsaechlich normalisierte OCR-Bild mit Wortrechtecken, Textbereiche,
Woerter, niedrige Confidence, erkannten Text und konkrete Parserablehnungen.
Neue Aufnahme und Schliessen verwerfen diese Daten. Kein Logging, Teilen,
Export, Dateischreiben, Fotospeichern oder Cloud-Fallback. Fehlende Bilddaten,
fehlende deutsche Vision-Unterstuetzung, leere OCR und fehlende Wortpositionen
werden getrennt behandelt.

### Verifikation und Noch Offene Abnahme

- 23 gezielte Parsertests bestanden, einschliesslich mehrzeiliger/gekruemmter
  Zellen, naher Zuckerzeile, bilingualer Einheiten, zweier Bezugsspalten und
  pruefbarem echtem Nullwert bei fehlender Bezugsmenge. Keine Bildgenauigkeit
  aus diesen synthetischen Tests abgeleitet.
- Ein explizit aktivierter echter Bildtest im bestehenden AppPersistence-Harness
  bestand mit Original-HEIC und fluechtigem JPEG, jeweils durch denselben
  App-OCR-Adapter und Parser. Er prueft korrekte Basis, korrekte erkannte Werte,
  offene statt erfundener Werte und Uebernehmbarkeit. Bild nicht eingebettet;
  ohne `PFT_LABEL_IMAGE_PATH` wird nur dieser Test uebersprungen. Assertions
  protokollieren weder Rohtext noch erkannte Zahlen. Aufruf mit lokalem Pfad:

  ```sh
  PFT_LABEL_IMAGE_PATH=/absoluter/pfad/zum/freigegebenen-original.heic \
  DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  zsh ios/ActivitySummaryKit/Tests/AppPersistence/run-tests.sh \
    --filter FoodProductPersistenceTests.testLocalLabelCameraPipelineWithExplicitPrivateImage
  ```

- Simulator Debug und unsigniertes Device Release erfolgreich gebaut. Keine
  erneute Auth-Gesamtsuite, kein Modellaufruf, keine Cloud-/CLI-Aenderung.
  In diesem ersten Fehlerreview blieb die Buildnummer 10; vorbestehende
  Xcode-Formatierung blieb unangetastet. Signierter Folgebuild siehe unten.
- **Noch nicht am iPhone abgenommen:** Die lokale macOS-Vision-Ausgabe belegt
  diesen Bildfall, nicht identische iOS-OCR oder echte Kameraqualitaet ueber
  verschiedene Verpackungen. Die JPEG-Variante ist keine Aufnahme durch den
  UIKit-Kameradialog. Nach separater Build-/Installationsfreigabe dasselbe
  Etikett erneut aufnehmen, Diagnose/Boxen und fehlende Felder pruefen;
  danach zweite Verpackung mit Portionsspalten, Spaltenwechsel, Abbruch und
  manuellen Ersetzungsdialog testen. Kein automatisches Produktspeichern.

### Abschlussreview fuer den Geraete-Nachtest

Der Review fand eine verbleibende Luecke: Die alleinige beste Vision-Lesart
transportierte keine Information ueber widerspruechliche Zahlenalternativen.
Der Adapter vergleicht nun die Zahlensequenzen der ersten drei angebotenen
Kandidaten. Abweichende Ziffern, Vorzeichen oder Ungleichheiten markieren
betroffene Zahlwoerter; Dezimalkomma und -punkt gelten dabei als gleich.
Beschriftungen mit niedriger Confidence bleiben weiterhin als Kontext erhalten.

Markierte Naehrwerte bleiben offen, statt als eindeutiger Wert in den Editor
zu gelangen. Eine markierte Bezugsmenge bleibt leer; andere eindeutige Werte
derselben Spalte bleiben pruefbar. Kein Ausweichen auf die andere Spalte oder
den zweitbesten Wert. Das optionale Tokenfeld `numberIsAmbiguous` erweitert den
portablen Vertrag rueckwaertskompatibel; bestehende JSON-Fixtures bleiben gueltig.
Vision-Kandidaten sind kein Vollstaendigkeits- oder Genauigkeitsnachweis: auch
eine einzige, scheinbar klare OCR-Lesart muss gegen das Etikett geprueft werden.

Drei neue gezielte Zahlensicherheitspruefungen und die bestehenden portablen
Fixtures bestanden; auch der echte HEIC/JPEG-Regressionstest bestand erneut.
Die bisherigen 23 Parserpruefungen und erfolgreichen App-/Auth-Pruefungen
wurden nicht pauschal wiederholt. Diagnose weiterhin nur per Aufklappen,
fluechtig im Scan-State, ohne Teilen/Export/Logging oder automatische Speicherung.

Reparatur und nachfolgende Buildnummer werden separat committed; keine neue
Installation in diesem Abschlussauftrag. Der erste Fehlerreviewstand war
ausdruecklich uncommitted zur Durchsicht belassen worden.

### Signiertes Update 1.0 (11), Noch Nicht Installiert

Reparaturcommit `3fa2d00a3aafa8f9bfda82e68788a2cc90f8c128` wurde regulaer
nach `origin/main` gepusht. Die anschliessende Buildvorbereitung ist getrennt:
nur zwei Projekt-Versionszeilen, lokale Pilot-Buildfreigabe samt Regression
und dieser Nachweis. Vorbestehende Xcode-Formatierung bleibt uncommitted.

Read-only-Geraeteabfrage bestaetigte weiterhin 1.0 (10). Vorhandene lokale
iPhone-Bundles und Archive enthielten hoechstens Build 10; damit ist 11 die
naechste lokal freie Nummer, keine Aussage ueber App-Store-Connect-Reservierungen.
70 gezielte Pilotkonfigurationstests bestanden; Build 12 bleibt gesperrt.
Nach der Zahlenalternativenkorrektur bestand der inkrementelle Simulator-Build;
anschliessend wurde Release 1.0 (11) fuer iPhoneOS erfolgreich signiert gebaut.
Keine pauschale Wiederholung bereits erfolgreicher Gesamtsuiten.

Bundle ausserhalb des Repositories:

```text
/Users/benedikt/Library/Developer/Xcode/DerivedData/pft-iphone-update11-20260925/Build/Products/Release-iphoneos/Trainingsplan.app
```

- Bundle-ID `com.benedikt.Trainingsplan`, arm64, Team `2SF7PV3WCD`.
- Apple-Development-Signatur mit `codesign --verify --deep --strict` bestaetigt.
- Effektive Release-Einstellungen und eingebettete API-/Entra-Werte stimmen
  mit den bereits geprueften lokalen Deploymentoutputs ueberein.
- Pilotdateien, Callback, Keychain/Entitlements und URL-/ATS-Konfiguration
  unveraendert. Profil byteidentisch zu Build 10, UUID
  `7423a2df-47ea-4cf0-be4f-7aa4bd207a98`, gueltig bis `2027-09-04T19:20:25Z`.
- Executable SHA256:
  `8e8107889705e592deb6ea333c82420b5e535c34ee9c116409759ce5996b1b95`.

Nicht installiert oder gestartet. Kein Provisionierungsupdate, keine Cloud-,
Modell- oder CLI-Kontextaenderung. Der gezielte Kameratest am iPhone bleibt
offen: derselbe Etikettenfall, fehlendes Eiweiss bzw. JPEG-Fett manuell ergaenzen,
zweite Verpackung mit Portionsspalten sowie Abbruch/Ersetzungsdialog pruefen.
Die Diagnose muss ausdruecklich aufgeklappt werden und bleibt fluechtig.

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