-- ============================================================
-- Global Patent Intelligence Pipeline - Database Schema
-- ============================================================
-- patents           : one row per granted patent
-- inventors         : one row per disambiguated inventor
-- companies         : one row per disambiguated assignee
-- patent_inventor   : many-to-many link (a patent has many inventors)
-- patent_company    : many-to-many link (a patent has many assignees)
-- cpc_sections      : reference table of CPC top-level sections (A-H, Y)
-- patent_cpc        : patent -> CPC category (optional, present when
--                     USE_CPC = True in src/config.py)
-- ============================================================

DROP TABLE IF EXISTS patent_cpc;
DROP TABLE IF EXISTS cpc_sections;
DROP TABLE IF EXISTS patent_inventor;
DROP TABLE IF EXISTS patent_company;
DROP TABLE IF EXISTS patents;
DROP TABLE IF EXISTS inventors;
DROP TABLE IF EXISTS companies;

CREATE TABLE patents (
    patent_id   TEXT PRIMARY KEY,
    title       TEXT,
    abstract    TEXT,
    filing_date DATE,
    year        INTEGER
);

CREATE TABLE inventors (
    inventor_id TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    country     TEXT
);

CREATE TABLE companies (
    company_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL
);

CREATE TABLE patent_inventor (
    patent_id   TEXT NOT NULL,
    inventor_id TEXT NOT NULL,
    PRIMARY KEY (patent_id, inventor_id),
    FOREIGN KEY (patent_id)   REFERENCES patents(patent_id),
    FOREIGN KEY (inventor_id) REFERENCES inventors(inventor_id)
);

CREATE TABLE patent_company (
    patent_id  TEXT NOT NULL,
    company_id TEXT NOT NULL,
    PRIMARY KEY (patent_id, company_id),
    FOREIGN KEY (patent_id)  REFERENCES patents(patent_id),
    FOREIGN KEY (company_id) REFERENCES companies(company_id)
);

CREATE TABLE cpc_sections (
    section_code TEXT PRIMARY KEY,   -- 'A','B','C','D','E','F','G','H','Y'
    description  TEXT NOT NULL
);

CREATE TABLE patent_cpc (
    patent_id    TEXT NOT NULL,
    section_code TEXT NOT NULL,
    subclass     TEXT,               -- e.g. 'H04L'
    PRIMARY KEY (patent_id, subclass),
    FOREIGN KEY (patent_id)    REFERENCES patents(patent_id),
    FOREIGN KEY (section_code) REFERENCES cpc_sections(section_code)
);

CREATE INDEX IF NOT EXISTS idx_patents_year    ON patents(year);
CREATE INDEX IF NOT EXISTS idx_inventors_ctry  ON inventors(country);
CREATE INDEX IF NOT EXISTS idx_pi_inventor     ON patent_inventor(inventor_id);
CREATE INDEX IF NOT EXISTS idx_pc_company      ON patent_company(company_id);
CREATE INDEX IF NOT EXISTS idx_pcpc_section    ON patent_cpc(section_code);

-- Seed CPC sections (official top-level category descriptions)
INSERT INTO cpc_sections (section_code, description) VALUES
    ('A', 'Human Necessities'),
    ('B', 'Performing Operations; Transporting'),
    ('C', 'Chemistry; Metallurgy'),
    ('D', 'Textiles; Paper'),
    ('E', 'Fixed Constructions'),
    ('F', 'Mechanical Engineering; Lighting; Heating; Weapons; Blasting'),
    ('G', 'Physics'),
    ('H', 'Electricity'),
    ('Y', 'General Tagging of New Technologies');
