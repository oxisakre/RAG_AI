# Sanoanimal Therapeutencheck — Projektzusammenfassung

**Datum:** 20. April 2026  
**Erstellt für:** Kontexttransfer in neuen Chat  
**Projekt-Owner:** Carsten Fritz, Managing Director OKAPI Gruppe  

---

## 1. Projektübersicht

### Was gebaut wird
Eine **Standalone-Web-App (PWA)** für Sanoanimal-Therapeuten, die veterinärpharmakologische Abfragen ermöglicht — mit dem Alleinstellungsmerkmal, dass **Praxis-Evidenz aus dem Therapeuten-Netzwerk** (nicht Pharma-Marketing) die Basis der Antworten bildet.

### Strategische Einordnung
Die App wird als eigenständiger Funktionsbereich in die **Sanoanimal Toolbox** integriert (neben BASIC und PRO). In der Fußzeile wählt der Nutzer zwischen BASIC, PRO und dem Pharma-/Arzneimittel-Bereich (Name noch offen — Arbeitstitel: "PharmCheck", "VetCheck", "Arzneimittel-Check"). Mobile-first, PWA-Architektur.

### Zielgruppe
- ~600 Sanoanimal-Therapeuten (Pferdetherapeutinnen, Tierheilpraktiker)
- ~140 aktive TH-Partner DACH
- Perspektivisch: Tierärzte im Sanoanimal-Netzwerk

---

## 2. Architektur-Entscheidungen

### Zwei-Quellen-Antwort-System
Jede Antwort im Therapeutencheck besteht aus zwei visuell getrennten Blöcken:

1. **Grüner Block "Sanoanimal Praxis-Einordnung"** — Praxis-Evidenz aus dem Therapeuten-Netzwerk (Layer 1)
2. **Blauer Block "Fakten — CliniPharm / Wissenschaftliche Literatur"** — Wissenschaftliche Fakten (Layer 2+3)

### Grund für dieses Design
Carsten hat die berechtigte Sorge, dass KI-basierte Medikamenteninformationen von Pharma-Marketing durchsetzt sind. Das Zwei-Quellen-System stellt sicher, dass die Sanoanimal-eigene Praxiserfahrung immer Vorrang hat vor generischem Internet-Wissen.

### RAG-Architektur (3 Layer)
- **Layer 1 — Therapeuten-Praxiswissen:** Bewertungen von Therapeuten/Tierärzten mit Name, Freitext, Patientenakte-Link (Quadrian), Ratings
- **Layer 2 — Kuratierte Web-Quellen:** CliniPharm/CliniTox UZH, EMA-Zulassungstexte, Peer-reviewed Journals, ECEIM/AAEP Consensus
- **Layer 3 — Strukturierte Faktendaten:** Dosierungen, HWZ, Metabolismus als deterministische Datensätze

### Technologie-Stack
- **Datenbank:** PostgreSQL mit pgvector Extension (passt zum bestehenden Quadrian-Stack)
- **Embeddings:** Voyage AI oder OpenAI text-embedding-3-large
- **Reasoning:** Claude API als LLM-Layer für Antwortgenerierung
- **Frontend:** PWA (Progressive Web App), mobile-first
- **Deployment:** Quadrian-Infrastruktur (AWS Frankfurt gemäß bestehender Spezifikation)

---

## 3. Erarbeitete Datenbanken (6 Excel-Dateien)

