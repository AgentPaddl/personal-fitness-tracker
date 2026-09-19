# Persoenlicher Ernaehrungs-KI-Pilot: Teilnehmerinformation

Stand: 2026-09-19, technische Grundlage `cba6ee4`. **Entwurf, nicht freigegeben.**
Dieser Text erteilt weder eine Einwilligung noch eine Teilnahmeberechtigung.
Derzeit ist die KI gesperrt; nur synthetische Tests und notwendige eigene
Kontometadaten waren freigegeben. Echte Mahlzeiten-/Gesundheitsdaten und die
Teilnahme der Ehefrau sind weiterhin nicht freigegeben. Die endgueltige,
vervollstaendigte Information muss vor einer eigenen Entscheidung vorliegen.

## Wer betreibt den Pilot?

Betreiber ist die private natuerliche Person, die das Repository und das
verifizierte private Azure-Abonnement besitzt und ueber den Pilot entscheidet.
Dies ist kein Arbeitgeberangebot und kein Dienst von GitHub Copilot.

| Angabe fuer die persoenlich ausgehaendigte Fassung | Beleg oder offener Punkt |
| --- | --- |
| Vollstaendiger Name des Betreibers: **OFFEN zu bestaetigen** | Technische Owner-Identitaet ist verifiziert; Anzeigename, Verzeichnisname und Git-Autor beweisen keinen vollstaendigen buergerlichen Namen. |
| Kontakt/Widerruf: **vorhandene verifizierte Owner-Kontaktadresse privat einsetzen** | Bereits fuer die Budgetbenachrichtigung aus dem identitaetsgebundenen Entra-Kontakt ermittelt. Geschuetzter Beleg: `local/20260919/parameters.json`, Feld `parameters.budgetEmails.value[0]`; keine neue Adresse erfinden. Die Nutzung als erreichbarer Pilotkontakt ist noch zu bestaetigen. |
| Kontakt-/Zustellanschrift: **OFFEN** | Keine fuer diese Information bestaetigte Anschrift; nicht aus Rechnungsanzeigen ableiten. |
| Zustaendige Datenschutzaufsicht: **OFFEN nach Betreiberort** | Beschwerde ist bei einer Datenschutzaufsicht moeglich, insbesondere am Wohn-/Arbeitsort oder Ort eines vermuteten Verstosses. |
| Datenschutzbeauftragter | Keiner fuer diesen Pilot dokumentiert; eine etwaige Benennungspflicht ist gesondert zu pruefen. |

Private Namen, E-Mail-Adressen, Anschriften, Kontokennungen und ausgefuellte
Erklaerungen gehoeren nicht in Git oder in Testlogs. Diese Git-Fassung ist ohne
das persoenliche Kontaktblatt noch keine vollstaendige Art.-13-Information.

## Zweck und freie Entscheidung

Die optionale KI hilft, fuer eine selbst ausgewaehlte Mahlzeit Kalorien, Protein,
Kohlenhydrate und Fett zu schaetzen. Du pruefst und korrigierst das Ergebnis
selbst. Erst deine ausdrueckliche Bestaetigung speichert einen Eintrag lokal.
Manuelle Eingabe bleibt ohne KI moeglich. Keine Diagnose, Behandlung, Werbung,
Bewertung durch Arbeitgeber/Versicherungen oder automatische Gesundheitsentscheidung
ist vorgesehen. Die angezeigte Konfidenz ist keine nachgewiesene Trefferquote.

Du musst weder Texte noch Bilder senden. Ohne Bild kannst du die Textfunktion
verwenden; ohne KI-Einwilligung bleibt die manuelle Nutzung. Die Entscheidung
ueber eine KI-Teilnahme ist von technischer Anmeldung, Budgetfreigabe, Ehe und
dem Microsoft-Vertrag des Betreibers unabhaengig.

## Welche Daten gelangen wohin?

