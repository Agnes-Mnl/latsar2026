"""
Quick script to check for duplicate NIPs across all files in test_dataset
"""
import os
import pandas as pd
from collections import Counter

# Paths
TEST_DATASET = r"d:\Second Brain\bantu_pacar\dataset\test_dataset"
OUTPUT_FILE = r"d:\Second Brain\bantu_pacar\quick_test\nip_duplicates.txt"

def read_excel_nips(file_path):
    """Read NIPs from Excel file"""
    nips = []
    try:
        # Try header=0 first
        df = pd.read_excel(file_path, engine='openpyxl', header=0, dtype={'NIP': str})
        if 'NIP' in df.columns:
            nips = df['NIP'].dropna().astype(str).tolist()
            print(f"  ✓ {os.path.basename(file_path)}: {len(nips)} NIPs (header=0)")
            return nips, "NIP"
        
        # Try header=1
        df = pd.read_excel(file_path, engine='openpyxl', header=1, dtype={'NIP': str})
        if 'NIP' in df.columns:
            nips = df['NIP'].dropna().astype(str).tolist()
            print(f"  ✓ {os.path.basename(file_path)}: {len(nips)} NIPs (header=1)")
            return nips, "NIP"
        
        print(f"  ✗ {os.path.basename(file_path)}: No 'NIP' column found. Columns: {list(df.columns)[:10]}")
    except Exception as e:
        print(f"  ✗ {os.path.basename(file_path)}: Error - {e}")
    
    return nips, None

def read_csv_nips(file_path):
    """Read NIPs from CSV file (pipe-delimited SIASN format)"""
    nips = []
    try:
        df = pd.read_csv(file_path, delimiter='|', encoding='utf-8', dtype={'NIP BARU': str})
        if 'NIP BARU' in df.columns:
            # Clean NIPs - remove quotes and keep only digits
            raw_nips = df['NIP BARU'].dropna().astype(str).tolist()
            nips = [nip.strip().lstrip("'\"") for nip in raw_nips]
            print(f"  ✓ {os.path.basename(file_path)}: {len(nips)} NIPs")
            return nips, "NIP BARU"
        
        print(f"  ✗ {os.path.basename(file_path)}: No 'NIP BARU' column found")
    except Exception as e:
        print(f"  ✗ {os.path.basename(file_path)}: Error - {e}")
    
    return nips, None

def main():
    print("=" * 60)
    print("NIP Duplicate Checker")
    print("=" * 60)
    print(f"\nScanning: {TEST_DATASET}\n")
    
    all_nips = []
    file_nips = {}  # Track which file each NIP comes from
    
    # Process all files
    for filename in os.listdir(TEST_DATASET):
        file_path = os.path.join(TEST_DATASET, filename)
        
        if filename.endswith('.xlsx'):
            nips, col = read_excel_nips(file_path)
            source_type = "SIMPEG"
        elif filename.endswith('.csv'):
            nips, col = read_csv_nips(file_path)
            source_type = "SIASN"
        else:
            continue
        
        # Track NIPs with their source
        for nip in nips:
            if nip not in file_nips:
                file_nips[nip] = []
            file_nips[nip].append(f"{source_type}:{filename}")
        
        all_nips.extend(nips)
    
    print(f"\n{'=' * 60}")
    print(f"TOTAL NIPs collected: {len(all_nips)}")
    print(f"UNIQUE NIPs: {len(set(all_nips))}")
    
    # Find duplicates (NIPs that appear more than once)
    nip_counts = Counter(all_nips)
    duplicates = {nip: count for nip, count in nip_counts.items() if count > 1}
    
    print(f"DUPLICATE NIPs: {len(duplicates)}")
    print("=" * 60)
    
    # Write output
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("=" * 60 + "\n")
        f.write("NIP DUPLICATE REPORT\n")
        f.write("=" * 60 + "\n\n")
        
        f.write(f"Jumlah NIP duplikat: {len(duplicates)}\n")
        f.write(f"Total NIP: {len(all_nips)}\n")
        f.write(f"Unique NIP: {len(set(all_nips))}\n\n")
        
        f.write("-" * 60 + "\n")
        f.write("DETAIL DUPLIKAT:\n")
        f.write("-" * 60 + "\n\n")
        
        for nip, count in sorted(duplicates.items(), key=lambda x: -x[1]):
            f.write(f"NIP: {nip} (appears {count}x)\n")
            for source in file_nips[nip]:
                f.write(f"  - {source}\n")
            f.write("\n")
        
        # Sample of first 10 unique NIPs for verification
        f.write("-" * 60 + "\n")
        f.write("SAMPLE 10 NIPs (for verification):\n")
        f.write("-" * 60 + "\n\n")
        
        sample_nips = list(set(all_nips))[:10]
        for i, nip in enumerate(sample_nips, 1):
            f.write(f"{i}. {nip}\n")
    
    print(f"\n✓ Output saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
