# Persoenliche iPhone-Pilotabnahme

## Abschluss der zwei Build7-Geraeteversuche

Stand 2026-09-19,20:29:15 Berlin: **KI gesperrt, Grant widerrufen,
16/16 Versuche verbraucht**. Die gesunde Single-Revision `iphone7-locked`
hat `AI_API_ONLY_ENABLED=false`; ihr geladener neuer Freigabeschluessel weist
genau den zuvor ausgestellten Grant zurueck. Signaturinhalt und unveraenderte
Konfigurationsbindung wurden im laufenden Container nachgeprueft, Health200.
Keine weiteren Modellaufrufe, Retries, Verfeinerungen oder CLI-Modelltests.
Alte Produktion und Teilnehmerkreis unveraendert, keine Alltagsfreigabe.

Am iPhone wurden erhaltener Datenbestand und die erwartete Meldung
"Die KI ist fuer diesen Pilot noch nicht aktiviert." bestaetigt. Der folgende
Live-Ledgervergleich zeigte weiterhin14 Versuche und unveraenderte Altoperationen:
auch dieser Geraete-Sperrtest erzeugte keine neue Reserve. Nach App-Neustart
und Bereitschaft wurde der frische Grant erst um20:19:57 Berlin ausgestellt,
die aktive Revision um20:21:18 bestaetigt. Nominelles Ende21:19:57; tatsaechlich
nach den beiden Versuchen vorzeitig gesperrt und durch Schluesselrotation widerrufen.

| Fall | Admission (Berlin) | Geraeterueckmeldung | Ledgerkosten USD |
| --- | --- | --- | --- |
| L1 | 20:22:50 | "geklappt"; numerische Einzelwerte und Abbrechen ohne Speichern noch nicht ausdruecklich bestaetigt | 0.0015279 |
| P5 | 20:25:05 | "es liegt kein nutzbares Ergebnis vor"; kein erneuter Versuch | 0.0008877 |

Der Zwischencheck vor P5 bestaetigte genau eine neue, abgerechnete Operation
und mindestens65Sekunden seit L1-Admission. Final genau zwei neue Operationen,
beide `settled=true`, `usage_known=true`; keine aktive Ausfuehrung und kein
gesperrter Ledger. Alle14 Altoperationen einschliesslich der vier Holds sind
inhaltlich unveraendert. Die neue Lebenszeitgrenze16 und kumulative Vollreserve
USD3.7488 sind erreicht; das ist keine Istkostensumme und keine neue16er-Serie.

Die beiden neuen Ledgerzustaende `succeeded` bezeichnen abgeschlossene
Provider-/Abrechnungsschritte, **keinen fachlich erfolgreichen Review**.
Insbesondere kann der Bild-Fachpfad nach erfolgreicher strukturierter Antwort
`is_food=false` noch in den generischen Fehler laufen. Die fluechtigen Logs
der inzwischen abgeschalteten aktiven Revision waren mangels Replik nicht
mehr abrufbar. Daher ist fuer diesen P5-Aufruf die semantische Nicht-Lebensmittel-
Erkennung nicht separat belegt; der Fehlertext allein reicht dafuer nicht.
Es wurde kein Modellaufruf zur Nachweisbeschaffung wiederholt.

Abgleich der Modellkosten:

- L1 und P5 zusammen **USD0.0024156**, beide mit bekanntem Verbrauch.
- Bekannte Modellkosten insgesamt **USD0.01620465**.
- Vier unveraenderte unbekannte Alt-Holds **USD0.9372**; keine neuen Holds.
- Bekannte Kosten plus konservative Alt-Holds **USD0.95340465**.
- EUR1.35 Zusatzreserve bleibt innerhalb EUR20+5 konservativ gebunden;
   keine Freigabe des Restpuffers aus verzoegerten Abrechnungswerten ableiten.
   EUR12-Netto-Stopp, EUR18-Betriebshuelse und Periodenende unveraendert.

Der einmalige Abschlusskostenabruf erhielt429 mit10Sekunden Retry-Hinweis.
Ein einzelner lesender Folgeabruf nach Ablauf des Hinweises war um18:28:26UTC
erfolgreich: weiterhin **EUR0.0900451973209686 netto** gebucht. Dieser
nachlaufende Azurewert ist keine endgueltige Rechnung und nicht mit den
USD-Modellkosten ohne Weiteres addierbar. Keine automatische Wiederholung.
Keine temporaeren Cloudjobs mehr vorhanden; die lokale Build-VM war bereits
gestoppt. Private Grants, Schluessel, Operatorhilfen und Laufzeitbelege bleiben
im ignorierten `local/20260919/`, nicht in Git.

Abschluss-Ledgerhash:
`1f6aba267c91d85f5e8327291c541823a3075a5d3c8c70398376581b26ef502c`.
Hash aller16 Operationen:
`c7a39d1f8f9a018455db92a6f99cc88356d360ced13052dab349c39cdc3c4cb2`.

Noch zu bestaetigen, **ohne weitere Analyse**: Entsprachen die L1-Werte fuer150g
exakt300kcal,15g Protein,30g Kohlenhydraten und12g Fett, und wurde danach ohne
Speichern abgebrochen? Blieben bei P5 ein speicherbarer Review und ein neuer
Eintrag aus? Die bisherigen Kurzmeldungen belegen diese Einzelpunkte nicht
ausdruecklich. PhotosPicker/Kamera, interaktiver MSAL-Ruecksprung,
Wiederherstellung und Alltagsnutzung bleiben ausserhalb dieser Abnahme.

## Gebuendelte Vorbereitung ab main 7acda4c

Historischer Vorbereitungsstand vor dem oben dokumentierten Testfenster.
"Noch offen" und "kein Grant" beschreiben in diesem Abschnitt diesen Zeitpunkt.

