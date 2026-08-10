"""Loads the Q2 synthetic fleet dataset from Excel into a SQLite database.

Run it once (and again whenever the workbook is reissued):

    python load_dataset.py                      # dataset/AROL_Q2_synthetic_fleet_dataset.xlsx
    python load_dataset.py path/to/other.xlsx   # or an explicit path

Sheet and column names are kept exactly as they appear in the workbook, so the
dataset documentation reads as the schema documentation with no mental mapping
in between.
"""

import sqlite3
import sys
from pathlib import Path

import openpyxl

SERVICE_DIR = Path(__file__).parent
DEFAULT_SOURCE = SERVICE_DIR / "dataset" / "AROL_Q2_synthetic_fleet_dataset.xlsx"
DB_PATH = SERVICE_DIR / "data" / "backoffice.db"

# Every query the agents will run filters on one of these, so they are indexed
# wherever a table happens to carry them.
INDEXED_COLUMNS = ("machineId", "companyId", "timestamp")


def infer_type(values: list) -> str:
    """Pick the narrowest SQLite type that holds every non-empty value."""
    present = [v for v in values if v is not None]
    if present and all(isinstance(v, int) and not isinstance(v, bool) for v in present):
        return "INTEGER"
    if present and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in present):
        return "REAL"
    return "TEXT"


def read_sheet(worksheet) -> tuple[list[str], list[tuple]]:
    rows = worksheet.iter_rows(values_only=True)
    header = [str(h) for h in next(rows)]

    # An empty cell must reach SQLite as NULL. The dataset leaves some foreign
    # keys deliberately blank so that an inner join silently drops rows: turning
    # those blanks into "" or "nan" would quietly remove the very case the
    # dataset is testing for.
    data = [
        tuple(None if v == "" else v for v in row)
        for row in rows
        if any(v is not None and v != "" for v in row)
    ]
    return header, data


def load_sheet(conn: sqlite3.Connection, name: str, header: list[str], data: list[tuple]) -> None:
    columns = [
        f'"{col}" {infer_type([row[i] for row in data])}'
        for i, col in enumerate(header)
    ]

    conn.execute(f'DROP TABLE IF EXISTS "{name}"')
    conn.execute(f'CREATE TABLE "{name}" ({", ".join(columns)})')

    placeholders = ", ".join("?" * len(header))
    conn.executemany(f'INSERT INTO "{name}" VALUES ({placeholders})', data)

    for col in INDEXED_COLUMNS:
        if col in header:
            conn.execute(f'CREATE INDEX "ix_{name}_{col}" ON "{name}" ("{col}")')


def main(source: Path) -> None:
    if not source.is_file():
        print(f"error: dataset not found at {source}", file=sys.stderr)
        print("Pass the path as an argument, or drop the workbook there.", file=sys.stderr)
        raise SystemExit(1)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)

    # Rebuilt from scratch on every run: the workbook is the source of truth, and
    # reloading a corrected version has to cost one command, not a migration.
    with sqlite3.connect(DB_PATH) as conn:
        for name in workbook.sheetnames:
            header, data = read_sheet(workbook[name])
            load_sheet(conn, name, header, data)
            print(f"{name:<22} {len(data):>6} righe, {len(header)} colonne")

    workbook.close()
    print(f"\nScritto {DB_PATH.relative_to(SERVICE_DIR)} ({DB_PATH.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE)
