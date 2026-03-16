"""
ETL Pipeline: JSON → Carry Detection → SQLite 3NF
Reads tft_raw_top150_*.json, extracts participants and units, applies carry detection.
"""
import os
import sys
import json
import glob
import pandas as pd
import sqlite3

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from processing.logic_carry import load_configs, is_unit_carry, parse_units_json

# --- CONFIG ---
RAW_JSON_PATTERN = "data/raw/tft_raw_top150_*.json"
DB_PATH = "data/processed/tft_data.db"


def read_participants_from_json() -> pd.DataFrame:
    """Read participants directly from tft_raw_top150_*.json files"""
    print("\n--- READ FROM JSON ---")

    json_files = sorted(glob.glob(RAW_JSON_PATTERN))
    if not json_files:
        print(f"❌ No files found matching: {RAW_JSON_PATTERN}")
        return None

    rows = []
    for json_path in json_files:
        print(f"  Loading {json_path}...")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for match_id, match in data.items():
            info = match.get('info', {})
            for participant in info.get('participants', []):
                rows.append({
                    'match_id': match_id,
                    'puuid': participant.get('puuid', ''),
                    'placement': participant.get('placement', 0),
                    'level': participant.get('level', 0),
                    'units': participant.get('units', []),
                })

    df = pd.DataFrame(rows)
    print(f"✅ Read {len(df)} rows from {len(json_files)} JSON file(s)")
    return df


def deduplicate_df(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicates by (match_id, puuid)"""
    before = len(df)
    df = df.drop_duplicates(subset=['match_id', 'puuid'], keep='first')
    after = len(df)

    if before != after:
        print(f"🔄 Deduplication: {before} → {after} rows ({before - after} duplicates removed)")

    return df


def run_etl():
    """Main ETL: JSON → Carry Detection → SQLite"""
    print("\n--- ETL: JSON → CARRY DETECTION → SQLITE ---")

    # 1. Load configs
    champ_map, items_roles, basic_components, ornn_items, unit_costs = load_configs()
    if not champ_map:
        print("❌ Failed to load configs. Aborting.")
        return

    # 2. Read from JSON
    df = read_participants_from_json()
    if df is None or len(df) == 0:
        print("❌ No data to process.")
        return

    # 3. Deduplicate
    df = deduplicate_df(df)

    # 4. Process each row
    carries_data = []
    players_set = set()
    matches_set = set()
    skipped = 0

    print("\n🔍 Processing carries...")
    for idx, row in df.iterrows():
        parsed_units = parse_units_json(row.get('units', []))

        # Apply unit_costs correction
        for unit in parsed_units:
            if unit_costs and unit['character_id'] in unit_costs:
                unit['cost'] = unit_costs[unit['character_id']]

        # Find carries
        carries_found = []
        for unit in parsed_units:
            if is_unit_carry(unit, champ_map, items_roles, basic_components, ornn_items):
                carries_found.append({
                    'carry_name': unit['character_id'],
                    'carry_tier': unit['tier'],
                    'carry_cost': unit['cost']
                })

        if not carries_found:
            skipped += 1
            continue

        puuid = row.get('puuid', '')
        match_id = row.get('match_id', '')

        players_set.add(puuid)
        matches_set.add(match_id)

        for carry in carries_found:
            carries_data.append({
                'puuid': puuid,
                'match_id': match_id,
                'placement': row.get('placement', 0),
                'level': row.get('level', 0),
                'carry_name': carry['carry_name'],
                'carry_tier': carry['carry_tier'],
                'carry_cost': carry['carry_cost']
            })

    print(f"✅ Found {len(carries_data)} carry instances. Skipped {skipped} rows without carry.")

    # 5. Create DataFrames
    df_players = pd.DataFrame({'puuid': list(players_set)})
    df_matches = pd.DataFrame({'match_id': list(matches_set)})
    df_carries = pd.DataFrame(carries_data)

    # 6. Save to SQLite
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA foreign_keys = ON;")

    conn.execute("DROP TABLE IF EXISTS carries;")
    conn.execute("DROP TABLE IF EXISTS players;")
    conn.execute("DROP TABLE IF EXISTS matches;")

    conn.execute("""
        CREATE TABLE players (
            puuid TEXT PRIMARY KEY
        );
    """)
    conn.execute("""
        CREATE TABLE matches (
            match_id TEXT PRIMARY KEY
        );
    """)
    conn.execute("""
        CREATE TABLE carries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            puuid TEXT,
            match_id TEXT,
            placement INTEGER,
            level INTEGER,
            carry_name TEXT,
            carry_tier INTEGER,
            carry_cost INTEGER,
            FOREIGN KEY (puuid) REFERENCES players(puuid),
            FOREIGN KEY (match_id) REFERENCES matches(match_id)
        );
    """)

    df_players.to_sql("players", conn, if_exists="append", index=False)
    df_matches.to_sql("matches", conn, if_exists="append", index=False)
    df_carries.to_sql("carries", conn, if_exists="append", index=False)

    print(f"\n✅ Saved to SQLite (3NF):")
    print(f"   - players: {len(df_players)} rows")
    print(f"   - matches: {len(df_matches)} rows")
    print(f"   - carries: {len(df_carries)} rows")

    conn.close()


if __name__ == "__main__":
    run_etl()
    print("\n🎉 Done!")