Stand 2026-09-19: Der begrenzte Auftrag umfasst das private AI-off-Deployment,
das datenerhaltende Update und genau zwei neue synthetische Geraeteversuche,
**L1 und P5 je einmal**. Keine weitere Teilnehmeraufnahme und keine Aenderung
der alten Produktion. Die aelteren Freigabevorschlaege weiter unten sind
historisch und werden fuer diesen Auftrag durch diesen Abschnitt ersetzt.

Bereits ausgefuehrt:

- Der korrigierte Gateway wurde als `iphone7-off` veroeffentlicht, Image
  `sha256:dc77fba44372a476f8f2e0c4346c4d4e2a6ef4deb1e26f2dab725768e050e927`.
  Das Backendpaket mit optionaler Fehlergrundweitergabe ist veroeffentlicht.
  Ein authentifizierter AI-off-POST bestaetigte503 `pilot_unavailable` mit
  `pilot_not_activated`, unveraenderten Ledger und alle14 Operationen:
  **kein Providerdispatch und keine neue Reserve**. Der iPhone-Sichttest
  dieses Textes ist noch offen.
- Vorher direkt installierter Build6, lokale Archive1-5 und sichtbare
  TestFlight-Builds1-5 geprueft. Build **1.0 (7)** signiert gebaut, als Update
  installiert und unmittelbar vom Geraet zurueckgelesen. Signatur, Profil,
  Bundle-/Team-/Keychain-Identitaet und eingebettete Pilotwerte gegen Build6
  geprueft. Keine Deinstallation, Datenloeschung oder Backuperstellung.
  SwiftData-Modelle und Containerkonfiguration wurden nicht geaendert.
  Ein fachlicher Sichtvergleich des persoenlichen Bestands nach Build7 bleibt
  eine Geraetepruefung, keine aus Installationsmetadaten ableitbare Aussage.
- Nur der opt-in Pilotbuild zeigt **Abnahmebild > L1 / P5**. Die zwei
  freigegebenen Originale liegen lokal und im gesonderten App-Cache. Der Helfer
  akzeptiert ausschliesslich ihre eingefrorenen Originalhashes, verwendet den
  normalen `FoodImagePreprocessor` und prueft die identische Aufbereitung bei
  Auswahl. Keine Anmeldung, Analyse oder Mahlzeitenspeicherung durch Auswahl.
- Die tatsaechlichen JPEGs aus Build7 wurden offline vom iPhone zurueckgelesen
  und mit den bekannten Originalen abgeglichen. Kein Auslesen persoenlicher
  Fotos oder der SwiftData-Datenbank. Diese Abnahme prueft den echten JPEG-/
  Multipart-/Reviewpfad, **nicht** PhotosPicker, Kamera oder Fotoimport.

| Fall | SHA-256 des normalisierten Gateway-Payloads |
| --- | --- |
| L1 | `4bedc4c13dc962fa6f564a172048976caa6d9c17f120426efed21480200fa34c` |
| P5 | `a08e6f14ab67709f6fe336f455b6e0c6c2c501b877187b04c1bab231f87a8931` |

Der getestete `extend_acceptance(..., iphone_payload_sha256=...)`-Zweig erlaubt
ausschliesslich14->16 mit zwei verschiedenen neuen Hashes, AI-off, exaktem
Ledgerhash/ETag und atomarem Create-only-Audit. Alte Zaehler, Operationen, vier
Holds und monetaere Tages-/Monatsgrenzen bleiben erhalten. Die CLI-Fallfolge
bleibt bei14 beendet und kann diese Geraeteversuche nicht ausfuehren. Neue
Lebenszeitobergrenze USD3.7488, **keine neue16er-Serie**.

Die atomare Live-Erweiterung ist bestaetigt: Limit16, weiterhin14 verbrauchte
Versuche und USD3.2802 kumulative Vollreserve; alle14 Operationen und vier
Holds unveraendert. Der Auditbeleg `acceptance-extension-16-v1` wurde gemeinsam
mit der einzigen Ledgeraenderung (Policybindung) erzeugt. Die nachfolgende
Revision `iphone7-bound-off` bindet dieselben zwei Hashes und den tatsaechlichen
Image-Digest. Kein Zaehler-/Hold-Reset und kein zusaetzlicher Modellversuch.

Zwei neue Vollreserven ergeben USD0.4686, konservativ EUR0.85, zuzueglich
EUR0.50 Neben-/Abschlussreserve: **hoechstens EUR1.35 innerhalb EUR20+5**.
Nach429-Drosselungen und abgewartetem Retry-Hinweis war der einzelne lesende
Abruf um18:05:16UTC erfolgreich: gebucht EUR0.0900451973209686 netto fuer den
Pilot. Abrechnungsnachlauf bleibt offen, kein Echtzeit-Istkostendeckel. Die
bestehende EUR18-Betriebshuelse und bisherige EUR2.19-Korrekturreserve bleiben
konservativ gebunden; der ungebundene Puffer sinkt von EUR4.81 auf EUR3.46.
Alte Holds USD0.9372 und bekannte Modellkosten USD0.01378905 unveraendert.
Kein neues Budget, EUR12-Netto-Stopp und urspruengliches Periodenende bleiben.

Lokale Checks:429 Gateway-/Ledger-/Provider-/Buildvalidator-Tests,
144 Backendtests,152 FoodAnalysisKit-Tests und28 EntraAuthKit-Tests bestanden;
danach28 fokussierte Amendmentchecks inklusive vier neuer Negativfaelle fuer
doppelte/alte Bildhashes bestanden. Signierter Release-Device-Build7 erfolgreich. Der konkrete Gatewayimagescan
meldet keine Schwachstellen oder Secrets; bekannte Scannergrenzen aus dem
Deploymentbericht bleiben bestehen. Kein interaktiver iPhone-Abnahmenachweis
wird daraus abgeleitet. **KI bleibt aus, kein neuer Grant und kein laufendes
Abnahmefenster.**

