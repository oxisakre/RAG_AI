
-- ═══════════════════════════════════════════════════════════════════
-- SANOANIMAL THERAPEUTENCHECK — PostgreSQL Schema V1
-- Datenstand: 20.04.2026
-- Zweck: RAG-Fakten-Layer für den Therapeutencheck
-- Technologie: PostgreSQL 15+ mit pgvector Extension
-- ═══════════════════════════════════════════════════════════════════

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";           -- Vektor-Embeddings für RAG
CREATE EXTENSION IF NOT EXISTS "pg_trgm";            -- Trigramm-Suche für Fuzzy-Match

-- ─────────────────────────────────────────────────────────────────
-- SCHEMA: therapeutencheck
-- ─────────────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS therapeutencheck;
SET search_path TO therapeutencheck, public;


-- ═══════════════════════════════════════════════════════════════════
-- 1. WIRKSTOFFE (Fakten-Layer: wissenschaftliche Wirkstoff-Daten)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE wirkstoffe (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wirkstoff_inn       TEXT NOT NULL UNIQUE,          -- INN-Name (z.B. "Phenylbutazon")
    wirkstoffklasse     TEXT NOT NULL,                 -- z.B. "Pyrazolon-Derivat"
    therapeutische_kategorie TEXT NOT NULL,             -- z.B. "NSAID / Analgetikum"
    wirkmechanismus     TEXT NOT NULL,                 -- Pferdespezifisch
    
    -- Pharmakokinetik PFERD
    bioverfuegbarkeit_oral TEXT,                       -- z.B. "~95%"
    hwz_plasma          TEXT,                          -- z.B. "3,5–10 h"
    verteilungsvolumen  TEXT,                          -- z.B. "0,14–0,2 L/kg"
    metabolismus        TEXT,                          -- z.B. "Hepatisch (CYP2C)"
    elimination         TEXT,                          -- z.B. "Renal"
    therapeutischer_index TEXT,                         -- "HOCH / MÄSSIG / GERING"
    
    -- Pferdespezifisch
    pferd_besonderheiten TEXT NOT NULL,                 -- Kerninhalt: was ist beim Pferd anders?
    cyp_enzyme          TEXT[],                        -- Array: ["CYP2C", "CYP3A"]
    pgp_substrat        BOOLEAN DEFAULT FALSE,         -- P-Glykoprotein-Substrat?
    
    -- Zugelassene Präparate
    zugelassene_praeparate TEXT[],                     -- Array: ["Equipalazone", "Phenylarthrite"]
    umwidmungs_praeparate  TEXT[],                     -- Array: ["Generika xy"]
    
    -- Quellen & Embedding
    quellen             TEXT[],
    embedding           vector(1536),                  -- OpenAI/Voyage Embedding
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_wirkstoffe_embedding ON wirkstoffe 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);
CREATE INDEX idx_wirkstoffe_klasse ON wirkstoffe (therapeutische_kategorie);
CREATE INDEX idx_wirkstoffe_trgm ON wirkstoffe 
    USING gin (wirkstoff_inn gin_trgm_ops);


