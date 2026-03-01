import pandas as pd
import re
import json

excel_path = r"C:\Users\agnes\Documents\0. LATSAR\nip_check_and_compare-main\nip_check_and_compare-main\Provinsi.xlsx"

def test_extraction():
    df = pd.read_excel(excel_path)
    print("Exact columns:", df.columns.tolist())
    
    mapping = {}
    
    for _, row in df.iterrows():
        # Get using the first few columns by index instead of name to be safe
        prov = str(row.iloc[0]).strip().upper() if pd.notna(row.iloc[0]) else ''
        kpu_prov = str(row.iloc[2]).strip().upper() if pd.notna(row.iloc[2]) else ''
        kpu_kab = str(row.iloc[3]).strip().upper() if pd.notna(row.iloc[3]) else ''
        
        if not prov or prov == 'NAN':
            continue
            
        # Area map
        match = re.search(r'(KABUPATEN|KOTA)\s+.+', kpu_kab)
        if match:
            area = match.group(0)
            area = re.sub(r'KOTA([A-Z])', r'KOTA \1', area)
            area = re.sub(r'KABUPATEN([A-Z])', r'KABUPATEN \1', area)
            area = re.sub(r'\s+', ' ', area).strip()
            mapping[area] = prov
            
        match_prov = re.search(r'PROVINSI\s+(.+)', kpu_prov)
        if match_prov:
            prov_name = match_prov.group(1).strip()
            mapping[f"PROVINSI {prov_name}"] = prov
        else:
            mapping[f"PROVINSI {prov}"] = prov

    with open('test_mapping.json', 'w') as f:
        json.dump(mapping, f, indent=2)
    print(f"Generated {len(mapping)} mappings")

if __name__ == '__main__':
    test_extraction()
