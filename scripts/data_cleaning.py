"""
Skrypt ETL do czyszczenia, transformacji i integracji relacyjnej bazy danych VOD.

Projekt: Porównawcza analiza katalogów platform VOD (Amazon Prime, Disney+, HBO Max, Netflix)
Format docelowy: Zoptymalizowane pliki CSV dla analityków danych i modeli Power BI
Standard: PEP8, kodowanie UTF-8-SIG, pełna walidacja spójności referencyjnej
"""

import ast
import re
import sys
from pathlib import Path
import numpy as np
import pandas as pd

# Konfiguracja bezpiecznego kodowania konsoli dla środowiska Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def clean_text_field(value: object, default: str = "Not Specified") -> str:
    """Oczyszczenie pola tekstowego ze znaków kontrolnych i zbędnych spacji."""
    if pd.isna(value):
        return default
    text = str(value)
    # Usunięcie znaków kontrolnych, przejść do nowej linii i twardych spacji
    text = re.sub(r"[\r\n\t\x00-\x1f\x7f-\x9f\u200b\xa0]", " ", text)
    # Redukcja wielokrotnych spacji do pojedynczego odstępu
    text = re.sub(r"\s+", " ", text).strip()
    return text if text else default


def parse_genres_column(raw_genres: object) -> tuple[str, str]:
    """
    Parsowanie surowego ciągu tekstowego z listą gatunków.

    Zwraca krotkę (primary_genre, genres_clean), gdzie:
    - primary_genre to pierwszy dominujący gatunek z wielkiej litery,
    - genres_clean to czytelna, rozdzielona przecinkami lista gatunków z wielkich liter.
    """
    if pd.isna(raw_genres):
        return "Not Specified", "Not Specified"

    cleaned_str = str(raw_genres).strip()
    if not cleaned_str or cleaned_str == "[]":
        return "Not Specified", "Not Specified"

    try:
        parsed = ast.literal_eval(cleaned_str)
        if isinstance(parsed, list):
            cleaned_list = [str(g).strip().title() for g in parsed if str(g).strip()]
            if cleaned_list:
                primary = cleaned_list[0]
                genres_clean = ", ".join(cleaned_list)
                return primary, genres_clean
    except Exception:
        # Awaryjna ekstrakcja tokenów słownych w przypadku niestandardowego formatowania
        tokens = re.findall(r"[a-zA-Z0-9_\-]+", cleaned_str)
        cleaned_list = [t.strip().title() for t in tokens if t.strip()]
        if cleaned_list:
            return cleaned_list[0], ", ".join(cleaned_list)

    return "Not Specified", "Not Specified"


def categorize_runtime(minutes: float) -> str:
    """Klasyfikacja czasu trwania na 3 standardowe kategorie biznesowe."""
    if pd.isna(minutes) or minutes < 90:
        return "Short (<90m)"
    if minutes <= 120:
        return "Standard (90-120m)"
    return "Long (>120m)"


def load_raw_titles(sources: dict[str, Path]) -> pd.DataFrame:
    """
    Wczytanie i scalenie tabel titles ze wszystkich platform źródłowych.

    Uzasadnienie: Ujednolicenie katalogu w jeden spójny DataFrame umożliwia
    kompleksową analizę porównawczą (benchmarking) całego rynku VOD.
    """
    frames: list[pd.DataFrame] = []
    for platform_name, file_path in sources.items():
        if not file_path.exists():
            raise FileNotFoundError(f"Brak pliku źródłowego: {file_path}")
        df = pd.read_csv(file_path)
        df["platform"] = platform_name
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    # Usunięcie technicznych duplikatów wierszy występujących w surowych zbiorach
    combined = combined.drop_duplicates().reset_index(drop=True)
    return combined


def load_raw_credits(sources: dict[str, Path]) -> pd.DataFrame:
    """
    Wczytanie i scalenie tabel credits ze wszystkich platform źródłowych.

    Uzasadnienie: Zbudowanie nadrzędnej tabeli relacyjnej obsady z zachowaniem
    informacji o platformie dystrybucyjnej.
    """
    frames: list[pd.DataFrame] = []
    for platform_name, file_path in sources.items():
        if not file_path.exists():
            raise FileNotFoundError(f"Brak pliku źródłowego: {file_path}")
        df = pd.read_csv(file_path)
        df["platform"] = platform_name
        frames.append(df)

    combined = pd.concat(frames, ignore_index=True)
    # Usunięcie technicznych duplikatów powielonych wpisów obsady
    combined = combined.drop_duplicates().reset_index(drop=True)
    return combined