| Handlung | Uebertragene/verarbeitete Daten und Empfaenger |
| --- | --- |
| Lokales Tagebuch und manuelle Eingabe | Mahlzeiten mit Datum, Name, Naehrwerten und ggf. Notizen; Training, Gewicht, Ziele und Favoriten liegen in der lokalen SwiftData-Datenbank. Die Analyse liest und uebertraegt nicht automatisch diesen Bestand. |
| Anmeldung | Microsoft Entra verarbeitet Konto-/Tenantkennung, Anmelde- und Sicherheitsdaten sowie Netzwerk-/Geraetemetadaten. Zugangsdaten werden in der Microsoft-Anmeldung eingegeben, nicht in einem KI-Prompt. Die App verwendet MSAL mit Keychain-Token-Cache und speichert die ausgewaehlte Kontokennung in UserDefaults. |
| Textanalyse | Nur der ausdruecklich eingegebene Beschreibungstext geht per HTTPS an die eigene Fitness-API auf Azure Functions und dann an den eigenen Gateway auf Azure Container Apps. Kontoberechtigung, Vorgangs-ID, Zeit- und Anfragemetadaten werden zur sicheren Zuordnung geprueft. |
| Bildanalyse | Das ausgewaehlte/aufgenommene Foto wird auf dem iPhone als JPEG neu erzeugt, maximal 1280 Pixel lange Seite und maximal 3 MiB. Urspruengliche EXIF-/GPS-Metadaten werden nicht uebernommen. Dieses Bild und optionaler Beschreibungstext gehen ueber denselben Weg. Engere serverseitige Pilotgrenzen koennen die Eingabe trotzdem ablehnen. |
| KI-Berechnung | Der Gateway sendet Text bzw. Bild, Aufgabenanweisung und Antwortschema an **Microsoft Azure OpenAI / Foundry Models**, derzeit GPT-5.4-mini. Keine bewusste Weitergabe des Entra-Logins oder des ganzen Tagebuchs an das Modell. Selbst eingegebene Namen oder sichtbare private Bilddetails bleiben jedoch Inhalt. Azure kennt die technische Ressource und deren Nutzung. |
| Ergebnis | Die Schaetzung samt Unsicherheit/Hinweisen geht ueber Gateway und Fitness-API zur App zurueck. Ein nicht verwertbares Ergebnis ist kein speicherbarer KI-Entwurf. Der aktuelle Nicht-Lebensmittel-Fall erscheint noch als allgemeiner Analysefehler, nicht als eindeutiger Hinweis auf Nicht-Lebensmittel. |
| Erneute Berechnung im Review | Aktueller Mahlzeitenname und sichtbare Naehrwerte, ggf. urspruenglicher Text, Eingabeart, Ueberarbeitungsnummer und deine Korrektur werden erneut uebermittelt. Das urspruengliche Bild wird dabei nicht erneut angehaengt. Jede neue Berechnung ist eine eigene Verarbeitung, keine lokale Korrektur. Manuelles Bearbeiten der Felder sendet nichts. |
| Schutz und Kostenkontrolle | Azure Table speichert pseudonyme HMAC-Kennungen, Inhaltsfingerabdruck, Vorgangsstatus, Zeit-, Zaehler- und Kosteninformationen. Keine Rohbilder, Beschreibungen oder Naehrwertergebnisse im operativen Ledger. Pseudonym ist nicht anonym: der Betreiber besitzt die Zuordnungsmoeglichkeit. |

Microsoft hostet das Modell in Azure. Dieser Datenweg geht nicht zu ChatGPT,
einem von OpenAI betriebenen API-Dienst oder GitHub Copilot; es gibt keinen
Copilot-Ersatzweg. Microsoft und vertraglich eingesetzte Unterauftragnehmer
verarbeiten Daten; der Betreiber kann administrative Betriebsdaten einsehen.
Ein durchgaengig vor dem Betreiber verschluesselter Datenweg wird nicht behauptet:
Backend und Gateway muessen die Eingabe fuer die Weiterverarbeitung lesen.

Bitte keine fremden Personen, Namen, Briefe, medizinischen Unterlagen oder
private Umgebung aufnehmen. Entfernte Bildmetadaten entfernen keine sichtbaren
Gesichter, Texte oder aus einer Mahlzeit ableitbaren Gesundheitsinformationen.

## Speicherung ist nicht dasselbe wie Verarbeitung

