"""
Contoh Script Perbandingan Data SIMPEG vs SIASN
================================================
Script ini menunjukkan bagaimana sistem akan mendeteksi perbedaan data
antara SIMPEG dan SIASN berdasarkan mapping kolom yang ditentukan.

Mapping kolom:
- NIP (SIMPEG) ↔ NIP BARU (SIASN) → untuk join/matching
- Jenjang Pendidikan ↔ TINGKAT PENDIDIKAN NAMA
- Nama Pendidikan ↔ PENDIDIKAN NAMA  
- Golru ↔ GOL AKHIR NAMA
- Nama Jabatan ↔ JABATAN NAMA
"""

import pandas as pd
import os

script_dir = os.path.dirname(os.path.abspath(__file__))

# Baca data contoh
df_simpeg = pd.read_csv(os.path.join(script_dir, 'contoh_simpeg.csv'))
df_siasn = pd.read_csv(os.path.join(script_dir, 'contoh_siasn.csv'))

# Mapping kolom untuk perbandingan
column_mapping = {
    'Jenjang Pendidikan': 'TINGKAT PENDIDIKAN NAMA',
    'Nama Pendidikan': 'PENDIDIKAN NAMA',
    'Golru': 'GOL AKHIR NAMA',
    'Nama Jabatan': 'JABATAN NAMA'
}

# Join data berdasarkan NIP
df_simpeg['NIP'] = df_simpeg['NIP'].astype(str).str.strip().str.replace("'", "")
df_siasn['NIP BARU'] = df_siasn['NIP BARU'].astype(str).str.strip().str.replace("'", "")

df_merged = pd.merge(
    df_simpeg, 
    df_siasn, 
    left_on='NIP', 
    right_on='NIP BARU', 
    how='inner',
    suffixes=('_SIMPEG', '_SIASN')
)

print("=" * 80)
print("LAPORAN PERBANDINGAN DATA SIMPEG vs SIASN")
print("=" * 80)
print(f"\nTotal data matched: {len(df_merged)} pegawai\n")

# Temukan perbedaan
issues_found = []
for idx, row in df_merged.iterrows():
    nip = row['NIP']
    nama = row['Nama Pegawai']
    
    row_issues = []
    for simpeg_col, siasn_col in column_mapping.items():
        val_simpeg = str(row[simpeg_col]).strip()
        val_siasn = str(row[siasn_col]).strip()
        
        if val_simpeg != val_siasn:
            row_issues.append({
                'kolom': simpeg_col,
                'simpeg': val_simpeg,
                'siasn': val_siasn
            })
    
    if row_issues:
        issues_found.append({
            'nip': nip,
            'nama': nama,
            'issues': row_issues
        })

# Tampilkan hasil
if issues_found:
    print(f"⚠️  DITEMUKAN {len(issues_found)} PEGAWAI DENGAN DATA TIDAK KONSISTEN\n")
    
    for i, issue in enumerate(issues_found, 1):
        print("-" * 60)
        print(f"#{i}. NIP: {issue['nip']}")
        print(f"    Nama: {issue['nama']}")
        print()
        
        for diff in issue['issues']:
            print(f"    📋 {diff['kolom']}:")
            print(f"       SIMPEG: {diff['simpeg']}")
            print(f"       SIASN : {diff['siasn']}")
            print()
    
    print("-" * 60)
    
    # Summary
    print(f"\n📊 RINGKASAN:")
    total_issues = sum(len(i['issues']) for i in issues_found)
    print(f"   • Total pegawai dengan masalah: {len(issues_found)}")
    print(f"   • Total perbedaan data: {total_issues}")
    
    # Breakdown per kolom
    issue_by_col = {}
    for issue in issues_found:
        for diff in issue['issues']:
            col = diff['kolom']
            issue_by_col[col] = issue_by_col.get(col, 0) + 1
    
    print(f"\n   Perbedaan per kategori:")
    for col, count in sorted(issue_by_col.items(), key=lambda x: x[1], reverse=True):
        print(f"   • {col}: {count} perbedaan")
else:
    print("✅ Semua data konsisten! Tidak ada perbedaan ditemukan.")

print("\n" + "=" * 80)
