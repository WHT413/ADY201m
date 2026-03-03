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
            items_roles_raw = json.load(f)
            
        # Handle new structure with CATEGORIZED key
        if 'CATEGORIZED' in items_roles_raw:
            items_roles = items_roles_raw['CATEGORIZED']
        else:   
            items_roles = items_roles_raw
        
        champ_map = {}
        for role, champs in champ_roles.items():
            for champ in champs:
                champ_map[champ] = role
        
        # Extract special item lists from JSON
        basic_components = set(items_roles.get('COMPONENTS', []))
        ornn_items = set(items_roles.get('ORNN_ITEMS', []))
        
        # Load Unit Costs (Fixes CSV anomalies)
        unit_costs = {}
        try:
            with open(os.path.join(CONFIG_DIR, 'champion_costs.json'), 'r', encoding='utf-8') as f:
                unit_costs = json.load(f)
        except Exception as e:
            print(f"[Config] Warning: Could not load champion_costs.json: {e}")
        
        print(f"[Config] Loaded {len(champ_map)} champions, {len(items_roles)} item roles, {len(unit_costs)} unit costs.")
        return champ_map, items_roles, basic_components, ornn_items, unit_costs
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

def parse_units_detailed(units_input, unit_costs=None):
    """
    Parse units from various formats (JSON list, JSON string, or Legacy Regex).
    """
    # 1. If already a list of dicts (parsed JSON)
    if isinstance(units_input, list):
        return parse_units_json(units_input, unit_costs)

    if not isinstance(units_input, str) or not units_input:
        return []

    # 2. Try parsing as JSON string
    try:
        # Handle simple CSV escaping if present
        clean_input = units_input.replace('""', '"') if '""' in units_input else units_input
        if clean_input.strip().startswith('['):
            data = json.loads(clean_input)
            if isinstance(data, list):
                return parse_units_json(data, unit_costs)
    except:
        pass

    # 3. Fallback: Legacy Regex for "TFT16_KogMaw(2★1$) | ..."
    units_data = []
    # Regex: UnitID(Tier★Cost$)[Items] - Items optional
    pattern = re.compile(r"^(?P<unit_id>[\w\d_]+)\((?P<tier>\d+)★(?P<cost>\d+)\$\)(?:\[(?P<items>.*?)\])?$")
    
    raw_units = units_input.split(' | ')
    
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
            
            # Correct Cost
            if unit_costs and unit_id in unit_costs:
                cost = unit_costs[unit_id]
            
            units_data.append({
                'character_id': unit_id,
                'tier': tier,
                'cost': cost,
                'itemNames': item_list
            })
            
    return units_data

def parse_units_json(units_data, unit_costs=None):
    """
    Parse list of unit dicts (from JSON).
    Input: [{'character_id': '...', 'tier': 1, 'rarity': 0, 'itemNames': [...]}, ...]
    Output: [{'character_id': '...', 'tier': 1, 'cost': 1, 'itemNames': [...]}]
    """
    if not isinstance(units_data, list):
        return []

    parsed_units = []
    
    for unit in units_data:
        unit_id = unit.get('character_id')
        if not unit_id: continue
        
        tier = unit.get('tier', 1)
        # Rarity 0 -> 1 Cost, 1 -> 2 Cost, etc.
        rarity = unit.get('rarity', 0)
        cost = rarity + 1
        
        # Correct Cost using verified map
        if unit_costs and unit_id in unit_costs:
            cost = unit_costs[unit_id]
            
        items = unit.get('itemNames', [])
        
        parsed_units.append({
            'character_id': unit_id,
            'tier': tier,
            'cost': cost,
            'itemNames': items
        })
        
    return parsed_units

def find_carry_in_match(units_str, champ_map, items_roles, basic_components, ornn_items, unit_costs):
    """
    Find ALL carry units in a match.
    Returns: List of {'carry_name': str, 'carry_tier': int, 'carry_cost': int}
    """
    parsed_units = parse_units_detailed(units_str, unit_costs)
    carries = []
    
    for unit in parsed_units:
        if is_unit_carry(unit, champ_map, items_roles, basic_components, ornn_items):
            carries.append({
                'carry_name': unit['character_id'],
                'carry_tier': unit['tier'],
                'carry_cost': unit['cost']
            })
    
    return carries



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
        # Try 'units_detailed' (Legacy) then 'units' (New JSON)
        units_text = row.get('units_detailed')
        if not units_text or pd.isna(units_text):
            units_text = row.get('units', '')
            
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