| Ort/Daten | Dauer und Grenzen der Loeschung |
| --- | --- |
| Lokale Eintraege | Bis du sie in der App loeschst; die KI hat keinen automatischen Loeschzugriff. Beim Uebernehmen werden Name, Datum und Naehrwerte gespeichert, nicht automatisch das Bild oder der komplette KI-Dialog. |
| Ausgewaehltes Bild, Eingabe, Review | Die App haelt sie waehrend des Ablaufs im Speicher; nach einem Fehler bleibt die Auswahl fuer eine bewusste weitere Entscheidung erhalten. Keine beabsichtigte Fotoablage durch die Kameraansicht. Ein Original aus deiner Fotomediathek bleibt dort unabhaengig bestehen. |
| Geraetesicherung/Export | Ein App-JSON-Backup enthaelt auch weitere lokale Fitnessdaten und ist nicht selbst verschluesselt. Finder-/iCloud-Geraetesicherungen und ein von dir gewaehlt gespeicherter Export koennen zusaetzliche Kopien erzeugen. Geraete-/iCloud-Einstellungen sind noch vor Ort zu pruefen; kein pauschales Versprechen ausschliesslich lokaler Speicherung. |
| Kontodaten auf dem iPhone | MSAL-Token-Cache im Keychain, Kontowahl in UserDefaults. App-Schliessen ist kein Logout und keine bestaetigte Tokenloeschung; es gibt keinen belegten komfortablen Abmelden-/Widerrufsbutton. Entfernung muss gezielt vorbereitet werden, ohne die Tagebuch-App zu deinstallieren. |
| Eigene API/Gateway | Nutzinhalt wird zur Bearbeitung im Arbeitsspeicher verarbeitet, nicht als Mahlzeitenarchiv gespeichert. Technische Logs enthalten Status/Laufzeiten/Anfragekennungen und begrenzte Providerdiagnostik, sollen aber keine Nutzinhalte oder Tokens enthalten. Das ist kein Nachweis, dass Plattformtelemetrie keinerlei personenbezogene Daten enthaelt. |
| Betreiberdiagnostik | Genehmigt sind maximal 7 Tage fuer technische Diagnosen. Betreibergefuehrte Loeschung, kein installierter automatischer Loeschjob. Bei Nachweisen vom 19.09. ist die Frist bis 26.09. zu pruefen. |
| Vorgangsledger | Konfigurierte Aufbewahrung 31 Tage; Loeschroutine vorhanden, Ausfuehrung durch Betreiber erforderlich. Finanzielle Unklarheiten, offene Holds und notwendige Abrechnungs-/Rechtsnachweise werden eingeschraenkt weiter aufbewahrt, solange der konkret begruendete Zweck besteht. Keine pauschale ewige Speicherung, keine Freigabe neuer Versuche durch Loeschung. |
| Microsoft-Modell | Chat Completions mit `store=false`; kein angeforderter dauerhafter Chatverlauf, keine Files/Assistants/Responses/Batch-Nutzung oder Feinabstimmung. Microsoft dokumentiert keine Nutzung dieser Eingaben/Ausgaben zum Training der Basismodelle. Das ist **kein Zero-Retention-Versprechen** fuer den gesamten Dienst. |
| Missbrauchs-/Sicherheitspruefung | Automatisierte Pruefung; markierte Inhalte koennen fuer autorisierte menschliche Pruefung gespeichert werden. Keine bestaetigte Ausnahme vom Human Review fuer dieses Konto. Fuer EWR-Deployments nennt Microsoft Pruefer im EWR. **OFFEN:** anwendbare Dauer, Loeschverfahren und rechtliche Ausnahmen fuer markierte Inhalte. Keine unbelegte 30-Tage-Obergrenze. |
| Weitere Plattform-/Vertragsdaten | Entra-Anmelde-/Auditdaten, Azure-Betriebsdaten, Billing und rechtlich notwendige Nachweise folgen eigenen Regeln. Deren konkrete Fristen/Loeschwege sind **OFFEN**; Easy-Auth-Tokenstore ist deaktiviert, nicht alle Microsoft-Logs. Key Vault hat 7 Tage geschuetzte Wiederherstellung; eine Ressourcenloeschung entfernt nicht sofort alle Kopien. |