Die live nachgepruefte Revision `iphone7-bound-off` ist gesund, Image-/Policy-
Bindung stimmen. Neun Authpruefungen, sechs Eingangsgrenzen, fremde Workload-
Abweisung, Table-RBAC und isolierte modellfreie Ledgerchecks bestanden; deren
Testpartition wurde entfernt. Der echte Pilotledger blieb dabei unveraendert.
Die erneute Snapshotpruefung bestaetigt14 Versuche, active0, blockedfalse,
vier Holds und identische14 Altoperationen. Operationshash:
`bc9eb34b657e573163b2cf9ed38e0a20952d50c7bad43580fb2ad8832a88b110`.
Der neue Ledgerhash nach ausschliesslicher Policybindung lautet
`7c47330d4b20428732baf4aa1227f5a7978f56c17b7708da6303c062eeb9e043`.

### Konkreter Geraeteablauf

1. Bestehende Daten nur ansehen und auf unveraenderten Bestand pruefen.
2. Solange KI aus: **Ernaehrung > Abnahmebild > L1 > Analysieren** einmal.
   Erwartet: "Die KI ist fuer diesen Pilot noch nicht aktiviert."
   Kein Review/Eintrag. Bei Anmeldung nur das bestehende eigene Konto nutzen.
   Silent-Login ist kein Nachweis eines interaktiven MSAL-Ruecksprungs.
3. Danach die App vollstaendig schliessen und neu oeffnen. Die Sperrantwort
   deaktiviert weitere Analysen im laufenden ViewModel absichtlich; kein Retry
   und keine Ersatzberechnung. **Abnahmebild > L1** erneut auswaehlen, noch
   nicht analysieren. Erst bei tatsaechlicher Testbereitschaft wird der frische
   gebundene Grant fuer hoechstens eine Stunde ausgestellt.
4. Nach bestaetigter Aktivierung L1 genau einmal analysieren. Die vorgegebene
   Beschreibung nennt150g. Review erwartet300kcal,15g Protein,30g Kohlenhydrate,
   12g Fett. Werte/Unsicherheit ansehen, dann **Abbrechen**, nicht Uebernehmen
   und nicht verfeinern. Kein neuer Eintrag.
5. Nach Ledgerabgleich und mindestens65Sekunden seit Admission P5 auswaehlen
   und genau einmal analysieren. Kein speicherbarer Review und kein neuer
   Eintrag. Der bekannte generische Fehlertext bleibt ein UX-Mangel; daraus
   keine allgemeine semantische Refusal-Abnahme ableiten. Weder Retry noch
   neue Berechnung bestaetigen.
6. Bei429, Timeout, unklarem Ausgang oder Abbruch keine Wiederholung. Nach
   maximal zwei Versuchen oder Abbruch sofort KI sperren, Grant widerrufen,
   alte und neue Operationen/Kosten getrennt abgleichen. Keine Alt-Holds
   aufloesen und keinen persoenlichen Eintrag loeschen.

L1/P5-Liveergebnisse, anschliessender Widerruf und finaler Kostenabgleich sind
**noch nicht ausgefuehrt**. Private Geraete-/Deployment-/Ledgerbelege bleiben
unter dem ignorierten `local/20260919/`; keine Einwilligungsdaten oder Secrets
werden durch diesen Bericht veroeffentlicht.

## Historie ab cba6ee4

Die folgenden Abschnitte erhalten den frueheren Vorbereitungsstand. Alte
Formulierungen "noch nicht genehmigt" oder "Build6" beschreiben nicht den
oben dokumentierten Build7-Auftrag.

## Bestaetigter Folgestand

Nach der unten erhaltenen Vorbereitung wurde das signierte Pilot-Bundle als
Update unter unveraenderter App-/Team-/Keychain-Identitaet installiert. Direkte
Geraeteabfragen bestaetigten zuvor **1.0 (5)** und danach **1.0 (6)**. Keine
Deinstallation, Datenloeschung oder TestFlight-Verteilung. Die privaten
Installations- und Versionsbelege bleiben ausschliesslich unter `local/`.

Der zeitlich passende Pilot-Gatewayeintrag vom 19.09. um **18:51:15 Berlin**
zeigt HTTP503 an `boundary=release`, vor Ledger-Zulassung und Providerdispatch.
Die KI blieb aus. Der anschliessende lesende Hashvergleich bestaetigte den
unveraenderten Ledger und alle14 Operationen: kein neuer Versuch, keine neue
Reserve, vier Holds ueber USD0.9372 und keine aktive Ausfuehrung. Eine vom
iPhone gelesene Request-ID fehlt; die Geraetezuordnung ist zeitlich, nicht
ueber protokollierten Eingabetext belegt.

Dies schliesst Stufe A nicht vollstaendig ab: Ein fachlicher Vorher-/Nachher-
Datenvergleich, Sicherungs-/Restore-Nachweis und interaktiver MSAL-Ruecksprung
sind damit nicht nachgewiesen. Build6 enthaelt weiterhin den generischen
Sicherheitstext. Der unten beschriebene neue Fehlervertrag ist nur lokal
implementiert, weder ausgerollt noch auf dem iPhone installiert.

## Historischer Vorbereitungsstand: nur Updatevorbereitung

Auftrag vom 19.09.2026: einmaliger lesender Kostenabruf und lokale Build-/
Updatevorbereitung, **keine Installation, kein Upload, keine Analyseanfrage**.
KI bleibt aus, Versuchslimit bleibt **14**, keine neuen Ressourcen oder
Teilnehmer. Stufe B weiter unten bleibt ein nicht freigegebener Zukunftsentwurf;
weder eine 14->16-Aenderung noch eine neue Kostenreserve wird jetzt umgesetzt.

