-- =============================================================================
-- PROJEKT: ANALIZA BENCHMARKINGOWA RYNKU VOD (AMAZON, DISNEY+, HBO, NETFLIX)
-- ETAP: FAZA 4 - ANALIZA DANYCH W JĘZYKU SQL (DUCKDB)
-- BLOK 1: STRUKTURA I WOLUMEN KATALOGÓW TREŚCI
-- =============================================================================

-- KPI 1.1: Całkowity wolumen katalogu w rozbiciu na platformy streamingowe
SELECT
    t.platform,
    COUNT(t.id) AS total_titles,
    ROUND(COUNT(t.id) * 100.0 / SUM(COUNT(t.id)) OVER (), 2) AS market_share_pct
FROM vod_titles AS t
GROUP BY
    t.platform
ORDER BY
    total_titles DESC;


-- KPI 1.2: Proporcja i struktura formatów (filmy vs seriale) per platforma
SELECT
    t.platform,
    COUNT(t.id) AS total_titles,
    COUNT(CASE WHEN t.type = 'MOVIE' THEN 1 END) AS movie_count,
    ROUND(COUNT(CASE WHEN t.type = 'MOVIE' THEN 1 END) * 100.0 / COUNT(t.id), 2) AS movie_share_pct,
    COUNT(CASE WHEN t.type = 'SHOW' THEN 1 END) AS show_count,
    ROUND(COUNT(CASE WHEN t.type = 'SHOW' THEN 1 END) * 100.0 / COUNT(t.id), 2) AS show_share_pct
FROM vod_titles AS t
GROUP BY
    t.platform
ORDER BY
    total_titles DESC;


-- KPI 1.3: Średni czas trwania filmów oraz średnia liczba sezonów seriali per platforma
SELECT
    t.platform,
    ROUND(AVG(CASE WHEN t.type = 'MOVIE' THEN t.runtime END), 2) AS avg_movie_runtime_min,
    ROUND(AVG(CASE WHEN t.type = 'SHOW' THEN t.seasons END), 2) AS avg_show_seasons
FROM vod_titles AS t
GROUP BY
    t.platform
ORDER BY
    avg_movie_runtime_min DESC;


-- =============================================================================
-- BLOK 2: SEGMENTACJA JAKOŚCIOWA I RYZYKO KATALOGU (QUALITY TIERING)
-- =============================================================================

-- KPI 2.1: Średnie i mediany ocen IMDb w rozbiciu na platformy i formaty (próba reprezentatywna)
SELECT
    t.platform,
    t.type,
    COUNT(t.id) AS rated_titles_count,
    ROUND(AVG(t.imdb_score), 2) AS avg_imdb_score,
    ROUND(MEDIAN(t.imdb_score), 2) AS median_imdb_score
FROM vod_titles AS t
WHERE
    t.has_valid_rating = TRUE
GROUP BY
    t.platform,
    t.type
ORDER BY
    t.platform ASC,
    t.type ASC;


-- KPI 2.2: Segmentacja jakościowa katalogu (Quality Tiering) per platforma
SELECT
    t.platform,
    CASE
        WHEN t.imdb_score >= 7.5 THEN 'Premium (IMDb >= 7.5)'
        WHEN t.imdb_score >= 6.0 THEN 'Standard (IMDb 6.0 - 7.4)'
        ELSE 'Low / Filler (IMDb < 6.0)'
    END AS quality_tier,
    COUNT(t.id) AS titles_count,
    ROUND(COUNT(t.id) * 100.0 / SUM(COUNT(t.id)) OVER (PARTITION BY t.platform), 2) AS tier_share_pct
FROM vod_titles AS t
WHERE
    t.has_valid_rating = TRUE
GROUP BY
    t.platform,
    quality_tier
ORDER BY
    t.platform ASC,
    CASE quality_tier
        WHEN 'Premium (IMDb >= 7.5)' THEN 1
        WHEN 'Standard (IMDb 6.0 - 7.4)' THEN 2
        ELSE 3
    END;


-- KPI 2.3: Pokrycie katalogu wiarygodnymi ocenami widzów (Rating Coverage)
SELECT
    t.platform,
    COUNT(t.id) AS total_titles,
    COUNT(CASE WHEN t.has_valid_rating = TRUE THEN 1 END) AS rated_titles_count,
    ROUND(COUNT(CASE WHEN t.has_valid_rating = TRUE THEN 1 END) * 100.0 / COUNT(t.id), 2) AS rating_coverage_pct,
    COUNT(CASE WHEN t.has_valid_rating = FALSE THEN 1 END) AS unrated_titles_count,
    ROUND(COUNT(CASE WHEN t.has_valid_rating = FALSE THEN 1 END) * 100.0 / COUNT(t.id), 2) AS unrated_share_pct