Hosting ist in Sweden Central, die Modellverarbeitung in der **EU DataZone**,
nicht zwingend nur in Schweden. EU Data Boundary und DPA haben dokumentierte
Support-, Sicherheits- und Transferausnahmen. **OFFEN:** fuer diesen Datenfluss
anwendbare Empfaenger/Unterauftragnehmer, Drittlandzugaenge, Garantien (z.B.
anwendbare Standardvertragsklauseln) und Bezugsmoeglichkeit der konkreten Garantien.
Eine normale KI-Einwilligung ist keine pauschale Art.-49-Ausnahme fuer Transfers.

## Rechtsgrundlage und Widerruf

Ob die ausschliesslich persoenliche/familiaere Taetigkeit des Betreibers unter
Art. 2 Abs. 2 Buchst. c DSGVO faellt, ist noch einzuordnen. Cloud-Nutzung allein
entscheidet diese Frage nicht; Microsofts eigene Datenschutzpflichten entfallen
dadurch nicht. Fuer eine anwendbare DSGVO ist folgender Weg **vorgeschlagen,
nicht beschlossen oder durch Einwilligung belegt**:

- Freiwillige Mahlzeitenanalyse: Art. 6 Abs. 1 Buchst. a; soweit die Angaben
  Gesundheitsdaten sind oder solche erkennen lassen, zusaetzlich ausdrueckliche
  Einwilligung nach Art. 9 Abs. 2 Buchst. a. Text und Bilder getrennt waehlbar.
- Notwendige Kontozuordnung und Sicherheits-/Kostenkontrolle: Zweckbindung und
  Datenminimierung; Art. 6 Abs. 1 Buchst. f kommt nur nach dokumentierter
  Erforderlichkeits-/Interessenabwaegung in Betracht. Keine Rechtfertigung von
  Gesundheitsdaten allein durch berechtigtes Interesse.
- Gesetzliche Aufbewahrung: Art. 6 Abs. 1 Buchst. c nur mit tatsaechlich
  einschlaegiger Pflicht; konkrete Pflicht/Frist **OFFEN**, keine erfundene
  steuerliche Pauschalfrist fuer diesen privaten Pilot. Rechtsverteidigung und
  Microsofts eigene Verantwortlichkeiten sind gesondert zuzuordnen.

Du kannst eine Einwilligung jederzeit ohne Begruendung ueber den persoenlich
bestaetigten Kontakt widerrufen, auch nur fuer Bilder. Beispiel: "Ich widerrufe
meine Einwilligung zur KI-Analyse ab jetzt." Bis zur Bestaetigung keine weiteren
Analysen absenden. Der Betreiber sperrt weitere KI-Verarbeitung, bestaetigt den
Eingang und klaert Loeschung/Aufbewahrung. Der aktuelle Pilot bietet keine
belegte technische Text-/Bild-Teilfreigabe; bei teilweisem Widerruf bleibt die
KI vollstaendig gesperrt, bis die Einschraenkung verlaesslich umgesetzt ist.
Abbrechen in der App kann bereits beim Provider laufende Verarbeitung nicht
zurueckholen. Der Widerruf aendert nicht die Rechtmaessigkeit frueherer,
wirksam eingewilligter Verarbeitung. Er ist kein Loeschbefehl fuer dein Tagebuch.

Soweit die DSGVO gilt, bestehen unter den jeweiligen Voraussetzungen Rechte
auf Auskunft, Berichtigung, Loeschung, Einschraenkung und Datenuebertragbarkeit
sowie Widerspruch bei Verarbeitung auf Grundlage berechtigter Interessen.
Anfragen sind grundsaetzlich binnen eines Monats zu beantworten; eine gesetzlich
zulaessige Verlaengerung muss begruendet mitgeteilt werden. Du kannst dich bei
einer Datenschutzaufsicht beschweren. Keine dieser Rechte wird hier abbedungen.