Lokale Xcode-Archive: Version **1.0**, Builds **1, 2, 3, 4, 5**, letztes Archiv
vom **08.09.2026, 13:53:58 UTC**. Alle verwenden
`com.benedikt.Trainingsplan` und Team `2SF7PV3WCD`, ebenso der aktuelle
Projektstand mit Build **5**. Der Betreiber bestaetigte auf Rueckfrage
**Version 1.0, hoechster TestFlight-Build 5**. Damit ist **6 der naechste freie
Buildwert nach diesem bestaetigten Stand**; kein serverseitig reservierter Wert.
Der eigene Browserzugriff endete an der App-Store-Connect-Anmeldung, also kein
automatisierter Servernachweis. Vor einer spaeteren Verteilung erneut auf
zwischenzeitliche Builds achten. Kein Upload erfolgt.

Das eine gekoppelte iPhone war beim lesenden `devicectl list devices` nicht
verbunden (hinterlegtes iOS 26.6.2). Seine aktuell installierte App-Version und
Installationsquelle sind **noch offen**; die entsprechende Rueckfrage blieb
unbeantwortet. TestFlight-Bestand, lokales Archiv und installierte App sind drei
verschiedene Nachweise. Vor dem Update am Geraet bestaetigen, nicht raten.

### Lokal gepruefter Build 6

- Release fuer `generic/platform=iOS`, Version **1.0 (6)**, ARM64, mindestens
   iOS 26.5. Lokal erfolgreich signiert; `codesign --verify --deep --strict`
   bestanden. Weder installiert noch gestartet oder hochgeladen.
- Bundle-ID `com.benedikt.Trainingsplan`, Team `2SF7PV3WCD`, vollstaendige App-ID
   `2SF7PV3WCD.com.benedikt.Trainingsplan`, Keychain-Gruppe
   `2SF7PV3WCD.com.microsoft.adalcache` unveraendert gegenueber Archiv 5.
   Vorhandenes Entwicklungsprofil umfasst das gekoppelte Geraet und ist bis
   04.09.2027 gueltig; keine neue Provisionierung. `get-task-allow=true` passt
   zum lokalen Entwicklungsweg, ist kein TestFlight-Verteilungsartefakt.
- `Pilot.local.xcconfig` stimmt exakt mit den geprueften Outputs aus
   `local/20260919/runtime-create.json` ueberein. API-URL, Tenant, Client, Scope
   und Callback wurden auch in aufgeloesten Buildsettings geprueft; keine
   Provider-/Gatewayzugangsdaten im Client und keine Produktionskonfigurationsaenderung.
- Der erste Build scheiterte, weil `validate_pilot.py` nur Build 5 erlaubte.
   Eng begrenzte Korrektur: nur die geprueften Builds **5 oder 6** zulassen;
   Release, Bundle, Team und Deploymentpruefungen unveraendert. Projektwert
   bleibt 5, dieser Build setzt ausschliesslich `CURRENT_PROJECT_VERSION=6`.
   Keine SwiftData-/Runtimeaenderung und keine Aenderung am Modelllimit.
- **146 FoodAnalysisKit + 28 EntraAuthKit + 20 Buildvalidator + 2 AI-off-Ingress-
   Tests bestanden**; der korrigierte Release-Build ohne gemeldete Warnung/Fehler.
   Diese lokalen Tests sind kein physischer Daten-/MSAL-Abnahmenachweis.

Lokales Artefakt (nicht in Git, nicht hochgeladen):
`/private/tmp/pft-iphone-preparation-njb4iktc/DerivedData/Build/Products/Release-iphoneos/Trainingsplan.app`.
Private Build-/Signaturbelege: `local/20260919/update-build6-*.json`.
Der temporaere Buildpfad kann vom System bereinigt werden; dann mit dem unten
festgehaltenen Aufruf erneut lokal bauen, nicht eine andere App installieren.

### Kurzer Geraetepruefplan, erst nach Installationsfreigabe

| Schritt | Erwartung / Stoppkriterium |
| --- | --- |
| Vorher | Installierte Version/Build und Quelle am iPhone bestaetigen; exportierte Daten lokal geschuetzt und Finder-Backup verschluesselt sichern. Anzahl und Stichproben von Mahlzeiten, Favoriten, Gewichten, Aktivitaeten, Workouts und Zielen privat festhalten. Kein Import, kein Loeschen. |
| Update | Nur den unten empfohlenen Xcode-In-place-Weg verwenden. Identische App-ID/Team/Keychain-Gruppe; bei Installationskonflikt stoppen statt deinstallieren. |
| Nachher | Dieselben Daten und Zuordnungen vergleichen, keine leere/neue Datenbank akzeptieren. App schliessen und erneut oeffnen; keine Testeintraege oder Wiederherstellung erforderlich. |
| Anmeldung/Rueckkehr | Erst nach separater Geraetetesterlaubnis synthetischen Text verwenden. Eigene Microsoft-Anmeldung abbrechen: kein Analyseversand. Bewusst erneut anmelden: Rueckkehr in dieselbe App, Eingabe bleibt erhalten, hoechstens ein anschliessender POST. Silent-Login beweist keinen interaktiven Ruecksprung; kein Cache-Reset ohne Freigabe. |
| KI aus | Bei korrekter Identitaet/erreichbarem Dienst erwartet: **503 `pilot_unavailable`**, kein Review und kein neuer Eintrag. Keine Wiederholungsaktion bestaetigen; Zaehler und Limit bleiben **14**, keine Modellaufrufe. 401/403/Timeout/anderer503 sind keine bestandene AI-off-Pruefung. |

Tatsaechlicher Nutzertext fuer diesen AI-off-Code (HTML-Entitaeten nur fuer die
ASCII-Quelldatei, inhaltlich unveraendert):

> Die Anfrage konnte nicht sicher best&auml;tigt werden. Beim KI-Anbieter k&ouml;nnte bereits Verbrauch entstanden sein.