FROM vod_titles AS t
GROUP BY
    t.platform
ORDER BY
    rating_coverage_pct DESC;


-- =============================================================================
-- BLOK 3: UNIKALNOŚĆ I WYŁĄCZNOŚĆ OFERTY (EXCLUSIVITY & PORTFOLIO MOAT)
-- =============================================================================

-- KPI 3.1: Poziom wyłączności katalogu (Exclusive vs Shared) per platforma
SELECT
    t.platform,
    COUNT(t.id) AS total_titles,
    COUNT(CASE WHEN t.is_exclusive = TRUE THEN 1 END) AS exclusive_titles_count,
    ROUND(COUNT(CASE WHEN t.is_exclusive = TRUE THEN 1 END) * 100.0 / COUNT(t.id), 2) AS exclusive_share_pct,
    COUNT(CASE WHEN t.is_exclusive = FALSE THEN 1 END) AS shared_titles_count,
    ROUND(COUNT(CASE WHEN t.is_exclusive = FALSE THEN 1 END) * 100.0 / COUNT(t.id), 2) AS shared_share_pct
FROM vod_titles AS t
GROUP BY
    t.platform
ORDER BY
    exclusive_share_pct DESC;


-- KPI 3.2: Efektywność jakościowa wyłączności (Exclusive vs Shared IMDb Score)
SELECT
    t.platform,
    ROUND(AVG(CASE WHEN t.is_exclusive = TRUE THEN t.imdb_score END), 2) AS exclusive_avg_imdb,
    ROUND(MEDIAN(CASE WHEN t.is_exclusive = TRUE THEN t.imdb_score END), 2) AS exclusive_median_imdb,
    ROUND(AVG(CASE WHEN t.is_exclusive = FALSE THEN t.imdb_score END), 2) AS shared_avg_imdb,
    ROUND(MEDIAN(CASE WHEN t.is_exclusive = FALSE THEN t.imdb_score END), 2) AS shared_median_imdb,
    ROUND(
        AVG(CASE WHEN t.is_exclusive = TRUE THEN t.imdb_score END) - 
        AVG(CASE WHEN t.is_exclusive = FALSE THEN t.imdb_score END), 
        2
    ) AS quality_delta
FROM vod_titles AS t
WHERE
    t.has_valid_rating = TRUE
GROUP BY
    t.platform
ORDER BY
    exclusive_avg_imdb DESC;


-- KPI 3.3: Struktura formatów w portfolio tytułów na wyłączność (Format Mix in Exclusive)
SELECT
    t.platform,
    COUNT(t.id) AS exclusive_titles,
    COUNT(CASE WHEN t.type = 'MOVIE' THEN 1 END) AS exclusive_movies_count,
    ROUND(COUNT(CASE WHEN t.type = 'MOVIE' THEN 1 END) * 100.0 / COUNT(t.id), 2) AS exclusive_movies_pct,
    COUNT(CASE WHEN t.type = 'SHOW' THEN 1 END) AS exclusive_shows_count,
    ROUND(COUNT(CASE WHEN t.type = 'SHOW' THEN 1 END) * 100.0 / COUNT(t.id), 2) AS exclusive_shows_pct
FROM vod_titles AS t
WHERE
    t.is_exclusive = TRUE
GROUP BY
    t.platform
ORDER BY
    exclusive_titles DESC;


-- =============================================================================
-- BLOK 4: SEGMENTACJA GATUNKOWA I GRUPY DOCELOWE (GENRE & AUDIENCE TARGETING)
-- =============================================================================

-- KPI 4.1: Top 3 wiodące gatunki per platforma (Analiza rankingowa CTE i ROW_NUMBER)
WITH ranked_genres AS (
    SELECT
        t.platform,
        t.primary_genre,
        COUNT(t.id) AS titles_count,
        ROUND(AVG(t.imdb_score), 2) AS avg_imdb_score,
        ROW_NUMBER() OVER (
            PARTITION BY t.platform 
            ORDER BY COUNT(t.id) DESC
        ) AS genre_rank
    FROM vod_titles AS t
    WHERE
        t.primary_genre IS NOT NULL
        AND t.primary_genre != 'Not Specified'
    GROUP BY
        t.platform,
        t.primary_genre
)
SELECT
    rg.platform,
    rg.genre_rank,
    rg.primary_genre,
    rg.titles_count,
    rg.avg_imdb_score
