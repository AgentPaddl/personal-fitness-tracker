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

## Manueller Geraetepruefplan (Noch Offen)

Erst nach gesonderter Installationsfreigabe, vorher persoenliches Datenbackup;
synthetische Produktdaten und Flugmodus verwenden. Keine KI-Anfrage ausloesen.

1. **Suche:** Produkte nach Teilname und mit anderer Gross-/Kleinschreibung
   finden, Suche leeren, fehlenden Treffer pruefen; Tastatur und Sheet-Wechsel.
   Einen alten Favoriten auf unveraendertes Verhalten pruefen.
2. **Produktspeichern:** Testprodukt mit 100 g Basis, 120 kcal, 10 g Protein,
   15 g Kohlenhydraten und 4 g Fett anlegen. Fehlende/Nullmenge sperrt Save.
   Verpackungsherkunft erfordert Bestaetigung; Aenderung setzt diese zurueck.
   Speichern auch doppelt antippen: ein Produkt, keine Tagesbucheintraege.
3. **Mengenwahl:** 250 g ergeben 300 kcal, 25/37.5/10 g Makros. Danach 100 g
   erneut waehlen: wieder Basiswerte. Einheit bleibt g, Basis unveraendert.
   Abbrechen und Wegwischen legen nichts an. Dezimalkomma und Grenzen pruefen.
4. **Protokollieren:** "Heute hinzufuegen" doppelt antippen: genau ein Eintrag
   mit Herkunft. Neue Portion bewusst erneut speichern: genau ein weiterer
   Eintrag. App dazwischen kurz in den Hintergrund schicken.
5. **Diagnoseexport:** Dateien-Dialog samt Abbruch pruefen. `productCreation`
   endet `productSaved`, `productReuse` endet `saved`/`discarded`/`incomplete`;
   keine Operationen und keine Mahlzeiteninhalte. Hintergrundzeit getrennt.
   Aktive Messung darf nicht geloescht werden, Tagebuch beim Loeschen unveraendert.
6. **Upgrade/Backup:** Auf dem Geraet Altbestand und Beziehungen nach Upgrade
   pruefen; Backup-Roundtrip nur mit gesicherten Testdaten. Der verschachtelte
   KI-Review-Produktdialog bleibt ein zusaetzlicher UI-Test unter gesonderter
   Freigabe; sein fachlicher Ablauf ist hier mit Stub-Services getestet.