Der Text ist generisch und nennt die absichtliche KI-Sperre nicht. Beim
geprueften deaktivierten Ingress wird jedoch **vor Ledger/Modellversand**
abgewiesen. Das ist durch Code und zwei lokale Tests belegt, nicht durch einen
neuen Live-POST. Eine separate, generische503-Abbildung kann stattdessen
"Der Analysedienst ist nicht erreichbar. Der Ausgang dieser Anfrage ist unklar."
anzeigen; diese Meldung alleine belegt den erwarteten Sperrpfad nicht.
**In dieser Vorbereitungsphase wurde kein synthetischer Analyse-POST gesendet.**

### Fehlervertrag: explizite Aktivierungssperre, noch nicht ausgerollt

Noch nicht ausgerollt oder auf dem iPhone installiert: Der authentifizierte
Gateway-Ingress liefert ausschliesslich bei `AI_API_ONLY_ENABLED=false` vor
Ledger-Zulassung und Providerdispatch weiterhin HTTP503 `pilot_unavailable`,
zusaetzlich `error.reason=pilot_not_activated`. Backend und iOS akzeptieren nur
diese genaue Status-/Code-/Grundkombination. Alte Clients ignorieren das neue
optionale Feld und behalten ihr konservatives Verhalten.

Neuer iOS-Text: "Die KI ist f&uuml;r diesen Pilot noch nicht aktiviert."
Dieser Zustand bietet keine Wiederholung oder Ersatzberechnung an. Andere
503-Antworten, fehlende/unbekannte Gruende und Timeouts behalten die bisherigen
Sicherheitshinweise. Eine bereits zuvor unklare Operation bleibt auch nach einer
spaeteren Sperrantwort als unklar markiert und erhaelt weiterhin einen Hinweis.
Der Grund bestaetigt nur die Ablehnung dieser Anfrage, nicht Kostenfreiheit
frueherer Versuche oder des Hostings. Build 6 und laufender Pilot unveraendert.