Loeschung wird getrennt bearbeitet: lokale Eintraege und eigene Foto-/Backupkopien
durch dich; Betreiberlogs und pseudonyme Vorgangsdaten durch den Betreiber;
notwendige Provider-/Plattformanfragen ueber den vertraglichen Kontakt zu Microsoft.
Nur minimale Kennungen, Zeitraum und Grund erheben, keine Rohbilder als
"Loeschnachweis" anfordern. Der Betreiber dokumentiert erledigte Loeschungen und
begruendete Ausnahmen mit naechstem Prueftermin. Ohne Nachweis keine Zusage einer
sofortigen oder vollstaendigen Loeschung aller Provider-/Backupdaten.

## Persoenliches Einwilligungsmuster (nicht ausgefuellt)

Erst nach Abschluss der offenen Informationen verwenden; keine vorangekreuzten
Felder. Technische Aktivierung bleibt eine weitere, separate Entscheidung.

- [ ] **Text:** Ich willige freiwillig und ausdruecklich ein, dass meine von mir
  abgesendeten Mahlzeitenbeschreibungen und Korrekturen einschliesslich daraus
  erkennbarer Gesundheitsdaten zum oben beschriebenen Zweck ueber die eigene
  API und Microsoft Azure verarbeitet und Schaetzungen an mich zurueckgegeben
  werden. Mir sind Empfaenger, Speicher-/Pruefungsgrenzen und Widerruf bekannt.
- [ ] **Bilder, optional:** Ich willige zusaetzlich ausdruecklich in diese
  Verarbeitung meiner jeweils ausgewaehlten Mahlzeitenbilder einschliesslich
  darin enthaltener oder daraus erkennbarer Gesundheitsdaten ein.

Teilnehmende Person: __________; Informationsversion: __________;
Datum und eigene bestaetigende Handlung/Unterschrift: __________.
Entscheidung zu nicht ausgewaehlten Umfaengen: keine Einwilligung.
Separater privater Nachweis der Aushaendigung und spaeterer Widerrufe: __________.
Niemand erklaert dies stellvertretend fuer den Betreiber oder seine Ehefrau.

## Betreiberanlage: DSFA-Vorpruefung und offene Entscheidungen

Dies ist eine dokumentierte Vorpruefung, keine abgeschlossene DSFA oder
Rechtsberatung. Beurteilt werden der vorbereitete Ein-Personen-Pilot, spaeter
allenfalls zwei Erwachsene, freiwillige Nutzung im privaten Umfeld, einzelne
bewusst abgesendete Mahlzeiten und keine medizinische Entscheidung. Die Aufnahme
einer zweiten Person ist damit nicht genehmigt. Der Zeitraum endet unveraendert
am 18.10.2026 um 22:19:10 UTC; keine automatische Verlaengerung.

| Kriterium/Risiko | Einordnung und Schutz bzw. offener Nachweis |
| --- | --- |
| Gesundheitsbezug/sensible Daten | Relevant: Ernaehrung, Texte und Bilder koennen Gesundheit erkennen lassen. Datensparsame Eingaben, ausdrueckliche eigene Entscheidung, kein Tagebuchupload. |
| Neue KI-Technik/Fehlschaetzungen | Relevant: Halluzinationen, falsche Portionen und ueberbewertete Konfidenz. Menschlicher Review, manuelle Alternative, kein automatisches Speichern oder Behandeln. |
| Bewertung/Profiling mit erheblicher Wirkung | Einzelne Naehrwertschaetzung; keine Entscheidung mit rechtlicher/aehnlich erheblicher Wirkung vorgesehen. Bei Gesundheitsprofilen, Empfehlungen oder Zweckwechsel neu pruefen. |
| Umfang/systematische Ueberwachung | Ein bis zwei Erwachsene, keine flaechendeckende oder oeffentliche Ueberwachung, kein umfangreicher Art.-35-Abs.-3-b-Fall belegt. Kleine Zahl allein ist keine Befreiung von Art. 35 Abs. 1. |
| Schutzbeduerftigkeit/Freiwilligkeit | Keine Kinder oder abhaengige Beschaeftigte vorgesehen. Ehebeziehung ist kein Einwilligungsnachweis; Ablehnung ohne Nachteil und manuelle Alternative sichern. |
| Datenverknuepfung/Zugangshindernis | Keine Fremddatenzusammenfuehrung vorgesehen; Kontozuordnung und Nutzungsmuster sind trotzdem personenbezogen. Keine essentielle Leistung von KI-Nutzung abhaengig. |
| Verlust/Offenlegung | Schwere moeglich hoch bei Gesundheitsdaten. HTTPS, getrennte Identitaeten, minimale Rollen, HMAC und inhaltsarme Logs reduzieren, beseitigen das Risiko aber nicht. Geraetesicherung und Rechtebearbeitung noch zu erproben. |
| Externe Speicherung/Transfers | Human Review, Retention und Transferausnahmen nicht abschliessend geklaert. Restwahrscheinlichkeit derzeit nicht belastbar quantifizierbar; keine Freigabe mit echten Gesundheitsdaten. |

