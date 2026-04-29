"""
Phase 5 Apex analytics harness for Olympus.

Standalone script that uses DuckDB in-process (no server) to run SQL queries
directly against the parquet bar-cache files in data/cache/.

DuckDB's read_parquet() glob support lets Apex query the entire cached universe
in a single SQL statement — no Python iteration, no pandas overhead. This is
the foundation for time-range filtering, symbol aggregation, and pattern
queries that Phase 5 will build on top of.

No imports from core/ — this is a fully self-contained read-only tool.
Run from the olympus/ directory:
    python tools/duckdb_query.py
"""

from __future__ import annotations

import os

import duckdb


def main() -> None:
    cache_dir = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "data", "cache")
    )
    parquet_glob = os.path.join(cache_dir, "*.parquet").replace("\\", "/")

    print(f"DuckDB in-process query against: {parquet_glob}")
    print()

    con = duckdb.connect()

    query = f"""
        SELECT
            symbol,
            COUNT(*)              AS bar_count,
            ROUND(AVG(close), 4)  AS avg_close
        FROM read_parquet('{parquet_glob}')
        GROUP BY symbol
        ORDER BY bar_count DESC
        LIMIT 10
    """

    result = con.execute(query).fetchdf()

    print("=" * 50)
    print("TOP 10 SYMBOLS BY BAR COUNT (data/cache/)")
    print("=" * 50)
    print(result.to_string(index=False))
    print("=" * 50)
    print(f"\nTotal symbols in cache: {con.execute(f'SELECT COUNT(DISTINCT symbol) FROM read_parquet(\'{parquet_glob}\')').fetchone()[0]}")

    con.close()


if __name__ == "__main__":
    main()