-- ═══════════════════════════════════════════════════════════════════
-- 2. MEDIKAMENTE (Handelspräparate, verlinkt mit Wirkstoffen)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE medikamente (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    handelsname         TEXT NOT NULL,
    wirkstoff_id        UUID NOT NULL REFERENCES wirkstoffe(id),
    zulassungsstatus    TEXT NOT NULL CHECK (zulassungsstatus IN (
                            'Tierarzneimittel zugelassen',
                            'Umwidmung (Humanarzneimittel)',
                            'Umwidmung (Tierarzneimittel andere Spezies)'
                        )),
    
    -- Dosierung & Applikation PFERD
    dosierung_pferd     TEXT NOT NULL,                 -- Exakte mg/kg-Angaben
    applikationsweg     TEXT NOT NULL,                 -- p.o., i.v., i.m., etc.
    anwendung           TEXT NOT NULL,                 -- Indikationstext
    wirkung             TEXT NOT NULL,                 -- Wirkungsbeschreibung
    nebenwirkungen      TEXT NOT NULL,
    kreuzreaktionen     TEXT,
    
    -- Regulatorisch
    wartezeit           TEXT,                          -- Fleisch/Milch
    rezeptpflicht       TEXT NOT NULL,                 -- "Ja (Rx)", "Ja (BTM)", etc.
    fei_dopingstatus    TEXT,                          -- FEI-Absetzfristen
    
    -- Quellen & Embedding
    quelle_url          TEXT,
    quellen             TEXT[],
    embedding           vector(1536),
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_medikamente_wirkstoff ON medikamente (wirkstoff_id);
CREATE INDEX idx_medikamente_embedding ON medikamente 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX idx_medikamente_trgm ON medikamente 
    USING gin (handelsname gin_trgm_ops);


-- ═══════════════════════════════════════════════════════════════════
-- 3. GIFTPFLANZEN
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE giftpflanzen (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deutscher_name      TEXT NOT NULL,
    botanischer_name    TEXT NOT NULL,
    familie             TEXT NOT NULL,
    giftigkeitsstufe    TEXT NOT NULL CHECK (giftigkeitsstufe IN (
                            'TÖDLICH', 'STARK', 'MÄSSIG', 'GERING'
                        )),
    
    -- Evidenz beim Pferd
    evidenz_pferd       TEXT NOT NULL CHECK (evidenz_pferd IN (
                            'GESICHERT', 'MÄSSIG', 'GERING'
                        )),
    dokumentierte_faelle TEXT,                          -- Literaturverweise equine Fälle
    
    -- Toxikologie
    toxin_wirkstoff     TEXT NOT NULL,
    toxische_teile      TEXT NOT NULL,
    wirkmechanismus     TEXT NOT NULL,
    symptome_pferd      TEXT NOT NULL,
    letale_dosis        TEXT,
    latenzzeit          TEXT,
    
    -- Therapie
    therapie            TEXT NOT NULL,
    prognose            TEXT NOT NULL,
    
    -- Ökologie
    vorkommen_dach      TEXT NOT NULL,
    saisonale_gefaehrdung TEXT NOT NULL,
    giftig_im_heu       TEXT NOT NULL,                 -- "JA" / "NEIN" / "Teilweise"
    verwechslungsgefahr  TEXT,
    
    -- Embedding & Quellen
    quellen             TEXT[],
    embedding           vector(1536),
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_giftpflanzen_embedding ON giftpflanzen 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);
CREATE INDEX idx_giftpflanzen_stufe ON giftpflanzen (giftigkeitsstufe);
CREATE INDEX idx_giftpflanzen_evidenz ON giftpflanzen (evidenz_pferd);
CREATE INDEX idx_giftpflanzen_heu ON giftpflanzen ((giftig_im_heu));
CREATE INDEX idx_giftpflanzen_trgm ON giftpflanzen 
    USING gin (deutscher_name gin_trgm_ops);


-- ═══════════════════════════════════════════════════════════════════
-- 4. WECHSELWIRKUNGEN (normalisiert, maschinenlesbar)
-- ═══════════════════════════════════════════════════════════════════

CREATE TYPE interaktions_typ AS ENUM (
    'wirkstoff_wirkstoff',
    'wirkstoff_futtermittel',
    'wirkstoff_erkrankung',
    'okapi_produkt_wirkstoff'
);

CREATE TYPE schweregrad AS ENUM (
    'KONTRAINDIZIERT',
    'SCHWERWIEGEND',
    'KLINISCH_RELEVANT',
    'MONITORING',
    'GUENSTIG'
);

CREATE TABLE wechselwirkungen (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    interaktions_typ    interaktions_typ NOT NULL,
    schweregrad         schweregrad NOT NULL,
    
    -- Interaktionspartner (flexibel: kann Wirkstoff, Futter, Erkrankung, OKAPI-Produkt sein)
    partner_a_typ       TEXT NOT NULL,                 -- "wirkstoff", "medikament", "futter", "erkrankung", "okapi_produkt"
    partner_a_name      TEXT NOT NULL,                 -- z.B. "Phenylbutazon"
    partner_a_id        UUID,                          -- FK zu wirkstoffe oder medikamente (optional)
    
    partner_b_typ       TEXT NOT NULL,
    partner_b_name      TEXT NOT NULL,
    partner_b_id        UUID,
    
    -- Inhalt
    mechanismus         TEXT NOT NULL,
    klinische_konsequenz TEXT NOT NULL,
    empfehlung          TEXT NOT NULL,
    evidenz             TEXT NOT NULL,
    
    -- OKAPI-spezifisch
    sanoanimal_praxisrelevanz TEXT CHECK (sanoanimal_praxisrelevanz IN ('HOCH', 'MÄSSIG', 'GERING')),
    
    -- Embedding & Quellen
    quellen             TEXT[],
    embedding           vector(1536),
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_ww_typ ON wechselwirkungen (interaktions_typ);
CREATE INDEX idx_ww_schwere ON wechselwirkungen (schweregrad);
CREATE INDEX idx_ww_partner_a ON wechselwirkungen (partner_a_name);
CREATE INDEX idx_ww_partner_b ON wechselwirkungen (partner_b_name);
CREATE INDEX idx_ww_embedding ON wechselwirkungen 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX idx_ww_praxis ON wechselwirkungen (sanoanimal_praxisrelevanz);


-- ═══════════════════════════════════════════════════════════════════
-- 5. KONTRAINDIKATIONEN (dedizierte, maschinenlesbare Tabelle)
--    → beantwortet: "Alle Wirkstoffe die bei Erkrankung X verboten sind"
--    → beantwortet: "Alle Erkrankungen bei denen Wirkstoff Y verboten ist"
-- ═══════════════════════════════════════════════════════════════════

CREATE TYPE kontra_schwere AS ENUM (
    'ABSOLUT',            -- Niemals geben (z.B. Kortikosteroide bei EMS → Hufrehe)
    'RELATIV',            -- Nur unter strenger Indikation/Monitoring
    'VORSICHT'            -- Dosisanpassung / engmaschiges Monitoring nötig
);

CREATE TABLE kontraindikationen (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wirkstoff_id        UUID REFERENCES wirkstoffe(id),
    wirkstoff_name      TEXT NOT NULL,                 -- Redundant für schnelle Abfragen
    wirkstoffklasse     TEXT,                          -- z.B. "Alle NSAID" oder "Alle Kortikosteroide"
    
    erkrankung_zustand  TEXT NOT NULL,                 -- z.B. "EMS", "PPID", "Dehydratation", "Fohlen <4 Monate"
    erkrankung_kategorie TEXT,                          -- z.B. "Endokrinologie", "Nephrologie", "Alter/Entwicklung"
    
    schwere             kontra_schwere NOT NULL,
    begruendung         TEXT NOT NULL,                 -- Warum kontraindiziert?
    konsequenz          TEXT NOT NULL,                 -- Was passiert bei Missachtung?
    alternative         TEXT,                          -- Welcher Wirkstoff stattdessen?
    
    evidenz             TEXT NOT NULL CHECK (evidenz IN ('GESICHERT', 'MÄSSIG', 'GERING')),
    quellen             TEXT[],
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_kontra_wirkstoff ON kontraindikationen (wirkstoff_name);
CREATE INDEX idx_kontra_erkrankung ON kontraindikationen (erkrankung_zustand);
CREATE INDEX idx_kontra_schwere ON kontraindikationen (schwere);
CREATE INDEX idx_kontra_klasse ON kontraindikationen (wirkstoffklasse);

-- Initialdaten aus bestehenden DBs
INSERT INTO kontraindikationen (wirkstoff_name, wirkstoffklasse, erkrankung_zustand, erkrankung_kategorie, schwere, begruendung, konsequenz, alternative, evidenz, quellen)
VALUES
    ('Dexamethason', 'Kortikosteroide (alle systemisch)', 'EMS / Insulindysregulation', 'Endokrinologie', 'ABSOLUT',
     'Kortikosteroide induzieren Insulinresistenz → Hyperinsulinämie → digitale Lamellarschädigung',
     'Akute Hufrehe — PFERDESPEZIFISCHES Risiko',
     'Prednisolon (weniger potent, besser steuerbar) oder NSAID mit Magenschutz',
     'GESICHERT', ARRAY['Johnson PJ 2002', 'Cornelisse CJ 2004', 'ECEIM Consensus']),
     
    ('Dexamethason', 'Kortikosteroide (alle systemisch)', 'PPID (Equines Cushing)', 'Endokrinologie', 'ABSOLUT',
     'PPID-Pferde haben bereits gestörte Insulinregulation → Kortikosteroide verschärfen Hufrehe-Risiko dramatisch',
     'Akute Hufrehe, Verschlechterung aller PPID-Symptome',
     'Pergolid-Dosisanpassung; bei Entzündung: NSAID mit Magenschutz',
     'GESICHERT', ARRAY['Durham AE', 'McFarlane D', 'ECEIM Consensus']),
     
    ('Dexamethason', 'Kortikosteroide (alle systemisch)', 'Laminitis-Vorgeschichte', 'Bewegungsapparat', 'ABSOLUT',
     'Jede Kortikosteroid-Exposition kann bei prädisponierten Pferden Hufrehe-Schub auslösen — auch intraartikulär!',
     'Rezidiv einer akuten Hufrehe',
     'NSAID (Meloxicam/Firocoxib) mit Magenschutz; Teufelskralle als Phytotherapie',
     'GESICHERT', ARRAY['Johnson PJ 2002', 'Cornelisse CJ 2004']),
     
    ('Triamcinolonacetonid', 'Kortikosteroide (intraartikulär)', 'EMS / PPID / Laminitis-Vorgeschichte', 'Endokrinologie', 'ABSOLUT',
     'Intraartikuläres Triamcinolon wird systemisch resorbiert → Hufrehe auch nach Gelenkinjektion dokumentiert',
     'Akute Hufrehe trotz lokaler Applikation — häufig unterschätzt!',
     'Hyaluronsäure intraartikulär; NSAID systemisch; Adequan (PSGAG)',
     'GESICHERT', ARRAY['Frisbie DD', 'McIlwraith CW']),
    
    ('Phenylbutazon', 'NSAID (alle)', 'GI-Ulzera (EGUS)', 'GI-Trakt', 'RELATIV',
     'NSAID hemmen protektive Prostaglandine → Ulkusverschlechterung; Phenylbutazon am schlechtesten GI-verträglich',
     'Progression bestehender Ulzera bis Perforation',
     'Firocoxib (COX-2-selektiv, GI-schonender) + obligater Omeprazol-Magenschutz',
     'GESICHERT', ARRAY['Andrews FM', 'ECEIM Consensus EGUS']),

    ('Phenylbutazon', 'NSAID (alle)', 'Niereninsuffizienz', 'Nephrologie', 'ABSOLUT',
     'NSAID hemmen renale Prostaglandine → verminderte Nierendurchblutung → papilläre Nekrose',
     'Akutes Nierenversagen',
     'Metamizol (spasmolytisch, weniger nephrotoxisch) oder Butorphanol (Opioid)',
     'GESICHERT', ARRAY['MacAllister CG', 'Plumbs']),
     
    ('Phenylbutazon', 'NSAID (alle)', 'Dehydratation / Hypovolämie', 'Intensivmedizin', 'ABSOLUT',
     'NSAID + Dehydratation = synergistische Nephrotoxizität (Triple-Hit bei Kolik)',
     'Akutes Nierenversagen',
     'ZUERST Flüssigkeitstherapie (Ringer-Laktat i.v.), DANN Analgesie',
     'GESICHERT', ARRAY['MacAllister CG', 'Read WK']),
     
    ('Acepromazin', NULL, 'Schock / Hypovolämie / Kolik', 'Intensivmedizin', 'ABSOLUT',
     'Alpha-1-Blockade → periphere Vasodilatation → schwere Hypotension bei kompromittiertem Kreislauf',
     'Kardiovaskulärer Kollaps, Tod',
     'Detomidin oder Xylazin (Alpha-2-Agonisten; ebenfalls kreislaufwirksam aber besser steuerbar, antagonisierbar)',
     'GESICHERT', ARRAY['Muir WW', 'Hubbell JAE']),
     
    ('Acepromazin', NULL, 'PPID unter Pergolid-Therapie', 'Endokrinologie', 'ABSOLUT',
     'Acepromazin = Dopamin-D2-Antagonist → antagonisiert Pergolid (D2-Agonist) direkt',
     'Verlust der PPID-Kontrolle; ACTH-Anstieg',
     'Detomidin, Xylazin, Romifidin (keine Dopamin-Antagonisten)',
     'GESICHERT', ARRAY['Durham AE', 'McFarlane D']),
     
    ('Enrofloxacin', 'Fluorchinolone (alle)', 'Wachsende Pferde (<2 Jahre)', 'Alter/Entwicklung', 'ABSOLUT',
     'Fluorchinolone hemmen DNA-Gyrase → toxischer Effekt auf Chondrozyten → irreversible Arthropathie',
     'Gelenkknorpelzerstörung, Lahmheit, irreversible Wachstumsstörungen',
     'TMP-Sulfonamid; Penicillin; Ceftiofur (nach Antibiogramm)',
     'GESICHERT', ARRAY['Yoon JH 2004', 'EMA CVMP']),
     
    ('Moxidectin', NULL, 'Fohlen <6,5 Monate', 'Alter/Entwicklung', 'ABSOLUT',
     'BHS bei Fohlen <6,5 Monate noch unreif → Moxidectin (hochlipophil) penetriert ins ZNS → schwere Neurotoxizität',
     'ZNS-Depression, Ataxie, Koma, Tod',
     'Ivermectin (ab 4 Monate; breitere therapeutische Breite) oder Fenbendazol',
     'GESICHERT', ARRAY['Fachinformation Equest', 'Plumbs']),
     
    ('Ivermectin', NULL, 'Fohlen <4 Monate', 'Alter/Entwicklung', 'VORSICHT',
     'P-gp an BHS noch nicht voll ausgereift → erhöhte ZNS-Penetration; geringere therapeutische Breite als bei adulten Pferden',
     'ZNS-Depression möglich; in Standarddosis meist sicher, aber engmaschig beobachten',
     'Fenbendazol (sicherste Option bei Fohlen); exakte Gewichtsbestimmung obligat',
     'GESICHERT', ARRAY['Olsén L 2007', 'Plumbs']),
     
    ('Misoprostol', NULL, 'Trächtigkeit', 'Reproduktion', 'ABSOLUT',
     'PGE1-Analogon → stimuliert Uteruskontraktion → Abort; auch bei niedrigen Dosen nicht ausgeschlossen',
     'Abort',
     'Omeprazol + Sucralfat für Magenulzera; KEIN Misoprostol bei trächtigen Stuten unter KEINEN Umständen',
     'GESICHERT', ARRAY['Plumbs', 'Fachinformation Misoprostol']),
     
    ('Metronidazol', NULL, 'Trächtigkeit', 'Reproduktion', 'RELATIV',
     'Teratogen im Tierversuch (Nager); beim Pferd keine equinen Teratogenitätsstudien, aber Vorsichtsprinzip',
     'Theoretisches Fehlbildungsrisiko; nicht gesichert beim Pferd',
     'Penicillin (bei Anaerobier-Verdacht: Penicillin + Metronidazol nur wenn lebensbedrohlich)',
     'MÄSSIG', ARRAY['Plumbs']),
     
    ('Atropin (systemisch)', NULL, 'Kolik / Ileus-Verdacht', 'GI-Trakt', 'RELATIV',
     'Atropin → Darmatonie; beim Pferd extreme GI-Empfindlichkeit gegenüber Anticholinergika → Kolikgefahr 24-48h nach systemischer Gabe',
     'Schwere Kolik durch iatrogene Darmatonie',
     'Bei Bradykardie: engmaschiges Monitoring statt sofortiger Atropingabe; ophthalmologisch: Tropicamid (kürzer wirksam)',
     'GESICHERT', ARRAY['Brooks DE', 'Muir WW']),
     
    ('Clenbuterol', NULL, 'Herzerkrankungen / Tachyarrhythmien', 'Kardiologie', 'ABSOLUT',
     'Beta-2-Agonist → Tachykardie; bei vorbestehenden Herzerkrankungen Arrhythmie-Risiko',
     'Schwere Tachyarrhythmie, potenziell fatal',
     'Ipratropiumbromid inhalativ (Anticholinergikum, keine kardiale Stimulation)',
     'MÄSSIG', ARRAY['Cole C et al.', 'Plumbs']);


-- ═══════════════════════════════════════════════════════════════════
-- 6. INDIKATIONEN-THERAPIE-MATRIX
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE indikationen (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    indikation          TEXT NOT NULL,                 -- z.B. "Akute Lahmheit"
    organsystem         TEXT NOT NULL,                 -- z.B. "Bewegungsapparat"
    schweregrad         TEXT NOT NULL,                 -- "Akut", "Chronisch", "Notfall"
    
    -- Therapieoptionen
    first_line_therapie TEXT NOT NULL,
    first_line_wirkstoff TEXT NOT NULL,                 -- Dosierung inkl.
    second_line         TEXT,
    begleittherapie     TEXT,
    okapi_produkte      TEXT,                          -- OKAPI/Phytotherapie-Empfehlungen
    kontraindizierte_ws TEXT NOT NULL,                 -- Was NICHT geben
    
    -- Monitoring & Prognose
    monitoring          TEXT NOT NULL,
    prognose            TEXT NOT NULL,
    
    -- Embedding & Quellen
    evidenz             TEXT NOT NULL,
    quellen             TEXT[],
    embedding           vector(1536),
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_indikationen_embedding ON indikationen 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 20);
CREATE INDEX idx_indikationen_organ ON indikationen (organsystem);
CREATE INDEX idx_indikationen_trgm ON indikationen 
    USING gin (indikation gin_trgm_ops);


-- ═══════════════════════════════════════════════════════════════════
-- 7. THERAPEUTEN-PRAXISBEWERTUNGEN (Layer 1: Praxis-Evidenz)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE therapeuten (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name                TEXT NOT NULL,                 -- Quellennachweis
    rolle               TEXT NOT NULL CHECK (rolle IN (
                            'Tierärztin/Tierarzt',
                            'Pferdetherapeutin/-therapeut',
                            'Tierheilpraktiker/in'
                        )),
    praxis_klinik       TEXT,
    
    -- Gamification / Anreizsystem
    bewertungen_count   INTEGER DEFAULT 0,
    level               TEXT DEFAULT 'Bronze' CHECK (level IN ('Bronze', 'Silber', 'Gold', 'Platin')),
    
    -- Quadrian-Integration
    quadrian_user_id    UUID,                          -- FK zu Quadrian Practice Software
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE praxisbewertungen (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    medikament_id       UUID REFERENCES medikamente(id),
    wirkstoff_id        UUID REFERENCES wirkstoffe(id),
    therapeut_id        UUID NOT NULL REFERENCES therapeuten(id),
    
    -- Bewertung
    wirksamkeit         SMALLINT NOT NULL CHECK (wirksamkeit BETWEEN 1 AND 5),
    vertraeglichkeit    SMALLINT NOT NULL CHECK (vertraeglichkeit BETWEEN 1 AND 5),
    empfehlung          SMALLINT NOT NULL CHECK (empfehlung BETWEEN 1 AND 5),
    
    erfahrungsjahre     TEXT,                          -- "<1", "1-3", "3-5", "5-10", ">10"
    erfahrungsbericht   TEXT NOT NULL,                 -- Freitext — wird als Vektor embeddet
    
    -- Patientenakte-Link (Quadrian-Integration)
    patientenakte_ref   TEXT,                          -- z.B. "Quadrian #PF-2026-0312"
    patientenakte_url   TEXT,                          -- Deep-Link in Quadrian
    
    -- Tags
    tags                TEXT[],                        -- ["GI-Probleme", "Nur kurzzeitig", etc.]
    
    -- Embedding für RAG
    embedding           vector(1536),                  -- Embedding des Erfahrungsberichts
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_bewertungen_medikament ON praxisbewertungen (medikament_id);
CREATE INDEX idx_bewertungen_wirkstoff ON praxisbewertungen (wirkstoff_id);
CREATE INDEX idx_bewertungen_therapeut ON praxisbewertungen (therapeut_id);
CREATE INDEX idx_bewertungen_embedding ON praxisbewertungen 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_bewertungen_tags ON praxisbewertungen USING gin (tags);


-- ═══════════════════════════════════════════════════════════════════
-- 8. KURATIERTE WEB-QUELLEN (Layer 2: wissenschaftliche Quellen)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE kuratierte_quellen (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    quelle_typ          TEXT NOT NULL CHECK (quelle_typ IN (
                            'CliniPharm_UZH',
                            'EMA_Zulassungstext',
                            'Peer_reviewed_Journal',
                            'Fachbuch',
                            'Guideline_Consensus',
                            'BfR_EFSA',
                            'FEI_Doping'
                        )),
    titel               TEXT NOT NULL,
    url                 TEXT,
    isbn                TEXT,
    autor               TEXT,
    jahr                INTEGER,
    
    -- Inhalt (für RAG)
    inhalt_text         TEXT,                          -- Extrahierter/zusammengefasster Text
    themen_tags         TEXT[],                        -- ["NSAID", "GI-Toxizität", "Pferd"]
    
    -- Embedding
    embedding           vector(1536),
    
    -- Qualitätsbewertung
    vertrauensstufe     TEXT DEFAULT 'Standard' CHECK (vertrauensstufe IN (
                            'Goldstandard',            -- Peer-reviewed, Consensus
                            'Standard',                -- Etablierte Quellen
                            'Supplementär'             -- Ergänzend, begrenzte Evidenz
                        )),
    
    -- Scraping-Status (für automatisierte Aktualisierung)
    letzte_aktualisierung TIMESTAMPTZ,
    scraping_aktiv      BOOLEAN DEFAULT FALSE,
    
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_quellen_embedding ON kuratierte_quellen 
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);
CREATE INDEX idx_quellen_typ ON kuratierte_quellen (quelle_typ);
CREATE INDEX idx_quellen_tags ON kuratierte_quellen USING gin (themen_tags);


-- ═══════════════════════════════════════════════════════════════════
-- 9. ABFRAGE-LOG (für Therapeutencheck-Verbesserung)
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE abfrage_log (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    therapeut_id        UUID REFERENCES therapeuten(id),
    abfrage_text        TEXT NOT NULL,                 -- Original-Frage des Therapeuten
    abfrage_embedding   vector(1536),                  -- Embedding der Frage
    
    -- RAG-Ergebnis
    verwendete_quellen  JSONB,                         -- Welche Tabellen/Einträge für Antwort genutzt
    antwort_text        TEXT,                          -- Generierte Antwort
    
    -- Feedback
    bewertung           SMALLINT CHECK (bewertung BETWEEN 1 AND 5),
    feedback_text       TEXT,
    
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_log_therapeut ON abfrage_log (therapeut_id);
CREATE INDEX idx_log_embedding ON abfrage_log 
    USING ivfflat (abfrage_embedding vector_cosine_ops) WITH (lists = 100);


-- ═══════════════════════════════════════════════════════════════════
-- 10. VIEWS für häufige Therapeutencheck-Abfragen
-- ═══════════════════════════════════════════════════════════════════

-- View: Alle ABSOLUTEN Kontraindikationen pro Wirkstoff
CREATE VIEW v_absolute_kontraindikationen AS
SELECT 
    wirkstoff_name,
    wirkstoffklasse,
    erkrankung_zustand,
    begruendung,
    konsequenz,
    alternative
FROM kontraindikationen
WHERE schwere = 'ABSOLUT'
ORDER BY wirkstoff_name, erkrankung_zustand;

-- View: Alle KONTRAINDIZIERTEN Wechselwirkungen
CREATE VIEW v_kontraindizierte_ww AS
SELECT 
    partner_a_name,
    partner_b_name,
    mechanismus,
    klinische_konsequenz,
    empfehlung
FROM wechselwirkungen
WHERE schweregrad = 'KONTRAINDIZIERT'
ORDER BY partner_a_name;

-- View: OKAPI-relevante Interaktionen
CREATE VIEW v_okapi_interaktionen AS
SELECT 
    partner_a_name AS okapi_produkt,
    partner_b_name AS medikament,
    schweregrad,
    mechanismus,
    empfehlung,
    sanoanimal_praxisrelevanz
FROM wechselwirkungen
WHERE interaktions_typ = 'okapi_produkt_wirkstoff'
ORDER BY sanoanimal_praxisrelevanz DESC, schweregrad;

-- View: Aggregierte Praxisbewertungen pro Medikament
CREATE VIEW v_medikament_praxisbewertung AS
SELECT 
    m.handelsname,
    w.wirkstoff_inn,
    COUNT(pb.id) AS bewertungen_anzahl,
    ROUND(AVG(pb.wirksamkeit), 1) AS avg_wirksamkeit,
    ROUND(AVG(pb.vertraeglichkeit), 1) AS avg_vertraeglichkeit,
    ROUND(AVG(pb.empfehlung), 1) AS avg_empfehlung
FROM medikamente m
JOIN wirkstoffe w ON m.wirkstoff_id = w.id
LEFT JOIN praxisbewertungen pb ON pb.medikament_id = m.id
GROUP BY m.handelsname, w.wirkstoff_inn
ORDER BY bewertungen_anzahl DESC;

-- View: Giftpflanzen die im Heu gefährlich sind
CREATE VIEW v_giftpflanzen_heu AS
SELECT 
    deutscher_name,
    botanischer_name,
    giftigkeitsstufe,
    toxin_wirkstoff,
    symptome_pferd,
    evidenz_pferd
FROM giftpflanzen
WHERE giftig_im_heu LIKE 'JA%'
ORDER BY 
    CASE giftigkeitsstufe 
        WHEN 'TÖDLICH' THEN 1 
        WHEN 'STARK' THEN 2 
        WHEN 'MÄSSIG' THEN 3 
        ELSE 4 
    END;


-- ═══════════════════════════════════════════════════════════════════
-- 11. FUNKTIONEN für RAG-Pipeline
-- ═══════════════════════════════════════════════════════════════════

-- Funktion: Similarity Search über ALLE Tabellen gleichzeitig
CREATE OR REPLACE FUNCTION search_all_knowledge(
    query_embedding vector(1536),
    match_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    source_table TEXT,
    source_id UUID,
    title TEXT,
    content TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    
    -- Wirkstoffe
    SELECT 'wirkstoffe'::TEXT, w.id, w.wirkstoff_inn, 
           w.pferd_besonderheiten,
           1 - (w.embedding <=> query_embedding) AS sim
    FROM wirkstoffe w
    WHERE w.embedding IS NOT NULL
      AND 1 - (w.embedding <=> query_embedding) > match_threshold
    
    UNION ALL
    
    -- Medikamente
    SELECT 'medikamente'::TEXT, m.id, m.handelsname,
           m.dosierung_pferd || ' | ' || m.nebenwirkungen,
           1 - (m.embedding <=> query_embedding) AS sim
    FROM medikamente m
    WHERE m.embedding IS NOT NULL
      AND 1 - (m.embedding <=> query_embedding) > match_threshold
    
    UNION ALL
    
    -- Giftpflanzen
    SELECT 'giftpflanzen'::TEXT, g.id, g.deutscher_name,
           g.symptome_pferd || ' | ' || g.therapie,
           1 - (g.embedding <=> query_embedding) AS sim
    FROM giftpflanzen g
    WHERE g.embedding IS NOT NULL
      AND 1 - (g.embedding <=> query_embedding) > match_threshold
    
    UNION ALL
    
    -- Wechselwirkungen
    SELECT 'wechselwirkungen'::TEXT, ww.id, 
           ww.partner_a_name || ' × ' || ww.partner_b_name,
           ww.klinische_konsequenz || ' | ' || ww.empfehlung,
           1 - (ww.embedding <=> query_embedding) AS sim
    FROM wechselwirkungen ww
    WHERE ww.embedding IS NOT NULL
      AND 1 - (ww.embedding <=> query_embedding) > match_threshold
    
    UNION ALL
    
    -- Indikationen
    SELECT 'indikationen'::TEXT, i.id, i.indikation,
           i.first_line_wirkstoff || ' | ' || i.okapi_produkte,
           1 - (i.embedding <=> query_embedding) AS sim
    FROM indikationen i
    WHERE i.embedding IS NOT NULL
      AND 1 - (i.embedding <=> query_embedding) > match_threshold
    
    UNION ALL
    
    -- Praxisbewertungen
    SELECT 'praxisbewertungen'::TEXT, pb.id,
           'Praxis: ' || t.name,
           pb.erfahrungsbericht,
           1 - (pb.embedding <=> query_embedding) AS sim
    FROM praxisbewertungen pb
    JOIN therapeuten t ON pb.therapeut_id = t.id
    WHERE pb.embedding IS NOT NULL
      AND 1 - (pb.embedding <=> query_embedding) > match_threshold
    
    ORDER BY sim DESC
    LIMIT max_results;
END;
$$;


-- ═══════════════════════════════════════════════════════════════════
-- 12. TRIGGER: Automatische Level-Berechnung für Therapeuten
-- ═══════════════════════════════════════════════════════════════════

CREATE OR REPLACE FUNCTION update_therapeut_level()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE therapeuten SET
        bewertungen_count = (
            SELECT COUNT(*) FROM praxisbewertungen WHERE therapeut_id = NEW.therapeut_id
        ),
        level = CASE
            WHEN (SELECT COUNT(*) FROM praxisbewertungen WHERE therapeut_id = NEW.therapeut_id) >= 40 THEN 'Platin'
            WHEN (SELECT COUNT(*) FROM praxisbewertungen WHERE therapeut_id = NEW.therapeut_id) >= 20 THEN 'Gold'
            WHEN (SELECT COUNT(*) FROM praxisbewertungen WHERE therapeut_id = NEW.therapeut_id) >= 6 THEN 'Silber'
            ELSE 'Bronze'
        END,
        updated_at = NOW()
    WHERE id = NEW.therapeut_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_bewertung_level
    AFTER INSERT ON praxisbewertungen
    FOR EACH ROW
    EXECUTE FUNCTION update_therapeut_level();
