"""
Utility script to extract all unique items from the raw participants CSV.
Outputs to data/processed/unique_items.txt
"""
import csv
import json
import os
import sys

# Define paths
CSV_PATH = "data/raw/tft_participants_top150_20260205_024108.csv"
OUTPUT_PATH = "data/processed/unique_items.txt"

def extract_items():
    print(f"Reading CSV from {CSV_PATH}...")
    
    if not os.path.exists(CSV_PATH):
        print(f"❌ File not found: {CSV_PATH}")
        return

    unique_items = set()
    total_processed = 0
    
    # Increase field size limit for large JSON strings (use safe int for Windows)
    csv.field_size_limit(2147483647)
    
    try:
        with open(CSV_PATH, 'r', encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                try:
                    units_str = row.get('units', '')
                    if not units_str:
                        continue
                        
                    # Parse JSON directly (CSV reader handles quoting)
                    units = json.loads(units_str)
                    
                    for unit in units:
                        items = unit.get('itemNames', [])
                        if items:
                            unique_items.update(items)
                            
                except json.JSONDecodeError as e:
                    print(f"JSON Error on row {total_processed}: {e}")
                    # Print snippet
                    print(f"Snippet: {units_str[:100]}")
                    continue
                except Exception as e:
                    print(f"Error on row {total_processed}: {e}")
                    import traceback
                    traceback.print_exc()
                    break
                
                total_processed += 1
                if total_processed % 1000 == 0:
                    print(f"\rProcessed {total_processed} rows... Found {len(unique_items)} items.", end="")
        
        print("\n\n✅ Extraction complete.")
        
        # Sort and save
        sorted_items = sorted(list(unique_items))
        
        os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            for item in sorted_items:
                f.write(f"{item}\n")
                
        print(f"🎉 Saved {len(sorted_items)} unique items to {OUTPUT_PATH}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    extract_items()