Gebuchte Benchmark-/Pilotkosten aus genau einem neuen lesenden Abruf stehen im
[Kostenstand der Updatevorbereitung](DEPLOYMENT-2026-09-19.md#update-preparation-posted-cost-read-2026-09-19).

## Gates nach Art statt pauschaler Blockerliste

| Gate | Verifizierter Stand / erforderlicher Nachweis |
| --- | --- |
| Finanzielle Holds | Vier historische unbekannte Verbraeuche, je USD0.2343, zusammen USD0.9372 bleiben voll reserviert. Kein Nachweis fuer Nullkosten, keine Freigabe durch Zeitablauf oder aggregierte Metriken. Finanzielle Klaerung ist kein Selbstzweck-Gate fuer einen sonst gedeckten synthetischen Smoke. |
| Offene Ausfuehrungssperre | Gesicherter Abschlussbeleg vom 19.09., 15:39:08 UTC: `active=0`, `blocked=false`, alle 14 Operationen erhalten. Die vier abgeschlossenen 429-Antworten belegen keine noch laufenden Slots. Hier nur lokal erneut geprueft, kein aktueller Live-Readback. Vor spaeterer Freigabe erneut modellfrei bestaetigen. |
| Absichtliche Sperren | KI aus, Schluessel widerrufen, 14/14 Versuche verbraucht. Kein weiterer Aufruf aus Restbudget oder einem neuen Kalendertag. Eine neue Freigabe, getestete monotone Erweiterung und frische konfigurationsgebundene Nachweise sind zwingend. |
| Geraete-/Datensicherheit | Installierte Identitaet/Signierung, lokale Sicherung, Datenerhalt, echter MSAL-Ruecksprung, Review/Speichern und Refusal auf diesem iPhone noch offen. |
| Echte Teilnehmerdaten | Vollstaendige Teilnehmerinformation, eigene Entscheidung, Rechtsgrundlagen-/DSFA-Einordnung, Retentions-/Transferfragen und wirksamer Widerrufsweg offen. Ein synthetischer Owner-Smoke ist keine Freigabe echter Gesundheitsdaten. |
| Refusal-Verstaendlichkeit | Sicherheitsverhalten lokal belegt; semantischer Nicht-Lebensmittel-Text fehlt. Vor gewoehnlicher Nutzung beheben oder als konkreten Restmangel entscheiden, nicht als bereits abgenommene Refusal-UI ausweisen. |
| Breitere Qualitaet/Last | Repraesentative Foto-/Last-/p95-Pruefungen spaeter vor Ausweitung, nicht Voraussetzung fuer zwei sequenzielle synthetische Aufrufe. Kein konkretes davon abhaengiges Sicherheitsleck belegt. Authentifizierung, Zaehler-/Hold-Erhalt, fehlender Auto-Retry und fehlendes Auto-Speichern bleiben sofortige Gates. |

Letzter Kostenstand: bekannt USD0.01378905 plus Holds USD0.9372 = USD0.95098905.
Lebenszeit-Vollreserven USD3.2802 sind nicht Ist-Kosten. Budget EUR20+5,
EUR12 kumulativer Netto-Stopp und Ende 18.10.2026 22:19:10 UTC bleiben bestehen.
AI-off beendet insbesondere ACR-/Hostingkosten nicht. Taegliche Kostenpruefung,
Diagnostikloeschung nach 7 Tagen und Vorgangspflege nach 31 Tagen bleiben
Betreiberpflichten mit begruendeten Accounting-Ausnahmen.

## Tatsachlicher P5-Pfad und Nutzertext

1. Provider200 mit `is_food=false, estimate=null`; Gateway verwirft den
   Mahlzeitenentwurf und liefert502 `provider_output_invalid`.
2. [Backend](../../backend/gateway_client.py) normalisiert dies zu502
   `gateway_upstream_error`. Der private semantische Diagnoseeintrag wird
   nicht an das iPhone uebermittelt. Kein `estimate` wird weitergegeben.
3. [iOS-Service](../../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodAnalysisService.swift)
   behandelt den Nicht-2xx-Status vor einer Ergebnisdekodierung als
   `.analysisFailed`. Ein eventuell beigefuegtes `estimate` wird nicht genutzt.
4. Tatsaechlicher [Nutzertext](../../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodAnalysisError.swift):

   > Es liegt kein nutzbares Ergebnis vor. Ob beim KI-Anbieter Verbrauch entstanden ist, ist unklar.

5. [ViewModel](../../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodAnalysisViewModel.swift)
   erzeugt keinen Review; bei einem Ersatzversuch wird ein alter Review vorher
   geschlossen. Fehler fuellen auch nicht das getrennte manuelle Formular.
   [Speichern](../../ios/Trainingsplan/FoodAnalysisReviewView.swift) setzt einen
   gueltigen Review und den bewussten Uebernehmen-Schritt voraus.
6. Die [Ansicht](../../ios/Trainingsplan/NutritionView.swift) bietet dennoch
   "Dieselbe Anfrage erneut senden" und "Neue Berechnung" (jeweils mit
   Bestaetigungsdialog) an. Keine automatische Wiederholung. Ein expliziter
   Retry verwendet dieselbe Vorgangs-ID; der aktivierte Pilot-Replayschutz
   verweigert einen schon angenommenen Vorgang. Eine bestaetigte neue Berechnung
   ist dagegen ein neuer kostenpflichtiger Versuch und im Smoke nicht erlaubt.

**Bewertung:** Fail-closed fuer Mahlzeitenspeicherung, aber keine gelungene
semantische Refusal-UI. Der Text unterscheidet Nicht-Lebensmittel nicht von
einer technischen Stoerung und ist fuer P5 unnoetig unklar: der Providerverbrauch
war hier bekannt. Ein generisches502 darf dennoch nicht als "kein Lebensmittel"
umetikettiert werden. Fuer eine spaetere UI-Korrektur braucht es ein eigenes,
domainbezogenes und durch Backend/iOS validiertes Refusal-Signal; generische
502/Transportfehler muessen getrennt bleiben. Zieltext z.B. "Kein Lebensmittel
erkannt. Es wurde kein Mahlzeiteneintrag erstellt. Du kannst die Eingabe manuell
erfassen." Dies ist ein Vorschlag, keine hier implementierte Vertragsaenderung.

Lokale Belege ersetzen keinen Sichttest auf dem iPhone: vorhandener Swift-Test
`testRefusedHTTPResponseNeverOpensAReviewOrRetries` prueft502 sogar mit
beigefuegtem Schein-Estimate, nil-Review und genau einen HTTP-Aufruf. Andere
vorhandene Tests pruefen Save-once, Rollback, Review-Abbruch, spaete Antworten,
unveraenderte Retry-ID und EXIF/GPS-Entfernung. In dieser Vorbereitung wurden
89 ausgewaehlte FoodAnalysisKit-Tests und alle 28 EntraAuthKit-Tests erfolgreich
ausgefuehrt. Kein Modell und keine physische Geraeteabnahme.

## Stufe A: datenerhaltendes Update, KI bleibt aus

**Vorgeschlagene separate Freigabe A:** genau das eigene vorhandene iPhone,
lokaler signierter In-place-Update und synthetische Anmeldung/AI-off-Pruefung;
**0 Modellaufrufe, USD0 Modellreserve**. Keine TestFlight-/App-Store-Verteilung,
kein anderer Teilnehmer, keine Wiederherstellung oder Deinstallation. Azure-
Authentifizierung/HTTP-Hosting kann kleine Betriebskosten verursachen und bleibt
in der vorhandenen Betriebsreserve; bei unzureichender Reserve stoppen.

1. Besitzer prueft am Geraet die bisher installierte App, Version/Build,
   Bundle-/Signierungsidentitaet und iOS-Version. Sollidentitaet aus dem Projekt:
   `com.benedikt.Trainingsplan`, Team `2SF7PV3WCD`; vorbereiteter Build **1.0 (6)**.
   Das beweist nicht den installierten Stand. App-ID-Prefix, Keychain-Gruppen,
   Profil und Entitlements vergleichen; Abweichung bedeutet Stopp, nicht
   Neuinstallation unter anderem Bundle oder Loeschung der vorhandenen App.
2. In der vorhandenen App unter "Ziele" > "Backup exportieren" sichern.
   JSON nur lokal/geschuetzt ablegen, zusaetzlich ein verschluesseltes lokales
   Finder-Geraetebackup mit bekanntem Wiederherstellungsweg. Kein iCloud-/Chat-/
   Repository-Upload dieser Gesundheitsdaten. Backupdatei auf Lesbarkeit und
   vollstaendige Kategorien pruefen, Hash privat protokollieren. Ein Export
   allein ist kein bereits erprobter Restore.
3. Vorher-Protokoll: Mahlzeiten, Favoriten, Gewichte, Aktivitaeten, Uebungen,
   Workouts inklusive Saetzen/Zuordnungen und Ziele; Anzahl und relevante
   Werte/Datumsbeziehungen lokal vergleichen. Keine Rohdaten/Screenshots in Git.
   **Nicht "Backup importieren"/"Aktuelle Daten ersetzen" testen:** der
   vorhandene Import loescht den aktuellen Bestand vor der Wiederherstellung.
4. Dieselbe App aus demselben Projekt bauen, SwiftData-Modelle/Store und
   Bundle-/Teamidentitaet unveraendert. Nur der einmalige Pilotbuild verwendet
   [ios/Config/Pilot.xcconfig](../../ios/Config/Pilot.xcconfig) und die schon
   vorhandene ignorierte lokale Konfiguration. Private Pilot-API, Tenant,
   Client und Scope aus vorhandenen Nachweisen vergleichen. Kein Default-
   Produktionsendpoint, kein Entwicklungs-Authbypass, keine Tokens im Build.
   Der Callback muss `msauth.com.benedikt.Trainingsplan://auth` bleiben.
5. Der lokale signierte Build ist bereits vorbereitet, die Installation nicht.
   Keine neue Apple-Provisionierung automatisch erlauben, kein
   `-allowProvisioningUpdates`, kein Archiv-Upload. Verwendeter Buildaufruf aus
   dem Repository, bei notwendigem Neubau mit geschuetztem DerivedData-Pfad:

   ```sh
   DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild \
     -project ios/Trainingsplan.xcodeproj -scheme Trainingsplan \
     -configuration Release -xcconfig ios/Config/Pilot.xcconfig \
   -destination 'generic/platform=iOS' \
   -derivedDataPath '<GESCHUETZTES_BUILDVERZEICHNIS_AUSSERHALB_GIT>' \
   -onlyUsePackageVersionsFromResolvedFile CURRENT_PROJECT_VERSION=6 build
   ```

6. **Einziger empfohlener Installationsweg, erst nach Freigabe:** iPhone per USB
   verbinden/entsperren; vorhandene Kopplung und ggf. Entwicklermodus am Geraet
   bestaetigen. In Xcode **Window > Devices and Simulators > eigenes iPhone >
   Installed Apps > `+`** das oben gepruefte `.app` als Update auswaehlen.
   Bei neu gebautem Artefakt vorher Signatur/Profil/Pilotwerte erneut pruefen.
   **Nicht** vorher `-`, "App loeschen", "Download/Replace Container" oder
   einen Backupimport verwenden. Kein Product > Run mit abweichender Default-
   Konfiguration, kein TestFlight-/App-Store-Upload als zweiter Weg. Verweigert
   iOS das In-place-Update, stoppen. Installation ist noch nicht erfolgt.
7. Zuerst ohne Analyse starten und alle Vorher-Werte wieder vergleichen,
   erneut exportieren und fachliche Inhalte vergleichen (Exportzeit und
   nicht garantierte Reihenfolge ignorieren). Keine Migration oder leere
   Datenbank akzeptieren. Bei Differenz App schliessen, Bestand/Backups erhalten,
   keine automatische Rueckspielung. Rollback nur nach eigener Restore-/
   Updatefreigabe unter gleicher Identitaet; KI bleibt aus.
8. Vorhandene Daten nur lesen und vergleichen, keine Testmahlzeit anlegen oder
   loeschen. Kein Backupimport, keine Fotos oder Gesundheitsdaten uebertragen.
9. KI-Sperre separat modellfrei bestaetigen; dann mit synthetischem Text die
   Anmeldung starten. Wenn interaktiv: einmal abbrechen (kein Analyseversand),
   dann bewusst erneut starten und nur eigenes Konto anmelden. Bei Silent-Login
   ist der interaktive Ruecksprung **nicht** bewiesen; gezielte Cache-/Sitzungs-
   massnahme separat freigeben, nicht Tagebuchdaten/App loeschen.
10. Wechsel zur Microsoft-Anmeldung und Rueckkehr in dieselbe App beobachten:
    kein falsches Abbrechen nur durch den Auth-Wechsel, Eingabesnapshot bleibt
    gleich, hoechstens ein anschliessender Analyse-POST. Bei ausdruecklichem
    Abbruch keine spaete automatische Sendung. AI-off muss einen normalisierten
   Fehler `503 pilot_unavailable` ohne Review/Eintrag ergeben und den
   Modellzaehler bei14 belassen. Den oben dokumentierten generischen Nutzertext
   nicht als Beweis eines Provideraufrufs werten.

Freigabe A prueft nicht die echten erfolgreichen/abgewiesenen KI-Antworten auf
dem Geraet. Bildschirmverhalten und Kontozuordnung nur als bestanden markieren,
wenn tatsaechlich beobachtet; Mock-Login ist kein echter MSAL-Ruecksprung.

## Stufe B: kleinster vorgeschlagener Live-Smoke

**Separate Freigabe B erforderlich, jetzt nicht erteilt:** maximal **2 neue
Modellaufrufe**, bei normalem Ablauf genau einer pro Fall. Kein Diagnose-Warmup,
keine Neuberechnung, kein Modell-Retry, kein Wechsel zu Copilot. Bei Fehler/
Unklarheit abbrechen, nicht zwei erfolgreiche Ergebnisse erzwingen.

| Reihenfolge | Einmalige Eingabe | Sichtbare Abnahme und Modellzahl |
| --- | --- | --- |
| 1 | Synthetisches L1-Etikett aus dem bestehenden Manifest, durch den echten iPhone-Bildpfad | Genau 1 Aufruf. Erwartet: 300 kcal, 15 g Protein, 30 g Kohlenhydrate, 12 g Fett; Review zeigt Werte/Unsicherheit, Bestand unveraendert bis Bestaetigung. Werte manuell editieren, bewusst einmal uebernehmen; auch bei raschem Doppeltippen genau 1 neuer Testeintrag. App neu oeffnen und Bestand pruefen. Keine Refinement-Anfrage. |
| 2 | Synthetisches P5-Nicht-Lebensmittel, durch denselben Pfad | Genau1 Aufruf. Provider200/non-food und Gateway/Backend502 privat korrelieren; Text und angebotene Aktionen auf dem iPhone beurteilen. Kein Review, kein neuer Mahlzeiteneintrag, kein alter Entwurf uebernehmbar, kein automatischer Retry nach Warten/App-Wechsel. Keinen Retry-/Neue-Berechnung-Dialog bestaetigen. |

Ein erfolgreicher Review-Abbruch samt danach erneutem Live-Speichern wuerde in
der aktuellen App einen weiteren erfolgreichen Modellaufruf benoetigen; das
gehoert **nicht** in diesen minimalen Zwei-Fall-Smoke. Review-Abbruch/Rollback
bleiben fuer diese Stufe durch lokale deterministische Tests belegt, nicht als
physischer Live-Test ausgegeben. Ein spaeter verlangter solcher Geraetenachweis
braucht einen zusaetzlichen freigegebenen Test oder einen gesondert geprueften
modellfreien UI-Testweg; es gibt keinen hier eingerichteten Replay-/Bypassmodus.

Vor Freigabe B sind neben bestandener Stufe A zwingend erforderlich:

- Die vorhandenen Grenzen erlauben nur14; `extend_acceptance` kann ausschliesslich
  den schon verbrauchten Schritt10->14. Nicht nochmals aufrufen. Ein neuer,
  eng begrenzter, getesteter Schritt14->16 muss erst implementiert/reviewt werden:
  AI-off, exakte Hashes/ETag, keine aktiven Slots, atomarer Auditbeleg. Zaehler,
  alte Operationen und alle Holds unveraendert. Lebenszeitreserve16 x0.2343 =
  **USD3.7488**, keine frischen16 Versuche. Tages-/Monatszaehlgrenzen passend16,
   monetaere USD2.343-Tages-/Monatsgrenzen nicht pauschal anheben.
- Exakt zwei synthetische **Geraete-Payloads offline** bestimmen. iOS erzeugt
  JPEG neu; bisherige Manifest-Hashes duerfen nicht unverifiziert uebernommen
  werden. Die resultierenden Bytes/Beschreibung mit dem Backendvertrag in
  den kanonischen Gateway-Body ueberfuehren, Inputgrenzen und SHA-256 pruefen.
  Neues enges Zwei-Fall-Manifest und neue Create-only-Receipts reviewen;
  historische Manifeste und Operationen erhalten, keine beliebigen Bilder
  zulassen und keine Hashausnahme im Runtimecode einbauen. Erforderlicher
  Offline-Extraktionsweg fuer das konkrete Geraet ist noch vorzubereiten.
- Frische Budget-/Konfigurations-/Auth-/Hold-Nachweise und gebundener Grant fuer
  hoechstens1 Stunde, nur Owner und diese zwei Faelle. Originalperiodenende
  unveraendert. Nach jedem Fall Ledger/Diagnose sichern, zweiten erst mindestens
   65 Sekunden nach letzter Admission und nach laengerem Retry-After zulassen.
  Bei429/Timeout/unbekanntem Ausgang stoppen und Hold/Diagnose erhalten; keine
  Wiederholung und kein Aufstocken zum Erreichen eines Erfolgs.
- Letzter P5-Verbrauch war bekannt, der Clienttext ist generisch. Fuer diesen
  synthetischen Smoke muss der bekannte UX-Mangel im Testauftrag ausdruecklich
  genannt bleiben; keine allgemeine Refusal-Abnahme daraus ableiten. Fuer
  gewoehnliche Nutzung ist die oben beschriebene Vertrags-/UI-Klaerung offen.

### Kostenreserve fuer Freigabe B

Pro Aufruf weiter maximal272,000 Input- und2,000 Output-Token finanziell
reserviert, zum bestehenden Profil USD0.825/4.95 je Million: **USD0.2343**.
Zwei Aufrufe: **USD0.4686** zusaetzliche Modellreserve. Mit den bisherigen
konservativen Faktoren EUR1.20/USD und1.50 fuer Steuer/FX ergibt das EUR0.84348,
aufgerundet **EUR0.85**, plus **EUR0.50** gebundene Neben-/Abschlussreserve:
**EUR1.35 Gesamtreserve innerhalb der vorhandenen EUR20+5, kein neues Budget**.
Diese Reserve ist vorgeschlagen, nicht freigegeben oder als verfuegbar bewiesen.
Bekannt/alt gehalten plus neue Modellreserve: USD1.41958905. Alte Holds nicht
nochmals addieren oder aufloesen; bisherige Restreserven nicht doppelt zusagen.
Frische kumulative Kostensicht und verbleibende Hosting-/Steuer-/FX-/Abbaupflichten
muessen EUR1.35 frei lassen; andernfalls keine Aktivierung. Kostennachlauf und
EUR12-Stopp gelten weiter, kein garantierter All-in-Rechnungsdeckel.

Nach hoechstens zwei Aufrufen: KI aus, Grant widerrufen, wirksame Ready-Revision
pruefen, Modellzahl hoechstens16 (im Erfolgsablauf16), alte Holds unveraendert,
neue Kosten/Unklarheiten getrennt belegen. Nur eindeutig eigene synthetische
Testeintraege entfernen, Originalbestand vergleichen. Temporaere Testressourcen
und gesicherte Diagnosezeilen gezielt bereinigen; keine Gesamt-Ledger-Loeschung.

## Entscheidungsblatt fuer den naechsten Schritt

- [ ] Betreiber bestaetigt persoenliches Kontaktblatt und offene Einordnung in
  [Teilnehmerinformation](TEILNEHMERINFORMATION-ENTWURF.md); keine Einwilligung
  fuer eine andere Person. Echte Gesundheitsdaten bleiben ausserhalb A/B.
- [ ] **A getrennt genehmigen:** eigenes Geraet, Backup, In-place-Update unter
  unveraenderter Identitaet und AI-off-Smoke,0 Modellaufrufe.
- [ ] Nach A: **Vorbereitung B getrennt genehmigen**, insbesondere minimaler
  gepruefter14->16-Amendment-/Manifestweg und ggf. Refusal-UI-Korrektur.
- [ ] Erst nach diesen Nachweisen **B genehmigen:** L1 und P5 je einmal,
  maximal2 neue Aufrufe, USD0.4686/EUR1.35 Reserve, einmaliger Grant<=1 Stunde,
  anschliessend Sperre/Widerruf/Bereinigung. Keine Freigabe fuer Ehefrau oder
  anschliessenden Dauerbetrieb.

Belegblatt fuer die spaetere Ausfuehrung: Geraet/Version/Build privat; vorher/
nachher fachlicher Datenvergleich; realer Sign-in/Abbruch/Ruecksprung; Review/
Save-once und P5-Text; genau zugeordnete Vorgangs-/Providerbelege; letzte
Zaehler/Holds; Sperre und Bereinigung. Nicht ausgefuehrte Felder bleiben offen.