"""Debug script to compare a single NIP between SIMPEG and SIASN"""
import pandas as pd
import re

# Sample NIP to check
nip = '196111141989031001'

print(f"NIP: {nip}")

# SIMPEG
simpeg_file = r'd:\Second Brain\bantu_pacar\dataset\test_dataset\DaftarPegawai_Pegawai PNS_Lihat Di Seluruh Unor Induk (5) (1).xlsx'
df1 = pd.read_excel(simpeg_file, engine='openpyxl', header=0, dtype={'NIP': str})
df1['NIP_CLEAN'] = df1['NIP'].astype(str).apply(lambda x: re.sub(r'[^0-9]', '', x))
row1 = df1[df1['NIP_CLEAN'] == nip]

# SIASN
siasn_file = r'd:\Second Brain\bantu_pacar\dataset\test_dataset\pns_A5EB03E23D54F6A0E040640A040252AD_20260109_143636.csv'
df2 = pd.read_csv(siasn_file, delimiter='|', dtype={'NIP BARU': str})
df2['NIP_CLEAN'] = df2['NIP BARU'].astype(str).apply(lambda x: re.sub(r'[^0-9]', '', x))
row2 = df2[df2['NIP_CLEAN'] == nip]

if not row1.empty and not row2.empty:
    fields = [
        ('Jenjang Pendidikan', 'TINGKAT PENDIDIKAN NAMA'),
        ('Nama Pendidikan', 'PENDIDIKAN NAMA'),
        ('Golru', 'GOL AKHIR NAMA'),
        ('Nama Jabatan', 'JABATAN NAMA'),
    ]
    for simpeg_col, siasn_col in fields:
        v1 = str(row1[simpeg_col].values[0]).strip().lower()
        v2 = str(row2[siasn_col].values[0]).strip().lower()
        match = "SAME" if v1 == v2 else "DIFF"
        print(f"{match}: {simpeg_col}")
        print(f"   SIMPEG: {v1}")
        print(f"   SIASN:  {v2}")
else:
    print("NIP NOT FOUND in one of the files")