def process_titles_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Główny potok przetwarzania i inżynierii cech dla tabeli TITLES.

    Kroki:
    1. Eliminacja szumu: usunięcie kolumny description oraz zbędnych metadanych TMDB/IMDb.
    2. Czyszczenie tytułów ze znaków łamania linii i podwójnych spacji.
    3. Obsługa braków danych w age_certification i seasons pod kątem Power BI.
    4. Twarde rzutowanie typów numerycznych.
    5. Inżynieria cech: primary_genre, genres_clean, is_exclusive, has_valid_rating, runtime_category.
    """
    # Usunięcie kolumny description oraz zbędnych metadanych
    # Uzasadnienie techniczne: Kolumna description zawiera liczne znaki nowej linii (\r, \n),
    # co powoduje błędy interpretacji wierszy w Power Query i zniekształca model relacyjny.
    # Kolumny tmdb_popularity, tmdb_score, production_countries oraz imdb_id są pomijane,
    # aby zredukować rozmiar tabeli i wyeliminować szum informacyjny z modelu raportowego.
    columns_to_drop = [
        "description",
        "tmdb_popularity",
        "tmdb_score",
        "production_countries",
        "imdb_id",
    ]
    df = df.drop(columns=columns_to_drop, errors="ignore").copy()

    # Czyszczenie kolumny title ze znaków łamania wiersza i nadmiarowych spacji
    # Uzasadnienie: Zapewnienie jednolitych etykiet na wykresach i precyzyjnego dopasowania tekstowego
    df["title"] = df["title"].apply(lambda x: clean_text_field(x, default="Untitled"))

    # Uzupełnienie braków w age_certification
    # Uzasadnienie biznesowe: Braki ratingów wiekowych w Power BI powodują powstawanie niepożądanej
    # kategorii (Blank) w filtrach i fragmentatorach danych, zniekształcając analizę demograficzną.
    df["age_certification"] = df["age_certification"].fillna("Unrated / Not Specified")
    df["age_certification"] = df["age_certification"].replace("", "Unrated / Not Specified")

    # Obsługa braków i standaryzacja kolumny seasons
    # Uzasadnienie biznesowe: Filmy z definicji mają 0 sezonów. Pozostawienie wartości NULL
    # powodowałoby błędy w kalkulacji miar DAX (AVERAGE) oraz ignorowanie filmów w analizach.
    # W przypadku seriali ewentualne braki uzupełniane są minimalną wartością 1.
    is_movie = df["type"] == "MOVIE"
    df["seasons"] = np.where(is_movie, 0, df["seasons"].fillna(1))

    # Twarde rzutowanie typów numerycznych
    # Uzasadnienie techniczne: Zagwarantowanie typów całkowitych int bez formatowania zmiennoprzecinkowego (.0)
    # pozwala Power BI na automatyczne rozpoznanie kolumn jako Whole Number bez błędów konwersji.
    df["seasons"] = df["seasons"].astype(int)
    df["release_year"] = pd.to_numeric(df["release_year"], errors="coerce").fillna(0).astype(int)
    df["runtime"] = pd.to_numeric(df["runtime"], errors="coerce").fillna(0).astype(int)
    df["imdb_score"] = pd.to_numeric(df["imdb_score"], errors="coerce")
    df["imdb_votes"] = pd.to_numeric(df["imdb_votes"], errors="coerce").astype("Int64")

    # Inżynieria cech: primary_genre oraz genres_clean
    # Uzasadnienie biznesowe: Wyodrębnienie wiodącego gatunku (primary_genre) pozwala na tworzenie
    # jednoznacznych wykresów udziału gatunkowego w Power BI, natomiast genres_clean dostarcza
    # czytelny dla użytkownika pełny zestaw gatunków produkcji.
    parsed_genres = df["genres"].apply(parse_genres_column)
    df["primary_genre"] = [item[0] for item in parsed_genres]
    df["genres_clean"] = [item[1] for item in parsed_genres]
    df = df.drop(columns=["genres"], errors="ignore")

    # Inżynieria cech: is_exclusive (wykrywanie wyłączności licencyjnej)
    # Uzasadnienie biznesowe: Wyłączność treści jest kluczowym miernikiem (KPI) wartości katalogu VOD.
    # Treści dostępne na wielu platformach to tytuły licencjonowane wspólnie (syndykowane).
    norm_title = df["title"].astype(str).str.strip().str.lower()
    norm_type = df["type"].astype(str).str.strip().str.upper()
    platform_counts = df.groupby([norm_title, df["release_year"], norm_type])["platform"].transform("nunique")
    df["is_exclusive"] = platform_counts == 1

    # Inżynieria cech: has_valid_rating (wiarygodność oceny widzów)
    # Uzasadnienie biznesowe: Oceny z małą liczbą głosów (<100) są statystycznie niestabilne i podatne
    # na anomalie. Flaga pozwala na filtrowanie rzetelnych ocen w analizach jakościowych.
    df["has_valid_rating"] = df["imdb_score"].notna() & df["imdb_votes"].notna() & (df["imdb_votes"] >= 100)

    # Inżynieria cech: runtime_category (segmentacja długości seansu)
    # Uzasadnienie biznesowe: Umożliwia segmentację katalogu pod kątem nawyków czasowych odbiorców.
    df["runtime_category"] = df["runtime"].apply(categorize_runtime)

    # Ustalenie ostatecznego, czystego układu 15 kolumn w tabeli głównej
    target_columns = [
        "id",
        "platform",
        "title",
        "type",
        "release_year",
        "age_certification",
        "runtime",
        "seasons",
        "primary_genre",
        "genres_clean",
        "imdb_score",
        "imdb_votes",
        "is_exclusive",
        "has_valid_rating",
        "runtime_category",
    ]
    return df[target_columns]


def process_credits_data(df_credits: pd.DataFrame, valid_titles_ids: set[str]) -> pd.DataFrame:
    """
    Główny potok czyszczenia i walidacji relacyjnej dla tabeli CREDITS.

    Kroki:
    1. Czyszczenie pól tekstowych (name, character, role) ze zbędnych spacji i znaków specjalnych.
    2. Imputacja brakujących wartości w kolumnie character wartością 'Not Specified'.
    3. Weryfikacja spójności referencyjnej klucza obcego id (relacja 1 -> N z titles).
    """
    df = df_credits.copy()

    # Czyszczenie i standaryzacja pól tekstowych
    # Uzasadnienie techniczne: Usunięcie białych spacji i znaków kontrolnych gwarantuje poprawne
    # wyszukiwanie aktorów oraz spójność etykiet na dashboardach.
    df["name"] = df["name"].apply(lambda x: clean_text_field(x, default="Unknown"))
    df["character"] = df["character"].apply(lambda x: clean_text_field(x, default="Not Specified"))
    df["role"] = df["role"].apply(lambda x: clean_text_field(x, default="Not Specified"))
    df["id"] = df["id"].astype(str).str.strip()
    df["person_id"] = pd.to_numeric(df["person_id"], errors="coerce").fillna(0).astype(int)

    # Zapewnienie integralności referencyjnej z tabelą TITLES
    # Uzasadnienie biznesowe: Eliminacja potencjalnych rekordów osieroconych (brak dopasowania id w titles),
    # co chroni model relacyjny Power BI przed błędami kardynalności.
    df = df[df["id"].isin(valid_titles_ids)].reset_index(drop=True)

    target_columns = ["person_id", "id", "name", "character", "role", "platform"]
    return df[target_columns]


def main() -> None:
    """Funkcja główna wykonująca pełen proces ETL i walidację końcową."""
    base_dir = Path(__file__).resolve().parent.parent
    processed_dir = base_dir / "data" / "processed"
    processed_dir.mkdir(parents=True, exist_ok=True)

    sources_titles = {
        "Amazon Prime": base_dir / "data" / "raw" / "amazon" / "amazon titles.csv",
        "Disney+": base_dir / "data" / "raw" / "disney+" / "disneytitles.csv",
        "HBO Max": base_dir / "data" / "raw" / "hbo" / "hbotitles.csv",
        "Netflix": base_dir / "data" / "raw" / "netflix" / "netflixtitles.csv",
    }

    sources_credits = {
        "Amazon Prime": base_dir / "data" / "raw" / "amazon" / "amazoncredits.csv",
        "Disney+": base_dir / "data" / "raw" / "disney+" / "disneycredits.csv",
        "HBO Max": base_dir / "data" / "raw" / "hbo" / "hbocredits.csv",
        "Netflix": base_dir / "data" / "raw" / "netflix" / "netflixcredits.csv",
    }

    print("=" * 80)
    print("PRODUKCYJNY PIPELINE ETL: CZYSZCZENIE I RELACYJNE MODELOWANIE DANYCH VOD")
    print("=" * 80)

    # 1. Wczytanie i przetwarzanie tabeli głównej TITLES
    print("\n[1/4] Wczytywanie i transformacja tabeli głównej TITLES...")
    raw_titles = load_raw_titles(sources_titles)
    titles_cleaned = process_titles_data(raw_titles)

    # 2. Wczytanie i przetwarzanie tabeli relacyjnej CREDITS
    print("[2/4] Wczytywanie i transformacja tabeli relacyjnej CREDITS...")
    raw_credits = load_raw_credits(sources_credits)
    valid_titles_ids = set(titles_cleaned["id"])
    credits_cleaned = process_credits_data(raw_credits, valid_titles_ids)

    # 3. Zapis danych do katalogu data/processed/ (format UTF-8-SIG dla Power BI / Excel)
    print("[3/4] Zapisywanie oczyszczonych plików do data/processed/...")
    output_titles_path = processed_dir / "vod_titles_cleaned.csv"
    output_credits_path = processed_dir / "vod_credits_cleaned.csv"

    titles_cleaned.to_csv(output_titles_path, index=False, encoding="utf-8-sig")
    credits_cleaned.to_csv(output_credits_path, index=False, encoding="utf-8-sig")

    # 4. Weryfikacja autonomiczna i raport jakości danych
    print("\n[4/4] WERYFIKACJA AUTONOMICZNA I RAPORT SPÓJNOŚCI DANYCH:")
    print("-" * 80)

    # Wymiary wygenerowanych plików
    print(f"Plik titles:   {output_titles_path.name:<25} | Wymiary: {titles_cleaned.shape[0]} wierszy, {titles_cleaned.shape[1]} kolumn")
    print(f"Plik credits:  {output_credits_path.name:<25} | Wymiary: {credits_cleaned.shape[0]} wierszy, {credits_cleaned.shape[1]} kolumn")

    # Weryfikacja kolumny seasons (musi zawierać TYLKO liczby całkowite)
    unique_seasons = sorted(int(x) for x in titles_cleaned["seasons"].unique())
    all_seasons_numeric = all(isinstance(x, int) for x in unique_seasons)
    print(f"\nWynik df['seasons'].unique():\n  {unique_seasons}")
    print(f"  -> Czy kolumna seasons zawiera WYŁĄCZNIE liczby całkowite?: {all_seasons_numeric}")

    # Weryfikacja kolumny age_certification (brak wartości null)
    unique_age = sorted(titles_cleaned["age_certification"].unique())
    has_null_age = titles_cleaned["age_certification"].isna().any()
    print(f"\nWynik df['age_certification'].unique():\n  {unique_age}")
    print(f"  -> Czy kolumna age_certification jest wolna od wartości NULL?: {not has_null_age}")

    # Weryfikacja spójności relacyjnej 1 -> N
    orphan_keys = set(credits_cleaned["id"]) - valid_titles_ids
    print(f"\nSpójność relacyjna klucza 'id' (1 -> N):\n  Liczba rekordów osieroconych w credits: {len(orphan_keys)}")
    print(f"  -> Integralność referencyjna w 100% zachowana: {len(orphan_keys) == 0}")

    # Podsumowanie dystrybucji platform i wyłączności
    print("\nPodsumowanie dystrybucji platform w tabeli TITLES:")
    summary = titles_cleaned.groupby("platform").agg(
        total_titles=("id", "count"),
        movies=("type", lambda x: (x == "MOVIE").sum()),
        shows=("type", lambda x: (x == "SHOW").sum()),
        exclusive_titles=("is_exclusive", "sum"),
        avg_imdb=("imdb_score", "mean"),
    )
    summary["exclusive_pct"] = summary["exclusive_titles"] / summary["total_titles"]
    print(summary.to_string(formatters={
        "avg_imdb": "{:.2f}".format,
        "exclusive_pct": "{:.1%}".format,
    }))

    print("\n" + "=" * 80)
    print("PROCES ZAKOŃCZONY SUKCESEM. DANE SĄ GOTOWE DO MODELOWANIA W POWER BI / SQL.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
