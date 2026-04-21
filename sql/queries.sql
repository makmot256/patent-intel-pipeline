-- ============================================================
-- Global Patent Intelligence Pipeline - Analytical Queries
-- ============================================================
-- Q1..Q7 are the required queries from the brief.
-- Q8..Q9 are the bonus CPC (innovation-category) queries.
-- Each block is fully standalone.
-- ============================================================

-- --------------------------------------------------
-- Q1 | Top inventors: who has the most patents?
-- --------------------------------------------------
SELECT
    i.inventor_id,
    i.name                              AS inventor,
    i.country,
    COUNT(DISTINCT pi.patent_id)        AS patent_count
FROM patent_inventor pi
JOIN inventors i ON i.inventor_id = pi.inventor_id
GROUP BY i.inventor_id, i.name, i.country
ORDER BY patent_count DESC, inventor ASC
LIMIT 10;

-- --------------------------------------------------
-- Q2 | Top companies: which companies own the most patents?
-- --------------------------------------------------
SELECT
    c.company_id,
    c.name                              AS company,
    COUNT(DISTINCT pc.patent_id)        AS patent_count
FROM patent_company pc
JOIN companies c ON c.company_id = pc.company_id
GROUP BY c.company_id, c.name
ORDER BY patent_count DESC, company ASC
LIMIT 10;

-- --------------------------------------------------
-- Q3 | Top countries: which countries produce the most patents?
-- --------------------------------------------------
SELECT
    i.country,
    COUNT(DISTINCT pi.patent_id)        AS patent_count
FROM patent_inventor pi
JOIN inventors i ON i.inventor_id = pi.inventor_id
WHERE i.country IS NOT NULL AND i.country <> ''
GROUP BY i.country
ORDER BY patent_count DESC
LIMIT 15;

-- --------------------------------------------------
-- Q4 | Trends over time: patents granted per year
-- --------------------------------------------------
SELECT
    year,
    COUNT(*) AS patent_count
FROM patents
WHERE year IS NOT NULL
GROUP BY year
ORDER BY year ASC;

-- --------------------------------------------------
-- Q5 | JOIN query: combine patents with inventors and companies
-- --------------------------------------------------
SELECT
    p.patent_id,
    p.title,
    p.year,
    i.name  AS inventor,
    i.country,
    c.name  AS company
FROM patents p
LEFT JOIN patent_inventor pi ON pi.patent_id  = p.patent_id
LEFT JOIN inventors       i  ON i.inventor_id = pi.inventor_id
LEFT JOIN patent_company  pc ON pc.patent_id  = p.patent_id
LEFT JOIN companies       c  ON c.company_id  = pc.company_id
ORDER BY p.year DESC, p.patent_id
LIMIT 50;

-- --------------------------------------------------
-- Q6 | CTE query: top 10 companies by average patents per year
-- --------------------------------------------------
WITH company_year_counts AS (
    SELECT
        c.company_id,
        c.name            AS company,
        p.year,
        COUNT(DISTINCT p.patent_id) AS patents_in_year
    FROM patents p
    JOIN patent_company pc ON pc.patent_id  = p.patent_id
    JOIN companies      c  ON c.company_id  = pc.company_id
    WHERE p.year IS NOT NULL
    GROUP BY c.company_id, c.name, p.year
),
company_stats AS (
    SELECT
        company_id,
        company,
        COUNT(DISTINCT year)   AS years_active,
        SUM(patents_in_year)   AS total_patents,
        ROUND(AVG(patents_in_year), 2) AS avg_patents_per_year
    FROM company_year_counts
    GROUP BY company_id, company
)
SELECT *
FROM company_stats
WHERE years_active >= 1
ORDER BY avg_patents_per_year DESC, total_patents DESC
LIMIT 10;

-- --------------------------------------------------
-- Q7 | Window function: rank inventors inside each country
-- --------------------------------------------------
WITH inventor_counts AS (
    SELECT
        i.inventor_id,
        i.name    AS inventor,
        i.country,
        COUNT(DISTINCT pi.patent_id) AS patent_count
    FROM patent_inventor pi
    JOIN inventors i ON i.inventor_id = pi.inventor_id
    WHERE i.country IS NOT NULL AND i.country <> ''
    GROUP BY i.inventor_id, i.name, i.country
)
SELECT
    country,
    inventor,
    patent_count,
    RANK()       OVER (PARTITION BY country ORDER BY patent_count DESC) AS country_rank,
    DENSE_RANK() OVER (PARTITION BY country ORDER BY patent_count DESC) AS country_dense_rank,
    ROW_NUMBER() OVER (ORDER BY patent_count DESC)                       AS global_row
FROM inventor_counts
ORDER BY country ASC, country_rank ASC
LIMIT 50;

-- --------------------------------------------------
-- Q8 | CPC innovation categories: patent share by section (bonus)
--      Runs only when the CPC data has been loaded.
-- --------------------------------------------------
SELECT
    s.section_code,
    s.description,
    COUNT(DISTINCT pc.patent_id) AS patent_count
FROM patent_cpc pc
JOIN cpc_sections s ON s.section_code = pc.section_code
GROUP BY s.section_code, s.description
ORDER BY patent_count DESC;

-- --------------------------------------------------
-- Q9 | CPC trend over time: patent volume per section per year (bonus)
-- --------------------------------------------------
SELECT
    p.year,
    s.section_code,
    s.description,
    COUNT(DISTINCT p.patent_id) AS patent_count
FROM patents p
JOIN patent_cpc    pc ON pc.patent_id    = p.patent_id
JOIN cpc_sections  s  ON s.section_code  = pc.section_code
WHERE p.year IS NOT NULL
GROUP BY p.year, s.section_code, s.description
ORDER BY p.year ASC, patent_count DESC;
