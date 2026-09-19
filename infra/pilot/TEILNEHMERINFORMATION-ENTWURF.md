# Persoenlicher Ernaehrungs-KI-Pilot: Teilnehmerinformation

Stand: 2026-09-19, Ownercode `a150af6`. **Informationsentwurf, kein Einwilligungsformular.**
Die ausschliesslich eigene Nutzung von Mahlzeitentexten, Bildern und Refinements
wurde separat beauftragt und aktiviert:3 Berechnungen/UTC-Tag,12 insgesamt,
urspruengliches Ende18.10.2026,22:19:10UTC.16 Abnahmeversuche und vier Holds bleiben
erhalten. Ehefrau und weitere Nutzer sind weiterhin ausgeschlossen.

Fuer diese persoenliche Eigennutzung gilt die dokumentierte Einordnung zur
Haushaltsausnahme aus Art.2(2)(c)/Erwaegungsgrund18 DSGVO; Microsofts eigene
Pflichten und MCA/DPA bleiben bestehen. Ein Selbsteinwilligungsformular,
Supportticket, MSAL-Loeschdialog oder formelle DSFA sind keine pauschalen
Aktivierungsbedingungen. Fruehere P-/N-/V-Formulierungen weiter unten sind
historische Vorsorgevorschlaege, nicht aktuelle Pflichtfelder fuer die
Eigennutzung. Verbindlicher Umfang und Begruendung stehen im
[aktuellen Betriebsstand](README.md#datenschutz-und-verbleibende-unsicherheiten).
Die Quellen, Datenwege, unbeantworteten Anbieterfragen und Qualitaetsgrenzen
bleiben erhalten. Eine Information fuer weitere Teilnehmer ist damit nicht
freigegeben; persoenliche Kontaktangaben und Erklaerungen werden nicht erfunden.

Build7 erhielt die bestehenden Daten. Im begrenzten Geraetetest wurden die
L1-Reviewwerte und der Abbruch ohne Speichern sowie fuer P5 kein speicherbarer
Review und kein neuer Eintrag bestaetigt. Dies ist weder eine allgemeine
Genauigkeitsstudie noch ein separater Nachweis der semantischen P5-Erkennung;
die generische P5-Fehlermeldung bleibt eine bekannte Einschraenkung.

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
Der Betreiber ist zugleich der einzige vorgesehene Nutzer; eine zweite
Kontoregistrierung oder erneute technische Identitaetsfeststellung ist nicht
erforderlich. Die Ehefrau bleibt bis zu ihrer eigenen Aufnahme ausgeschlossen.

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

Vertragspartner des vorhandenen Microsoft-Kundenvertrags ist **Microsoft Ireland
Operations Limited** (Definition "Microsoft" im accountbezogenen Original).
Fuer die beauftragte Verarbeitung gelten MCA und eingebundener DPA; Microsofts
eigene Vertrags-, Sicherheits- und Geschaeftszwecke sind davon zu unterscheiden.
Die DPA-Vertretung im EWR ist Microsoft Ireland Operations Limited; der
Datenschutzkontakt ist ueber den DPA-Abschnitt "How to Contact Microsoft"
zugaenglich. Das ersetzt nicht den persoenlichen Pilotkontakt oben.

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
| Betreiberdiagnostik | Bestehende Entscheidung: maximal 7 Tage ab Erhebung fuer technische Diagnosen, ohne Nutzinhalte. Dieselbe Frist ist fuer den regulaeren Umfang vorgeschlagen, nicht neu bewilligt. Taegliche betreibergefuehrte Faelligkeitspruefung und Loeschung, kein installierter automatischer Loeschjob. Nachweise vom 19.09. werden spaetestens am 26.09. zum entsprechenden Erhebungszeitpunkt faellig. |
| Vorgangsledger | 31 Tage ab Erstellung der Operation; vorgeschlagen auch fuer regulaere Nutzung. Keine Fristverlaengerung durch Phasenwechsel oder Grant-Erneuerung. Loeschroutine vorhanden, aber keine vollstaendige Holds-/Archivierungsstrategie: vor Ausfuehrung notwendige Abrechnungsbelege sichern und Ausnahme pruefen. Offene Holds, minimale gemeinsame Zaehler und notwendige Nachweise getrennt zweckgebunden erhalten; Loeschen darf keine neue Versuchskapazitaet schaffen. |
| Microsoft-Modell | Chat Completions mit `store=false`; kein angeforderter dauerhafter Chatverlauf, keine Files/Assistants/Responses/Batch-Nutzung oder Feinabstimmung. Microsoft dokumentiert keine Nutzung dieser Eingaben/Ausgaben zum Training der Basismodelle. Das ist **kein Zero-Retention-Versprechen** fuer den gesamten Dienst. |
| Automatischer Prompt-Cache | Fuer diese Modellgeneration dokumentierter Default `in_memory`, kein `24h` angefordert. Berechnete Prompt-Praefixe koennen automatisch zwischengespeichert werden, auch fuer Bilder/Schema. Normalerweise Loeschung nach5-10 Minuten Inaktivitaet, spaetestens1 Stunde nach letzter Nutzung; erneute Nutzung verschiebt diesen Bezugspunkt. Keine gemeinsame Nutzung zwischen Azure-Subscriptions. Das ist eine separate dienstseitige Cachefrist, nicht die Human-Review-Frist; `store=false` deaktiviert diesen Cache nicht. |
| Missbrauchs-/Sicherheitspruefung | Automatisierte Pruefung; markierte Inhalte koennen fuer autorisierte menschliche Pruefung gespeichert werden. Keine bestaetigte Ausnahme vom Human Review fuer dieses Konto. Fuer EWR-Deployments nennt Microsoft Pruefer im EWR. **OFFEN:** anwendbare Dauer, Loeschverfahren und rechtliche Ausnahmen fuer markierte Inhalte. Keine unbelegte 30-Tage-Obergrenze. |
| Entra-Anmelde-/Auditdaten | Lesend am19.09. belegt: keine assignedPlans, keine subscribedSkus, keine Entra-Diagnoseexporte. Damit aktuell Free: Standard-Anmelde-/Auditdaten7 Tage. Keine Aussage ueber unbekannte manuelle Downloads oder alle Sicherheitsdaten: MFA-Nutzungsberichte30 Tage, risikobehaftete Benutzer bis Risikobehebung. Lizenz-/Exportaenderungen erfordern Neubewertung. Easy-Auth-Tokenstore deaktiviert, nicht alle Entra-Logs. |
| Azure Activity Log | Verwaltungsereignisse werden standardmaessig 90 Tage vorgehalten und dann geloescht; Eintraege sind nicht individuell aender-/loeschbar. Das ist keine Frist fuer alle Datenebenen-/Dienstlogs. Kein zusaetzlicher Logexport wird hier angeordnet. |
| Dienst-/Vertragsdaten | Konkrete weitere Diensttelemetrie, Billing-Aufbewahrung und Ausnahmen sind noch abzugrenzen. Key Vault hat 7 Tage geschuetzte Wiederherstellung. Der DPA nennt fuer nach Ablauf/Kuendigung der Subscription noch gespeicherte Online-Service-Kundendaten 90 Tage eingeschraenkten Zugriff und Loeschung binnen weiterer90 Tage, mit vertraglichen Ausnahmen. Kein Gleichsetzen von Ressourcenloeschung mit Subscription-Kuendigung und keine Uebertragung dieser Regel auf markierte Modellinhalte. |

Vorgeschlagener Ausnahmeprozess fuer notwendige lokale Nachweise: Bei Ende des
Piloten bzw. Widerruf nur den zur Klaerung benoetigten Minimalbeleg behalten,
Grund, Datenumfang, Zugriff, einschlaegige Pflicht (falls vorhanden) und naechsten
Prueftermin festhalten. Offene Holds beim taeglichen Kostenabgleich und spaetestens
alle30 Tage nach Pilotende erneut pruefen. Nach Klaerung binnen7 Tagen loeschen,
soweit keine konkret belegte weitere Pflicht besteht. Keine erfundene gesetzliche
Jahresfrist und keine automatische Loeschung noch ungeklaerter Holds. Diese
Entscheidung und die Behandlung des Einwilligungsnachweises sind privat zu
bestaetigen, nicht durch diesen Entwurf erteilt.

Hosting ist in Sweden Central, die Modellverarbeitung in der **EU DataZone**,
nicht zwingend nur in Schweden. Der vorhandene DPA, Abschnitt "Data Transfer",
erfasst moegliche Verarbeitung in den USA und anderen Laendern mit Microsoft-
oder Unterauftragnehmerbetrieb, vorbehaltlich der geografischen Zusagen und
Ausnahmen. Fuer Transfers aus EU/EWR verweist er auf die von Microsoft
implementierten2021-Standardvertragsklauseln; deren Definition benennt das
Processor-to-Processor-Modul zwischen Microsoft Ireland Operations Limited
und Microsoft Corporation. "Appendix C - Additional Safeguards Addendum"
enthaelt ergaenzende Zusagen. Die Garantiegrundlage ist somit nicht unbekannt.
Eine Kopie/Bezugsmoeglichkeit besteht ueber [Microsoft DPA](https://aka.ms/DPA)
und den vorhandenen privaten Vertragsbeleg; der Betreiber stellt die relevante
Fassung auf Anfrage bereit. Nicht behauptet wird eine abgeschlossene
Transferfolgenbewertung fuer diesen konkreten Pilot.

**Konkret zugeordnete Transferausnahmen:** autorisierter Fernzugriff von ausserhalb
EU/EFTA auf Betriebs-/Supportdaten; weltweite Sicherheitsverarbeitung von
pseudonymen Logs und begrenzten Daten (Konsolidierung vor allem USA, ggf. andere
Azure-Regionen); begrenzte Entra-Verzeichnisreplikation einschliesslich Name/E-Mail;
gelegentlicher Netzwerktransit ausserhalb der Boundary; begrenzte pseudonyme
Daten fuer globale Dienstqualitaet/Lizenzpruefung. Supportfalltitel, eskalierte
Faelle und Voicemails koennen ausserhalb gespeichert werden. Das sind moegliche
Verarbeitungsszenarien, kein Beleg eines im Pilot eingetretenen Vorfalls.
Microsoft beschreibt Zweckbindung, MFA, befristete genehmigte Zugriffe,
Secure Admin Workstations/VDI und Verschluesselung; SCC/DPA gelten wie oben.
Nicht behauptet werden aktiviertes Customer Lockbox, kundeneigene Modellschluessel
oder eine individuelle Transferfolgenbewertung.

**Kontobezogener Unterschied:** Entra-Organisationsland `DE`, aber ARM-
`dataBoundary=Global` (jeweils lesend19.09.2026). Die regionale Bereitstellung
bindet deshalb nicht saemtliche Verwaltungs-/Professional-Services-Daten an die
EU. Die fehlende ARM-EU-Einstellung wird weder still geaendert noch durch
Einwilligung ersetzt; Microsoft laesst deren Einrichtung nur fuer neue leere
Tenants zu. Kein Auftrag zu neuem Tenant, Migration oder neuen Kosten.

| Datenkategorie | Dienst und anwendbare Ortsaussage |
| --- | --- |
| Mahlzeitentext/-bild, Schema und Antwort im eigenen Transport | Functions und ACA sind in Sweden Central bereitgestellt; Nutzinhalt wird im Arbeitsspeicher verarbeitet. ARM Global ist keine Einstellung ihrer Datenebene. |
| Modellinferenz und Prompt-Cache | Azure OpenAI `DataZoneStandard` in EU DataZone; Inferenz kann innerhalb der EU-Zone verteilt sein. Nicht aus ARM Global auf weltweite Mahlzeiteninferenz schliessen. |
| Ausgewaehlte Abuse-/Human-Review-Inhaltskopien | Azure-OpenAI-Missbrauchsschutz: laut Dienstbeschreibung ressourcengetrennter Store in der Ressourcengeografie, fuer EWR-Deployment EWR-Pruefer; genaue Frist/Kriterien offen. Allgemeine Sicherheitsausnahmen gesondert beachten. |
| Pseudonyme Vorgangs-/Kostenmetadaten | Azure Table im regionalen Pilot-Storage, ohne Rohbilder oder Mahlzeitentexte. Andere Plattformtelemetrie nicht mit diesem Ledger gleichsetzen. |
| Konten, Anmeldung, Sicherheitsindikatoren | Entra mit Organisationsland DE, aktuell Free/kein Diagnoseexport; eigene Verzeichnis-/Sicherheitstransfers, nicht der Inferenzpfad der Mahlzeiten. |
| Ressourcenkennungen, Konfiguration und Verwaltungsoperationen | ARM `Global`: keine konfigurierte ARM-EU-Datenboundary; keine Behauptung, jedes Managementdatum liege zwingend in den USA. Activity Log hat eigene Orts-/90-Tage-Regeln. |
| Supportfalltitel, Diagnosen und andere Professional Services Data | Azure Support; mangels ARM-EU-Konfiguration keine entsprechende EU-Speicherzusage. Keine Mahlzeiten/Bilder an Support mitsenden; bewusst mitgesendete Inhalte waeren ein eigener Datenfluss. |

Die Klassifikation **V/U/T im Entscheidungsblatt** legt die Pilotbedingungen fest.
ARM Global allein ist kein pauschaler rechtlicher oder technischer Aktivierungs-
blocker; es verlangt die korrekte Information ueber die betroffenen Kategorien.
**Weiter offen:** aktuelle dienstbezogene Unterauftragnehmerliste und fuer nicht
naeher spezifizierte Fernzugriffs-/Supportempfaenger konkrete Laenderzuordnung;
die allgemein dokumentierten Ausnahmen selbst sind nicht mehr unbekannt.
Keine zusaetzlichen Dienste wie Bing-Grounding, Websuche, Files oder Training.
Eine normale KI-Einwilligung ist keine pauschale Art.-49-Ausnahme fuer Transfers.

## Microsoft-Nachweise: Vertrag, Einstellung, Restfrage

Recherche und gezielte GET-Abfragen am19.09.2026, keine Vertragsannahme,
Supportanfrage, Konfigurationsaenderung oder Modellanfrage. Der bereits
accountbezogen verifizierte MCA mit Microsoft Ireland Operations Limited und
DPA May2026 wird weiterverwendet; Originalhashes stehen unten.

| Ebene | Fuer diesen Pilot belegt | Keine weitergehende Behauptung |
| --- | --- | --- |
| Vertrag | MCA bindet DPA/Product Terms ein. Azure-Product-Terms, Abschnitt Microsoft Foundry Models, erlauben temporaere Input-/Output-Speicherung fuer Abuse Monitoring und autorisierten Human Review; fuer Deployments in der EU Boundary EWR-Pruefer. Ausnahme nur bei erteilter und eingehaltener Modified-Abuse-Monitoring-Genehmigung. DPA/Privacy & Security Terms enthalten geografische Zusagen samt Transferausnahmen und SCC. | "Temporaer" nennt hier keine Anzahl Tage. Portal-Einstellung ist keine neue Vertragszusage. Keine fehlende separate DPA-Unterschrift. |
| Konfiguration | Archivierter Deploymentbeleg: `pilot-mini`, GPT-5.4-mini `2026-03-17`, `DataZoneStandard`, Sweden Central, NoAutoUpgrade. Erneutes Account-GET: Kind OpenAI, Sweden Central, kein `ContentLogging=false`. Code: Chat Completions, `store=false`, keine angeforderte24h-Cache-Policy, keine Files/Responses/Assistants/Batch/Feinabstimmung/Bing-Anbindung. | Nicht OpenAI-direkte API, nicht Copilot, nicht Sweden-only-Verarbeitung; keine belegte Monitoring-Ausnahme, kein Zero Retention. Modellbedingungsseite enthaelt keine GPT-5.4-mini-spezifische Zusatzklausel in der gelesenen Fassung. |
| Dienstbeschreibung | Datenverarbeitungsseite: Modellinferenz fuer EU-DataZone innerhalb der EU-Zone; kein Zugriff anderer Kunden oder OpenAI, kein Basismodelltraining aus diesen Daten ohne Erlaubnis/Weisung. Modelle selbst zustandslos. Automatisierte Abuse-Pruefung speichert die dabei geprueften Inhalte laut Beschreibung nicht; fuer Human Review ausgewaehlte Stichproben dagegen in ressourcengetrenntem Store in der Ressourcengeografie. | Zustandslosigkeit des Modells ist nicht Speicherfreiheit des Dienstes. Vertragliche temporaere Speicherung und die konkreter beschriebene Stichprobenpruefung nicht zu einem pauschalen Nullspeicherungsversprechen zusammenziehen. |
| Weitere Kontoeinstellungen | Microsoft Graph `organization` (nur countryLetterCode/assignedPlans): DE/leere Plaene; `subscribedSkus`: leer. ARM `Microsoft.aadiam/diagnosticSettings` API2017-04-01: leer. ARM `Microsoft.Resources/dataBoundaries/default` API2024-08-01: Global/Succeeded. | Belegt Entra Free ohne eingerichtete Diagnoseexporte und keine ARM-EU-Bindung, nicht den rechtlichen Betreiberwohnsitz oder das Fehlen aller Microsoft-internen Kopien. |

Belegte Quellen, jeweils relevante Abschnitte statt pauschaler Compliancebehauptung:

- [Azure Product Terms fuer MCA](https://www.microsoft.com/licensing/terms/productoffering/MicrosoftAzure/MCA): Microsoft AI Services / Microsoft Foundry Models / Data Use and Access for Abuse Monitoring und Limited exception.
- [Privacy & Security Terms fuer MCA](https://www.microsoft.com/licensing/terms/product/PrivacyandSecurityTerms/MCA): General, Core Online Services, EU Data Boundary Services. DPA hat Vorrang; Bing/Web-IQ-Ausnahmen werden hier nicht genutzt.
- [Datenverarbeitung](https://learn.microsoft.com/en-us/azure/foundry/responsible-ai/openai/data-privacy): Inferencing, DataZone, Preventing abuse, ContentLogging; Dokumentstand18.05.2026.
- [Abuse Monitoring](https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/abuse-monitoring): Components, Modified abuse monitoring; Dokumentstand13.05.2026. Genehmigungsantrag ueber das dort verlinkte Microsoft-Customer-Voice-Formular, kein einfacher Opt-out-Schalter; kein Antrag gestellt.
- [Prompt-Cache](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/prompt-caching): In-memory retention, Configure per request, FAQ; Dokumentstand11.08.2026. Keine Uebernahme der abweichenden GPT-5.5/5.6-Regeln auf das gepinnte Mini-Modell.
- [Fortbestehende Transfers](https://learn.microsoft.com/en-us/privacy/eudb/eu-data-boundary-transfers-for-all-services): Remote access, Protecting customers, Directory data, Network transit, Professional Services Data; Dokumentstand30.03.2026.
- [Nichtregionale Dienste](https://learn.microsoft.com/en-us/privacy/eudb/eu-data-boundary-configure-azure-nonregional-services): Entra und ARM; [ARM-Konfiguration und GET](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/manage-data-boundary). Entra-Sicherheit: [fortlaufende Teiltransfers](https://learn.microsoft.com/en-us/privacy/eudb/eu-data-boundary-ongoing-partial-transfers#microsoft-entra-id), etwa globale Sperrindikatoren bei Missbrauch.
- [Modellspezifische Bedingungen](https://learn.microsoft.com/en-us/legal/microsoft-foundry/model-specific-terms): gelesene Fassung17.07.2026; keine zusaetzliche GPT-5.4-mini-Speicherfrist genannt.

### Exakt fehlende Auskunft und Bezugsweg

**N1, an Microsoft Azure Support fuer die vorhandene Ressource**, ueber Azure
Portal > Hilfe + Support; fuer Datenschutz-/Betroffenenanfragen zusaetzlich der
im DPA unter "How to Contact Microsoft" genannte Privacy-Kanal. Kein kostenpflichtiger
Supportplan wird hier bestellt. Falls der vorhandene Supportumfang nicht reicht,
den vertraglichen Datenschutzkontakt um Weiterleitung an das Dienstteam bitten.
Vorbereiteter Inhalt, **nicht abgesendet**, nur Ressourcenkennung/Zeitraum privat
beifuegen, keine Mahlzeiten, Bilder, Tokens oder kompletten Logs:

> Fuer Azure OpenAI GPT-5.4-mini 2026-03-17, EU DataZoneStandard in Sweden
> Central, Chat Completions mit store=false und ohne ContentLogging=false:
> Welche maximale Dauer oder objektiven Loeschkriterien gelten fuer temporaere
> Abuse-Monitoring-Kopien und Human-Review-Stichproben, ab welchem Ereignis,
> einschliesslich Replikate/Backups? Werden vor der Auswahl weitere Kopien
> gespeichert? Welche Sicherheits-/Rechtsausnahmen verlaengern diese Dauer,
> wer prueft sie wann, und welcher Anfrageweg mit welchen minimalen Kennungen
> ermoeglicht Auskunft/Loeschung? Welche Wirkung haben Ressourcen-/Subscription-
> Loeschung, und wann ist die Loeschung aller betroffenen Kopien abgeschlossen?
> Bitte Inhaltskopien von Missbrauchsmustern/Signalen und Systemlogs mit jeweils
> eigenen Fristen trennen sowie anwendbare Vertrags-/Dienstfassung und Unterschied
> zwischen Standard- und Modified Abuse Monitoring bestaetigen.

Die untersuchten Bedingungen und die Account-Capabilities beantworten diese
Frist-/Loeschfragen nicht. Kein belastbarer Nachweis einer30-Tage-Obergrenze.

**N2, Plattformrest:** Entra-Lizenz/Diagnoseexport ist geklaert. Fuer Microsofts
eigene Betriebs-/Sicherheits-/Billingdaten fehlen noch dienst-/zweckbezogene
Fristen oder Loeschkriterien und rechtliche Ausnahmen; derselbe Datenschutzkontakt
bzw. Billing-Support muss sie fuer diese Dienste benennen. Die allgemeinen
DPA-Fristen nach Subscription-Ende ersetzen diese Zuordnung nicht.
Konkrete Anfrage: "Welche Fristen oder objektiven Loeschkriterien gelten getrennt
fuer Inhaltskopien, Konto-/Ressourcenkennungen, Sicherheits-/Supporttelemetrie
und Abrechnungsbelege von Azure OpenAI, Functions/ACA, Storage, Entra und ARM;
welche gesetzlichen Ausnahmen und welche Wirkung hat die Ressourcenloeschung?"
Reine interne Betriebs-/Billingdetails bleiben **U**, nicht automatisch ein
Hindernis fuer die eigene Nutzung. Unbekannte Mahlzeitenkopien oder fehlende
wesentliche Pflichtinformationen waeren dagegen vor Aktivierung zu klaeren.
Am iPhone ist die Lage technisch geklaert: `clearSelectedAccountIdentifier`
entfernt nur die Kontowahl. Der vorhandene MSAL-Adapter exponiert keine
Konten-/Tokenentfernung. App-Schliessen, Grant-Widerruf und Session-Sperre sind
keine lokale Keychain-Loeschung. Fuer einen nachweisbaren gezielten Loeschweg
ohne Deinstallation fehlt weiterhin eine gesondert gepruefte Bedienmoeglichkeit;
dieser Auftrag implementiert keine neue iOS-Funktion und loescht keine Daten.

### Gezielter MSAL-Loeschweg, nicht ausgefuehrt

Die App pinnt MSAL2.15.0, Revision `d54e9653f94883a896af533133888be1c2ef5c75`.
Der [zugehoerige oeffentliche API-Header](https://github.com/AzureAD/microsoft-authentication-library-for-objc/blob/d54e9653f94883a896af533133888be1c2ef5c75/MSAL/src/public/MSALPublicClientApplication.h)
dokumentiert `removeAccount:error:` fuer alle Tokens **dieser Anwendung und
dieses Kontos**. Das ist kein pauschales Keychain-Wipe. Konkreter spaeterer Ablauf:

1. KI gesperrt lassen; laufende Login-/Tokenvorgaenge beenden, automatische
  Neuanmeldung waehrend der Entfernung verhindern. Vorher App-Konfiguration
  (Client-ID, Authority, Keychain-Zugriffsgruppe/Entitlements) und genau die
  vorhandene Owner-Kontokennung zuordnen; keine fremden Konten bearbeiten.
2. Auf derselben `MSALPublicClientApplication` mit `accountForIdentifier:error:`
  dieses Konto laden. Bei Cachefehler oder uneindeutiger Zuordnung abbrechen,
  nicht wahllos alle Konten loeschen. Kein Konto ist kein Beweis, dass Browser,
  Broker und alle Geraetekopien bereinigt sind.
3. Nur fuer dieses Konto `removeAccount:error:` aufrufen und Rueckgabewert/Fehler
  pruefen. Erst nach Erfolg `clearSelectedAccountIdentifier()` fuer die
  App-Kontowahl ausfuehren und gehaltene Anmeldesitzung/Tokenreferenzen verwerfen.
  Bei Fehler keine Erfolgsbestaetigung und keine automatische Neuanmeldung.
4. Lokal bzw. im kontrollierten Test nachweisen: Kontowahl leer, Konto-/Token-
  Lookup im betroffenen App-Cache bereinigt, Neustart stellt die Auswahl nicht
  wieder her, keine lokalen Tokens erneut nutzbar. Andere Konten und SwiftData-
  Tagebuch unveraendert. Kein Modellaufruf und keine Tokenwerte im Nachweis.
  Broker-/SSO-Ruecklieferung von Konten nicht mit einer erfolgreichen lokalen
  Cacheloeschung verwechseln; verbleibenden Umfang explizit benennen.
5. Browser-/Broker-SSO ist ein **anderer Umfang**: ggf. nach separater Entscheidung
  `signoutWithAccount:signoutParameters:completionBlock:` mit
  `signoutFromBrowser=true` (OIDC-Netzwerk-/Browseraktion). Broker/MDM kann den
  Umfang beeinflussen. `wipeAccount` und `wipeCacheForAllAccounts` nicht aktivieren:
  diese koennen geteilte bzw. andere Kontencaches treffen. Kein globaler
  Sessionwiderruf, keine Authenticator-Kontenentfernung, keine App-Deinstallation.

[Microsoft beschreibt die Signout-Parameter und deren Nebenwirkungen](https://azuread.github.io/microsoft-authentication-library-for-objc/Classes/MSALSignoutParameters.html).
Cacheentfernung widerruft keine bereits ausgegebenen Tokens serverseitig und
loescht weder Providerlogs noch Tagebuch/Backups. Umgekehrt loescht ein
serverseitiger Grantwiderruf keinen iPhone-Keychain-Eintrag. Der jetzige Adapter
bietet Schritt2-4 nicht als ausfuehrbare Bedienfunktion an: Implementierung und
modellfreier Nachweis sind noch **V**, nicht durch eine Beschreibung erledigt.
Keiner dieser Schritte wurde in diesem Review ausgefuehrt.

### Unterauftragnehmerliste: Frage und Bezugsweg

**N3, Empfaengerrest:** Die aktuelle "Microsoft Online Services Subprocessor
List" mit Versionsdatum, Rechtstraegern, Taetigkeiten, Diensten und Laendern
ist ueber das im DPA genannte [Service Trust Portal](https://servicetrust.microsoft.com/)
zu beschaffen. Die oeffentliche Dokumentansicht und Trust-Center-Verweise lieferten
hier keine auswertbare aktuelle Liste; Letztere fuehrten zur Anmeldung. Nicht
behauptet wird, dass sie generell nicht verfuegbar ist. Mit vorhandenem berechtigtem
Konto dort nach dem Dokumenttitel suchen; falls kein Zugriff besteht, dieselbe
Liste und die konkret einschlaegigen Support-/Fernzugriffslaender vom
Microsoft-Vertrags-/Datenschutzkontakt anfordern. Keine neue Zustimmung/NDA
stellvertretend abgeben. Liste gegen Entra, Functions/ACA, Storage/Table, KV/ACR
und Azure OpenAI abgleichen; nicht alle weltweit gelisteten Firmen automatisch
als tatsaechliche Empfaenger dieses Piloten darstellen.
Konkrete Anfrage: "Bitte aktuelle datierte Online-Services-Unterauftragnehmerliste
und Zuordnung der fuer diese Dienste einschlaegigen Rechtstraeger, Zwecke,
Datenkategorien und Laender sowie der jeweiligen Transfergarantien bereitstellen."
Die wesentliche Zuordnung ist **V**; nicht veroeffentlichte Detailketten bzw.
gelegentliche Fernzugriffslaender bleiben explizite **U**, solange dadurch keine
wesentliche Information oder erforderliche Transferbewertung ersetzt wird.

## Rechtsgrundlage und Widerruf

Fuer diesen Ein-Nutzer-Start ist persoenlich festzuhalten, ob ausschliesslich
eigene Daten privat genutzt werden und weder Oeffentlichkeit, Verein noch
Arbeitgeber beteiligt sind. Betreiber- und Nutzerrolle sind dieselbe Person;
ein Muster darf nicht kuenstlich eine Einwilligung eines Dritten fingieren.
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

Vorbereitete Interessenabwaegung fuer den Fall anwendbarer DSGVO: Berechtigter
Zweck ist Schutz vor unberechtigter Nutzung, Doppelabrechnung und Budgetverlust.
Kontopruefung, HMAC-Vorgangskennung und Kostenstatus sind dafuer erforderlich;
Rohbilder, Naehrwerte oder Tracking ueber andere Dienste waeren es nicht.
Restrisiken sind Zuordenbarkeit, Einsicht des Administrators und externe
Sicherheitsdaten. Ein Nutzer, kurze Zweckfristen, begrenzte Zugriffe und
inhaltlose Belege reduzieren diese Risiken. Ob die Interessen ueberwiegen,
ist vom Betreiber mit Datum zu entscheiden; Gesundheitsinhalte werden dadurch
nicht legitimiert. Bei Haushaltsausnahme ist die begruendete Nichtanwendbarkeit
statt einer erfundenen Art.-6-/Art.-9-Einwilligung zu dokumentieren. Eine eigene
informierte Entscheidung ueber den Cloudversand bleibt in beiden Faellen noetig.

Eine moegliche Haushaltsausnahme gilt nur fuer diese tatsaechlich ausschliesslich
eigene private Nutzung. Sie wird **nicht auf eine spaetere externe Beta uebertragen**:
fremde Testpersonen, oeffentliche Einladung, Produkt-/Geschaeftszweck oder
Verarbeitung fremder Gesundheitsdaten erfordern vorher eine neue Rollen-,
Rechtsgrundlagen-, Informations-, Transfer- und DSFA-Pruefung. Unentgeltlichkeit
oder die Bezeichnung "Beta" allein begruenden keine Haushaltsausnahme.

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
Dieses Muster nur verwenden, wenn die dokumentierte Rechtsgrundlagenentscheidung
den Einwilligungsweg vorsieht; bei begruendeter Haushaltsausnahme eine eigene
informierte Nutzungsentscheidung aufzeichnen, nicht DSGVO-Anwendbarkeit vortaeuschen.
Ohne technische Trennung der Umfaenge reicht "nur Text" nicht fuer die Freigabe
der heute auch bildfaehigen API. Dann bleibt die KI gesperrt; keine Ausweitung
der Entscheidung auf Bilder durch technische Aktivierung.

## Betreiberanlage: DSFA-Vorpruefung und offene Entscheidungen

Dies ist eine dokumentierte Vorpruefung, keine abgeschlossene DSFA oder
Rechtsberatung. Beurteilt wird ausschliesslich der vorbereitete Ein-Personen-Pilot
mit maximal3 Berechnungen pro UTC-Tag und12 insgesamt, freiwillig und privat, einzelne
bewusst abgesendete Mahlzeiten und keine medizinische Entscheidung. Die Aufnahme
einer zweiten Person ist damit nicht genehmigt. Der Zeitraum endet unveraendert
am 18.10.2026 um 22:19:10 UTC; keine automatische Verlaengerung.

| Kriterium/Risiko | Einordnung und Schutz bzw. offener Nachweis |
| --- | --- |
| Gesundheitsbezug/sensible Daten | Relevant: Ernaehrung, Texte und Bilder koennen Gesundheit erkennen lassen. Datensparsame Eingaben, ausdrueckliche eigene Entscheidung, kein Tagebuchupload. |
| Neue KI-Technik/Fehlschaetzungen | Relevant: Halluzinationen, falsche Portionen und ueberbewertete Konfidenz. Menschlicher Review, manuelle Alternative, kein automatisches Speichern oder Behandeln. |
| Bewertung/Profiling mit erheblicher Wirkung | Einzelne Naehrwertschaetzung; keine Entscheidung mit rechtlicher/aehnlich erheblicher Wirkung vorgesehen. Bei Gesundheitsprofilen, Empfehlungen oder Zweckwechsel neu pruefen. |
| Umfang/systematische Ueberwachung | Ein erwachsener Nutzer, maximal12 neue Berechnungen im verbleibenden Zeitraum, keine flaechendeckende oder oeffentliche Ueberwachung, kein umfangreicher Art.-35-Abs.-3-b-Fall belegt. Kleine Zahl allein ist keine Befreiung von Art. 35 Abs. 1. |
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

Privates Entscheidungsfeld: Betreiberort/zustaendige Art.-35-Abs.-4-Liste mit
Version und gepruefter Fundstelle: __________. DSGVO-Anwendungsbereich und
Begruendung: __________. Ergebnis: [ ] Vorpruefung bei Haushaltsausnahme nur
vorsorglich; [ ] keine voraussichtlich hohe Gefahr, Begruendung trotz der beiden
Indikatoren: __________; [ ] DSFA erforderlich, vor Aktivierung abzuschliessen.
Entscheidende Person/Datum: __________. Keine Auswahl ist vorweggenommen.
Wesentliche V-Luecken muessen vor der abschliessenden Bewertung geschlossen sein;
U-Punkte bleiben mit ihren Grenzen Bestandteil der Risikobetrachtung.
Bei zweiter Person, Zweckwechsel, anderen Empfaengern oder hoeherem Umfang erneut
pruefen; dies genehmigt insbesondere keine Aufnahme der Ehefrau.

## Genau verbleibende Angaben und Nachweise

**Persoenlich ausfuellen oder entscheiden, nur privat:**

Kurzfassung zum Bearbeiten: [vorausgefuelltes Entscheidungsblatt](EIGENTUEMER-ENTSCHEIDUNGSBLATT.md).
Vorhandene private Vertrags-/Kontaktangaben uebernehmen; keine erneute technische
Identitaetspruefung. Eine formelle Zustellanschrift ist nicht Voraussetzung fuer
das blosse private Lesen dieser Vorbereitung, sondern nach der rechtlichen
Einordnung fuer die gegebenenfalls erforderliche vollstaendige Information.

| Nr. | Noch erforderlich | Was bereits vorliegt |
| --- | --- | --- |
| P1 Kontakt | Vorhandene private Angaben uebernehmen; vollstaendigen Betreibernamen und Betreiberort nur soweit fehlend ergaenzen bzw. bestaetigen. Kontakt-/Zustellanschrift soweit fuer die rechtlich erforderliche Information noetig. Erreichbarkeit des bekannten Kontakts bestaetigen. | Owner-Identitaet und Kontaktquelle sind belegt; keine neue Adresse/Identitaet erfinden. Aufsicht wird anhand Betreiberort bestimmt, nicht geraten. |
| P2 Rechtsgrundlage | Tatsaechlich ausschliesslich eigener privater Gebrauch bestaetigen; Haushaltsausnahme begruendet einordnen oder die vorgeschlagene Art.-6-/Art.-9-Zuordnung und Interessenabwaegung entscheiden. Ergebnis/Datum eintragen. | Zweck, Datenwege und vorgeschlagene Abwaegung oben; keine pauschale Rechtsfreigabe erforderlich. Etwaige gesetzliche Belegpflicht nur nennen, wenn tatsaechlich einschlaegig. |
| P3 Aufbewahrung/Transfers | Nach Schliessen der V-Anteile von N1-N3 und Offenlegung der U-Anteile die konkreten Regeln fuer regulaere eigene Daten entscheiden:7 Tage Diagnostik,31 Tage Operationen, begrenzte Hold-/Belegausnahmen und manuelle Pruefung. Bestehende iCloud-/Geraetesicherungen und Exportkopien privat einordnen. | Bestehende7/31-Tage-Entscheidung gilt bisher fuer technische Abnahme; kein neuer Backupauftrag und keine Aenderung vorhandener Daten. Vertrag/SCC werden nicht erneut unterschrieben. |
| P4 Eigene Entscheidung | Erst mit vollstaendiger Informationsversion Text und optional Bilder selbst waehlen und mit Datum/Handlung dokumentieren; bei gewaehltem Einwilligungsweg ausdrueckliches Muster oben verwenden. | Kein Haken gesetzt; bisherige Budget-/Testfreigaben sind keine Einwilligung fuer persoenliche Mahlzeiten. Ablehnung bleibt moeglich. |
| P5 DSFA-Vorpruefung | Das Entscheidungsfeld oben mit zustaendiger Liste, Begruendung und Datum abschliessen; falls erforderlich DSFA vor Aktivierung. | Konkrete Risikoanalyse fuer einen Nutzer liegt vor; keine pauschale DSFA-Befreiung. Ob ein Datenschutzbeauftragter zu benennen ist, nur bei einschlaegiger Pflicht begruenden, keinen Kontakt erfinden. |
| P6 Betrieb und Aktivierung | Vorgeschlagene3/12-Policy, unveraendertes Enddatum, gemeinsame Kostenkontrolle sowie eigene taegliche Kosten-/Loeschpruefung und rechtzeitigen Cleanup bestaetigen. Nach den erforderlichen V-Nachweisen und persoenlichen Entscheidungen den einen Plan im README einschliesslich Review/Auslieferung des lokal fertigen N4 freigeben; Aktivierung erst nach modellfreiem Live-Nachweis. | Stoppeigner ist bereits der Betreiber; kein neuer Verantwortlicher, kein neues Budget, kein automatischer Folgegrant. |

**Noch zu beschaffen/technisch zu belegen, nicht von dir zu erraten oder
pauschal zu attestieren:**

| Nr. | Konkrete Restluecke und Abschlussnachweis |
| --- | --- |
| N1 Modellaufbewahrung | Microsoft-Nachweis fuer markierte Inhalte beim konkret verwendeten Standard-Abuse-Monitoring: maximale Frist oder belastbare Loeschkriterien, Ausnahmen und Rechte-/Loeschkanal. Keine bestaetigte Human-Review-Ausnahme; keine30-Tage-Frist erfinden. Bei unbeantworteter Luecke bleibt echte Datennutzung gesperrt. |
| N2 Plattform/Loeschung | Entra Free/kein Diagnoseexport belegt; Hold-Cleanup lokal korrigiert und getestet. Offen bleiben konkret zugeordnete Microsoft-Betriebs-/Billingfristen und ein am Geraet gepruefter, gezielter MSAL-Entfernungsweg ohne Deinstallation, siehe Bezugswege oben. |
| N3 Transfers | Allgemeine und dienstbezogene Ausnahmen, SCC und Schutzmassnahmen oben zugeordnet; ARM Global ist belegt. Noch aktuelle Unterauftragnehmerliste und nicht spezifizierte Empfaengerlaender ueber Service Trust Portal/Vertragskontakt ergaenzen. Keine Behauptung pauschaler EU-Exklusivitaet. |
| N4 Phasenwechsel | Lokal implementiert und fokussiert getestet, einschliesslich Archivsimulation mit16/16 und vier Holds. Noch kein Live-Uebergang/Deployment. Vor Aktivierung gesondert freigegebene gesperrte Auslieferung, exakte Policy-/Grantbindung und modellfreier Live-Readback gemaess README erforderlich. |

Kein Auftrag zu erneuter MCA-Annahme, separater DPA-Unterschrift, pauschalem
Cloud-Audit, neuem Modelltest oder Stellvertretung bei Einwilligung. Fehlende
Providerbelege werden nicht durch eine Risikoakzeptanzformel ersetzt. Vollstaendig
aushaendigbar ist die Information erst nach den erforderlichen Betreiberangaben,
begruendeter rechtlicher Einordnung und Schliessen wesentlicher V-Luecken.
U-Punkte werden als Grenzen offengelegt, nicht als Nullrisiko bestaetigt;
T-Schritte muessen fuer die reine Eigentuemerphase nicht vorgezogen werden.
Der einzige gebuendelte technische Ablauf steht im
[Ein-Nutzer-Plan](README.md#regulaere-ein-nutzer-nutzung-ab-d5de5c6).

## Quellen und technischer Abgleich

Am 19.09.2026 erneut gelesene oeffentliche Quellen:
[DSGVO](https://eur-lex.europa.eu/eli/reg/2016/679/oj/deu), insbesondere Art.
2, 6, 7, 9, 13, 17, 21, 28, 35, 36 und 44 ff.;
[Microsoft Datenverarbeitung](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/openai/data-privacy)
und [Missbrauchspruefung](https://learn.microsoft.com/en-us/azure/ai-foundry/openai/concepts/abuse-monitoring).
Die Microsoft-Seiten nennen in der hier geprueften Fassung keine belastbare
numerische Obergrenze fuer die Aufbewahrung zur menschlichen Missbrauchspruefung.

Fuer diese Dokumentationsfortschreibung wiederverwendet: accountbezogener MCA
SHA-256 `72431ff06d62e32ba19f49aed82e256caecc6a895334d87725c50b13c4e8c3ac`
und DPA May2026 SHA-256
`d79e06734ddff63593375c5134f3e362da7ddf6d265308776a2c7db4b7233f41`.
Die vorhandenen privaten Originale wurden lokal hashgeprueft; kein neuer
Vertrag akzeptiert. DPA-Abschnitte "Data Transfer", "Data Retention and
Deletion", "Notice and Controls on use of Subprocessors" und "How to Contact
Microsoft" sowie MCA-Definition "Microsoft" konkretisieren die Angaben oben.
Oeffentliche Microsoft-Dokumentation am19.09.2026 gezielt gelesen:
[Entra-Fristen](https://learn.microsoft.com/en-us/entra/identity/monitoring-health/reference-reports-data-retention)
und [Azure Activity Log](https://learn.microsoft.com/en-us/azure/azure-monitor/platform/activity-log).
Diese beiden Quellen sind Dienstbeschreibungen; die spaeter im selben Auftrag
gezielt gelesenen Konto-Metadaten und ihre Ergebnisse sind oben getrennt ausgewiesen.

Accountbezogene Vertrags-/Betriebsbelege und private Quellen stehen im
[Deploymentprotokoll](DEPLOYMENT-2026-09-19.md#concrete-privacy-review).
Codeabgleich: [Versand](../../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodAnalysisService.swift),
[Bildaufbereitung](../../ios/FoodAnalysisKit/Sources/FoodAnalysisKit/FoodImagePreprocessor.swift),
[Review/Speichern](../../ios/Trainingsplan/FoodAnalysisReviewView.swift),
[Backup](../../ios/Trainingsplan/BackupService.swift),
[MSAL](../../ios/Trainingsplan/Entra/MSALEntraTokenAcquirer.swift),
[Gatewaytransport](../../backend/gateway_client.py) und
[Providerparameter](../../ai-gateway/app/providers/openai_api.py).