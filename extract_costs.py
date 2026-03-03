import re
from bs4 import BeautifulSoup

try:
    with open('opgg_page.html', 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    
    # Strategy 1: Find rows in the table
    # The user screenshot shows a table.
    rows = soup.find_all('tr')
    
    results = {}
    
    print(f"Found {len(rows)} rows.")
    
    for row in rows:
        # Check for cost
        text = row.get_text()
        
        # Look for cost like $1, $2
        cost_match = re.search(r'\$(\d+)', text)
        if not cost_match:
            continue
            
        cost = int(cost_match.group(1))
        
        # Look for champion name
        # Usually in an img alt or just text
        # The row usually contains the champion name
        # We can extract all text and filter out the cost, rank, etc.
        # But looking for img alt is safer
        imgs = row.find_all('img')
        name = None
        for img in imgs:
            alt = img.get('alt')
            # Filter out traits/origins which might also have icons
            # Champion names start with capital letters, no numbers usually.
            # Traits also do.
            # But the champion name is usually text next to the image too.
            if alt and alt not in ['Ascendant', 'Bastion', 'Cost', 'Win Rate'] and 'tft-trait' not in str(img.get('src')):
                 # heuristic: champion img src usually differs from trait
                 if 'champion' in str(img.get('src')) or 'portrait' in str(img.get('src')):
                     name = alt
                     break
                 # specific to op.gg typical layout
                 if not name: 
                     name = alt # fallback
        
        # Refined name extraction
        # The name is often in a specific cell
        # Let's try to find the cell with the champion
        
        if name:
             # Clean name
             if name == "Cost": continue
             results[name] = cost

    print(f"Extracted {len(results)} champions.")
    # Print first 10
    for k, v in list(results.items())[:10]:
        print(f"{k}: {v}")
        
    # Save to file if successful
    if len(results) > 50:
        import json
        with open('extracted_costs.json', 'w') as f:
            json.dump(results, f, indent=4)

except Exception as e:
    print(f"Error: {e}")