### 3.1 Medikamenten-DB (`pferde_arzneimittel_v3.xlsx`)
- **51 Medikamente × 14 Spalten**
- Spalten: Zulassungsstatus, Handelsname, Wirkstoff, Dosierung (Pferd), Applikationsweg, Anwendung, Wirkung, Nebenwirkungen, Kreuzreaktionen, Kontraindikationen (rot), Wartezeit, Rezeptpflicht, FEI-Absetzfristen, Quelle
- Kategorien: NSAID, Kortikosteroide, Antibiotika, Antiparasitika, Sedativa/Anästhetika, GI-Trakt, Sonstige
- Farbkodierung: Creme=Original (19 aus Starter-DB), Hellgrün=Ergänzungen, Orange=Umwidmungen (Kaskadenrecht)
- **Basis:** Starter-DB von Carsten (19 Einträge) + 32 wissenschaftlich fundierte Ergänzungen
- **Quellen:** EMA-Zulassungstexte, CliniPharm UZH, Plumb's — bewusst KEIN Hersteller-Marketing

### 3.2 Giftpflanzen-DB V2 (`giftpflanzen_equiden_v2.xlsx`)
- **29 Pflanzen × 19 Spalten**
- NEU in V2: Spalte "Evidenz beim Pferd" (GESICHERT/MÄSSIG/GERING) + Spalte "Dokumentierte Fälle" mit Literaturverweisen
- 17 Pflanzen mit GESICHERTER equiner Evidenz, 5 MÄSSIG, 5 GERING (transparent gekennzeichnet als extrapoliert)
- Besonders praxisrelevant: Spalte "Giftig im Heu/Silage?" — JKK, Herbstzeitlose, Sumpfschachtelhalm, Adlerfarn sind im Heu GEFÄHRLICHER als frisch
- **Selbstkritik:** Einige Pflanzen (Efeu, Adonisröschen, Maiglöckchen, Rosskastanie, Zaunwicke) haben limitierte equine Evidenz → mit TRANSPARENZHINWEIS versehen

### 3.3 Wirkstoff-DB V2 (`wirkstoffe_equiden_v2.xlsx`)
- **22 Wirkstoffe × 14 Spalten + CYP-Enzym-Tab (6 Einträge)**
- Alle Pharmakokinetik-Daten sind PFERDESPEZIFISCH (nicht aus Humanmedizin extrapoliert)
- Kernspalte: "Pferdespezifische Besonderheiten" — Informationen die in keinem Human-Lehrbuch stehen
- **CYP-Enzym-Tab:** CYP3A (6 equine Isoenzyme), CYP2C, CYP2D, CYP1A, CYP2E, P-Glykoprotein
- Key Insights: Omeprazol beim Pferd über CYP3A (nicht CYP2C19 wie beim Mensch); Tramadol wirkt beim Pferd NICHT (CYP2D-Defizit); P-gp an BHS schützt vor Ivermectin-Neurotoxizität

### 3.4 Wechselwirkungen-Matrix V2 (`wechselwirkungen_equiden_db_v2.xlsx`)
- **61 Interaktionen in 4 Sheets:**
  - Sheet 1: Wirkstoff × Wirkstoff (22 Interaktionen)
  - Sheet 2: Wirkstoff × Futtermittel (8 Interaktionen)
  - Sheet 3: Wirkstoff × Erkrankung (9 Interaktionen)
  - **Sheet 4: OKAPI Produkte × Medikament (22 Interaktionen) — ALLEINSTELLUNGSMERKMAL**
- Schweregrad-Kodierung: KONTRAINDIZIERT (rot), SCHWERWIEGEND (orange), KLINISCH RELEVANT (gelb), MONITORING (blau), GÜNSTIG (grün)
- OKAPI-Tab deckt ab: Teufelskralle, Weidenrinde, Magnesium, Calcium, Eisen, Zink, Mariendistel, Leinsamen/Leinöl, Bierhefe, Mönchspfeffer, Ingwer, MSM, Flohsamen, Schwarzkümmelöl
- Inkl. FEI-Dopingrelevanz für OKAPI-Produkte (Teufelskralle + Weidenrinde = FEI-verboten!)
- Spalte "Sanoanimal-Praxisrelevanz" (HOCH/MÄSSIG/GERING) — 10 von 22 = HOCH