FROM ranked_genres AS rg
WHERE
    rg.genre_rank <= 3
ORDER BY
    rg.platform ASC,
    rg.genre_rank ASC;


-- KPI 4.2: Struktura kategorii wiekowych (Audience Distribution) per platforma
SELECT
    t.platform,
    t.age_certification,
    COUNT(t.id) AS titles_count,
    ROUND(COUNT(t.id) * 100.0 / SUM(COUNT(t.id)) OVER (PARTITION BY t.platform), 2) AS share_pct
FROM vod_titles AS t
WHERE
    t.age_certification IS NOT NULL
GROUP BY
    t.platform,
    t.age_certification
ORDER BY
    t.platform ASC,
    share_pct DESC;


-- KPI 4.3: Jakość ocen w segmentach wiekowych (Quality by Age Rating)
SELECT
    t.platform,
    t.age_certification,
    COUNT(t.id) AS rated_titles_count,
    ROUND(AVG(t.imdb_score), 2) AS avg_imdb_score,
    ROUND(MEDIAN(t.imdb_score), 2) AS median_imdb_score
FROM vod_titles AS t
WHERE
    t.has_valid_rating = TRUE
    AND t.age_certification IS NOT NULL
GROUP BY
    t.platform,
    t.age_certification
HAVING
    COUNT(t.id) >= 20
ORDER BY
    t.platform ASC,
    avg_imdb_score DESC;


-- =============================================================================
-- BLOK 5: RELACYJNA ANALIZA OBSADY I REŻYSERÓW (TALENT & STAR POWER)
-- =============================================================================

-- KPI 5.1: Kluczowi twórcy - Top 3 reżyserzy per platforma (Analiza rankingowa CTE i ROW_NUMBER)
WITH director_stats AS (
    SELECT
        t.platform,
        c.name AS director_name,
        COUNT(DISTINCT t.id) AS directed_titles_count,
        ROUND(AVG(t.imdb_score), 2) AS avg_imdb_score,
        ROW_NUMBER() OVER (
            PARTITION BY t.platform 
            ORDER BY COUNT(DISTINCT t.id) DESC, AVG(t.imdb_score) DESC
        ) AS director_rank
    FROM vod_titles AS t
    JOIN vod_credits AS c 
        ON t.id = c.id AND t.platform = c.platform
    WHERE
        c.role = 'DIRECTOR'
        AND c.name != 'Unknown'
    GROUP BY
        t.platform,
        c.name
)
SELECT
    ds.platform,
    ds.director_rank,
    ds.director_name,
    ds.directed_titles_count,
    ds.avg_imdb_score
FROM director_stats AS ds
WHERE
    ds.director_rank <= 3
ORDER BY
    ds.platform ASC,
    ds.director_rank ASC;


-- KPI 5.2: Siła gwiazd (Star Power) w produkcjach wysokiej jakości (Premium Content: IMDb >= 7.5)
SELECT
    c.name AS actor_name,
    COUNT(DISTINCT t.id) AS premium_titles_count,
    ROUND(AVG(t.imdb_score), 2) AS avg_imdb_score,
    STRING_AGG(DISTINCT t.platform, ', ') AS platforms_list
FROM vod_titles AS t
JOIN vod_credits AS c 
    ON t.id = c.id AND t.platform = c.platform
WHERE
    c.role = 'ACTOR'
    AND c.name != 'Unknown'
    AND t.has_valid_rating = TRUE
    AND t.imdb_score >= 7.5
GROUP BY
    c.name
HAVING
    COUNT(DISTINCT t.id) >= 5
ORDER BY
    premium_titles_count DESC,
    avg_imdb_score DESC
LIMIT 10;


-- KPI 5.3: Twórcy międzyplatformowi (Cross-Platform Talent obecni na >= 3 platformach)
SELECT
    c.name AS talent_name,
    STRING_AGG(DISTINCT c.role, ' / ') AS roles,
    COUNT(DISTINCT t.platform) AS platforms_count,
    STRING_AGG(DISTINCT t.platform, ', ') AS platforms_list,
    COUNT(DISTINCT t.id) AS total_titles_count,
    ROUND(AVG(t.imdb_score), 2) AS avg_imdb_score
FROM vod_titles AS t
JOIN vod_credits AS c 
    ON t.id = c.id AND t.platform = c.platform
WHERE
    c.name != 'Unknown'
    AND t.has_valid_rating = TRUE
GROUP BY
    c.name
HAVING
    COUNT(DISTINCT t.platform) >= 3
ORDER BY
    platforms_count DESC,
    total_titles_count DESC,
    avg_imdb_score DESC
LIMIT 10;



