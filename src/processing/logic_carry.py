import json
import os
import re
import pandas as pd

# --- CONFIGS ---
DOCKER_CONFIG_DIR = "/app/configs"
LOCAL_CONFIG_DIR = "./configs"
CONFIG_DIR = DOCKER_CONFIG_DIR if os.path.exists(DOCKER_CONFIG_DIR) else LOCAL_CONFIG_DIR

def load_configs():
    """Load config and reverse the champion map"""
    try:
        with open(os.path.join(CONFIG_DIR, 'champ_roles.json'), 'r', encoding='utf-8') as f:
            champ_roles = json.load(f)
        with open(os.path.join(CONFIG_DIR, 'items_roles.json'), 'r', encoding='utf-8') as f:
            items_roles = json.load(f)
        
        champ_map = {}
        for role, champs in champ_roles.items():
            for champ in champs:
                champ_map[champ] = role
        
        # Extract special item lists from JSON
        basic_components = set(items_roles.get('COMPONENTS', []))
        ornn_items = set(items_roles.get('ORNN_ITEMS', []))
        
        print(f"[Config] Loaded {len(champ_map)} champions & {len(items_roles)} item roles.")
        return champ_map, items_roles, basic_components, ornn_items
    except Exception as e:
        print(f"[LogicCarry] Error loading configs: {e}")
        return {}, {}, set(), set()

def is_unit_carry(unit_data, champ_map, items_roles, basic_components, ornn_items):
    """Find Carry (Strict Mode: >=2 Core item/Ornn)"""
    character_id = unit_data.get('character_id')
    items = unit_data.get('itemNames', []) 

    # Rule 1: quantity
    if len(items) < 3: return False

    # Rule 2: ThiefsGloves -> False
    if "TFT_Item_ThiefsGloves" in items: return False

    # Find role
    role = champ_map.get(character_id)
    if not role: return False
    
    core_items = items_roles.get(role, [])
    perfect_items_count = 0
    
    for item in items:
        # Rule 3: Skip the components
        if item in basic_components: continue 
            
        # Rule 4: Ornn items -> count
        if item in ornn_items:
            perfect_items_count += 1
            continue
            
        # Rule 5: Core item -> count
        if item in core_items:
            perfect_items_count += 1
            
    return perfect_items_count >= 2

def parse_units_detailed(units_str):
    """
    Parse string: "TFT16_KogMaw(2★1$) | TFT16_Malzahar(2★3$)[Item1+Item2]"
    Output: [{'character_id': 'TFT16_KogMaw', 'tier': 2, 'cost': 1, 'itemNames': [...]}, ...]
    """
    if not isinstance(units_str, str) or not units_str:
        return []
        
    units_data = []
    # Regex: UnitID(Tier★Cost$)[Items] - Items optional
    pattern = re.compile(r"^(?P<unit_id>[\w\d_]+)\((?P<tier>\d+)★(?P<cost>\d+)\$\)(?:\[(?P<items>.*?)\])?$")
    
    raw_units = units_str.split(' | ')
    
    for raw_unit in raw_units:
        raw_unit = raw_unit.strip()
        match = pattern.match(raw_unit)
        if match:
            unit_id = match.group('unit_id')
            tier = int(match.group('tier'))
            cost = int(match.group('cost'))
            items_str = match.group('items')
            
            item_list = []
            if items_str:
                item_list = [i.strip() for i in items_str.split('+') if i.strip()]
            
            units_data.append({
                'character_id': unit_id,
                'tier': tier,
                'cost': cost,
                'itemNames': item_list
            })
            
    return units_data

def find_carry_in_match(units_str, champ_map, items_roles, basic_components, ornn_items):
    """
    Find the first carry unit in a match.
    Returns: {'carry_name': str, 'carry_tier': int, 'carry_cost': int} or None
    """
    parsed_units = parse_units_detailed(units_str)
    
    for unit in parsed_units:
        if is_unit_carry(unit, champ_map, items_roles, basic_components, ornn_items):
            return {
                'carry_name': unit['character_id'],
                'carry_tier': unit['tier'],
                'carry_cost': unit['cost']
            }
    
    return None

def run_debug_test(file_path):
    print(f"[Debug] Checking file: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    champ_map, items_roles = load_configs()
    
    try:
        df = pd.read_csv(file_path) 
        print(f"Loaded {len(df)} rows for testing.")
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    carry_count = 0
    debug_printed = False

    for _, row in df.iterrows():
        units_text = row.get('units_detailed', '')
        match_id = row.get('match_id', 'Unknown')
        
        parsed_units = parse_units_detailed(units_text)
        
        # --- DEBUG ITEM NAME ---
        if not debug_printed and parsed_units:
            for u in parsed_units:
                if u['itemNames']:
                    print(f"[DEBUG FORMAT] Unit: {u['character_id']} | Items: {u['itemNames']}")
                    debug_printed = True # Just print first item to debug
                    break
        # ------------------------------------

        for unit in parsed_units:
            if is_unit_carry(unit, champ_map, items_roles):
                print(f"FOUND CARRY: Match {match_id} | {unit['character_id']} | Items: {unit['itemNames']}")
                carry_count += 1
                
    print(f"\n Test Finished. Found {carry_count} carries in sample data.")

if __name__ == "__main__":
    CSV_PATH = "data/raw/tft_matches_vn2_top150.csv"
    run_debug_test(CSV_PATH)