### 3.5 Indikationen-Therapie-Matrix (`indikationen_therapie_matrix.xlsx`)
- **13 Indikationen × 13 Spalten**
- Abgedeckt: Akute Lahmheit, Chronische Arthrose, EGUS squamös, EGUS glandulär (getrennt!), Akute Kolik, Equines Asthma, PPID, EMS, Atemwegsinfektion, Druse, Endoparasiten, Photosensibilisierung, Stehende Sedation
- Pro Indikation: First-Line + Dosierung, Second-Line, Begleittherapie, OKAPI-Produkte, Kontraindikationen, Monitoring, Prognose
- OKAPI-Spalte gibt pro Indikation konkrete Produktempfehlungen UND Warnungen

### 3.6 PostgreSQL-Schema (`therapeutencheck_schema.sql`)
- **724 Zeilen SQL, production-ready**
- 10 Tabellen, 3 ENUM-Typen, 34 Indexes (inkl. pgvector IVFFlat), 5 Views, 2 Funktionen, 1 Trigger
- Tabellen: wirkstoffe, medikamente, giftpflanzen, wechselwirkungen, kontraindikationen (16 Initialdaten), indikationen, therapeuten, praxisbewertungen, kuratierte_quellen, abfrage_log
- `search_all_knowledge()` — Funktion die mit einem Vektor-Query ALLE Tabellen durchsucht
- Trigger für automatische Level-Berechnung (Bronze→Silber→Gold→Platin)
- Views: absolute Kontraindikationen, OKAPI-Interaktionen, aggregierte Praxisbewertungen, Giftpflanzen im Heu

---

## 4. UI-Prototypen (2 HTML-Dateien)

### 4.1 Therapeutencheck (`therapeutencheck.html`)
- Chat-Interface mit Zwei-Quellen-Antwortdesign (grüner Praxis-Block + blauer Fakten-Block)
- Sidebar: Schnellsuche, Kategorien (Medikamente, Wirkstoffe, Giftpflanzen, Wechselwirkungen, Indikationen, Kontraindikationen)
- Hint-Chips, Verlaufshistorie, Confidence-Indikatoren
- Sanoanimal-Designsprache (dunkles Grün, Gold-Akzente, Playfair Display)

### 4.2 Medikamenten-Bewertungs-App (`medikamenten-bewertung.html`)
- 50 Medikamente als Karten mit Wirksamkeit/Verträglichkeit/Empfehlung-Ratings
- Modal mit existierenden Erfahrungsberichten + Bewertungsformular
- **Anreizsystem / Gamification:**
  - Contributor-Dashboard mit Level (Bronze→Silber→Gold→Platin)
  - Fortschrittsbalken ("13/20 Bewertungen → Gold-Status")
  - Freischaltbare Belohnungen (Vollzugang Wechselwirkungen-DB, Experten-Badge im Therapeuten-Finder)
  - Quadrian Micro-Prompt ("Du hast Metacam eingesetzt. Kurze Bewertung? ~30 Sek.")
  - XP-Feedback nach Abgabe

---

## 5. Offene Punkte / Entscheidungen

### 5.1 Name für den Funktionsbereich
Arbeitstitel: "PharmCheck", "VetCheck", "Arzneimittel-Check" — muss noch finalisiert werden

### 5.2 Integration in Sanoanimal Toolbox
- BASIC / PRO / [Pharma-Bereich] als Fußzeilen-Navigation
- Mobile-first PWA
- Sanoanimal Toolbox-Spezifikation (Pro + Basic) existiert bereits aus früherem Chat

### 5.3 Rechtliche Absicherung
- Medien-/Pharmarecht-Anwalt für Nutzungsbedingungen, Content-Richtlinien, Haftungsfreistellung
- Budget: ca. 2.000–4.000 €
- Muss VOR öffentlichem Launch erledigt sein
- Praxis-Erfahrungsberichte = geschützter als "Bewertungen"; namentliche Beitragende = besserer Rechtsschutz als anonym