**Vorlaeufiges Ergebnis:** Kein zwingender umfangreicher Fall aus Art. 35 Abs. 3
belegt; mindestens sensible Daten und innovative Verarbeitung sind relevante
Hochrisiko-Indikatoren. Keine pauschale Entscheidung "DSFA nicht erforderlich".
Vor echten Daten: zustaendige Art.-35-Abs.-4-Liste anhand des Betreiberorts
pruefen und begruendet entscheiden, ob voraussichtlich hohes Risiko besteht.
Bei hohem Risiko DSFA nach Art. 35 Abs. 7 abschliessen; bleibt trotz Massnahmen
hohes Risiko, Art. 36 vor Beginn pruefen. Ein rein synthetischer technischer
Smoketest ist davon zu unterscheiden, enthaelt aber weiterhin Kontometadaten.

Offene Entscheidungen, jeweils durch Betreiber mit Datum und Beleg:

1. Name, erreichbarer Kontakt, Betreiberort und rechtlicher Anwendungsbereich.
2. Art.-6-/Art.-9-Zuordnung, Freiwilligkeit und Einwilligungs-/Widerrufsprozess;
   Interessenabwaegung fuer minimale Sicherheits-/Abrechnungsdaten.
3. Anwendbare Human-Review-/Plattformfristen, Loeschwege, Transfergarantien,
  konkrete Microsoft-Vertrags-/Empfaengeridentitaet und Unterauftragnehmer
  fuer die auszuhaendigende Fassung. Der accountbezogen gepruefte MCA bindet den DPA
   ein; eine separate fehlende DPA-Unterschrift wurde nicht festgestellt.
4. DSFA-Entscheidung und ggf. vollstaendige DSFA; erneute Pruefung bei zweiter
  Person, Zweckwechsel, neuen Empfaengern, hoeheren Umfaengen oder Profilbildung.
5. Erreichbare Bearbeitung von Widerruf/Rechteanfragen, manuelle Retentionspruefung
   und Vorfallprozess; bei anwendbarer DSGVO Art. 33/34 beruecksichtigen.

## Quellen und technischer Abgleich

Am 19.09.2026 erneut gelesene oeffentliche Quellen:
[DSGVO](https://eur-lex.europa.eu/eli/reg/2016/679/oj/deu), insbesondere Art.
2, 6, 7, 9, 13, 17, 21, 28, 35, 36 und 44 ff.;
[Microsoft Datenverarbeitung](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/openai/data-privacy)
und [Missbrauchspruefung](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/abuse-monitoring).
Die Microsoft-Seiten nennen in der hier geprueften Fassung keine belastbare
numerische Obergrenze fuer die Aufbewahrung zur menschlichen Missbrauchspruefung.

Accountbezogene Vertrags-/Betriebsbelege und private Quellen stehen im
[Deploymentprotokoll](DEPLOYMENT-2026-09-19.md#concrete-privacy-review).
Codeabgleich: [Versand](../../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodAnalysisService.swift),
[Bildaufbereitung](../../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodImagePreprocessor.swift),
[Review/Speichern](../../ios/Trainingsplan/FoodAnalysisReviewView.swift),
[Backup](../../ios/Trainingsplan/BackupService.swift),
[MSAL](../../ios/Trainingsplan/Entra/MSALEntraTokenAcquirer.swift),
[Gatewaytransport](../../backend/gateway_client.py) und
[Providerparameter](../../ai-gateway/app/providers/openai_api.py).