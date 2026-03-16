"""
Utility script to extract all unique items from tft_raw_top150_*.json files.
Outputs to data/processed/unique_items.txt
"""
import json
import glob
import os

RAW_JSON_PATTERN = "data/raw/tft_raw_top150_*.json"
OUTPUT_PATH = "data/processed/unique_items.txt"


def extract_items():
    json_files = sorted(glob.glob(RAW_JSON_PATTERN))
    if not json_files:
        print(f"❌ No files found matching: {RAW_JSON_PATTERN}")
        return

    print(f"Reading {len(json_files)} JSON file(s)...")

    unique_items = set()
    total_processed = 0

    for json_path in json_files:
        print(f"  Loading {json_path}...")
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        for match_id, match in data.items():
            info = match.get('info', {})
            for participant in info.get('participants', []):
                for unit in participant.get('units', []):
                    items = unit.get('itemNames', [])
                    if items:
                        unique_items.update(items)

                total_processed += 1
                if total_processed % 1000 == 0:
                    print(f"\rProcessed {total_processed} rows... Found {len(unique_items)} items.", end="")

    print("\n\n✅ Extraction complete.")

    sorted_items = sorted(list(unique_items))

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        for item in sorted_items:
            f.write(f"{item}\n")

    print(f"🎉 Saved {len(sorted_items)} unique items to {OUTPUT_PATH}")


if __name__ == "__main__":
    extract_items()