### 5.4 Inhaltliche Validierung
- Christina / Fachteam muss alle 6 Datenbanken fachlich prüfen
- Priorität: Dosierungsangaben, Giftpflanzen-Evidenz, OKAPI-Interaktionen, Indikationen-Matrix
- KEIN optionaler Schritt — Grundlage für klinische Empfehlungen

### 5.5 Noch zu erarbeitende Inhalte
- Indikationen-Matrix erweitern: Hufrehe (akut/chronisch), Wundversorgung, Augenheilkunde (Uveitis, Ulkus), Reproduktion, Fohlen-spezifisch, Zahnheilkunde
- Kontraindikationen-Matrix: 16 Einträge als Initialdaten im Schema — muss erweitert werden
- Giftpflanzen: Pflanzenbilder, regionale Verbreitungskarten, monatlicher Gefährdungskalender

---

## 6. Nächste Schritte (Priorisiert)

| # | Schritt | Wer | Zeitrahmen |
|---|---------|-----|------------|
| 1 | Fachliche Validierung der 6 Datenbanken | Christina / Fachteam | 1–2 Wochen |
| 2 | Technisches Briefing an Leo (Quadrian) | Carsten → Leo | Sofort |
| 3 | PostgreSQL-Schema deployen + pgvector | Leo / Quadrian | 2–4 Wochen |
| 4 | Datenimport-Skript (Excel → PostgreSQL) | Leo | 1–2 Tage |
| 5 | Embedding-Pipeline (Voyage/OpenAI) | Leo | 2–3 Tage |
| 6 | Therapeutencheck MVP (UI + RAG-Backend) | Leo / Quadrian | 4–8 Wochen |
| 7 | Bewertungs-App Closed Beta (10–15 THs) | Carsten + Christina | Parallel zu 6 |
| 8 | Rechtliche Absicherung (Anwalt) | Carsten | Vor Go-Live |
| 9 | Toolbox-Integration (BASIC/PRO/Pharma) | Leo | Nach MVP |

---

## 7. Dateien-Übersicht (alle in /mnt/user-data/outputs/)

| Datei | Typ | Inhalt |
|-------|-----|--------|
| `therapeutencheck.html` | UI-Prototyp | Chat-Interface mit Zwei-Quellen-Design |
| `medikamenten-bewertung.html` | UI-Prototyp | Bewertungs-App mit Gamification |
| `pferde_arzneimittel_v3.xlsx` | Datenbank | 51 Medikamente, 14 Spalten |
| `giftpflanzen_equiden_v2.xlsx` | Datenbank | 29 Giftpflanzen, 19 Spalten, mit Evidenz |
| `wirkstoffe_equiden_v2.xlsx` | Datenbank | 22 Wirkstoffe + CYP-Enzyme, 14 Spalten |
| `wechselwirkungen_equiden_db_v2.xlsx` | Datenbank | 61 Interaktionen, 4 Sheets inkl. OKAPI |
| `indikationen_therapie_matrix.xlsx` | Datenbank | 13 Indikationen, 13 Spalten |
| `therapeutencheck_schema.sql` | DB-Schema | PostgreSQL + pgvector, 724 Zeilen, 10 Tabellen |

---

## 8. Quellenphilosophie (durchgängig)

**Bevorzugte Quellen:** CliniPharm/CliniTox UZH, EMA-Zulassungstexte, Plumb's Veterinary Drug Handbook, Peer-reviewed Journals (JEVS, EVJ, JAVMA, JVIM), ECEIM/AAEP/ACVIM Consensus Statements, BfR/EFSA-Stellungnahmen.

**Bewusst NICHT als Primärquelle:** Hersteller-Marketing, SEO-optimierte Websites, Pharma-Beipackzettel ohne wissenschaftliche Einordnung.

**Alle PK-Daten sind pferdespezifisch** — keine Extrapolation aus Humanmedizin oder anderen Tierarten ohne Kennzeichnung.
