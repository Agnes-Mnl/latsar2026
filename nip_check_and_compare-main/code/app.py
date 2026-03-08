"""
NIP Data Checker - Flask Application
Membandingkan data pegawai antara SIMPEG dan SIASN
"""

import os
import logging
import traceback
import re
import pandas as pd
from flask import Flask, render_template, request, jsonify, session, Response
from werkzeug.utils import secure_filename
import tempfile
import io

# Setup logging - console and file
LOG_FILE = os.path.join(os.path.dirname(__file__), 'nip_checker.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    handlers=[
        logging.StreamHandler(),  # Console
        logging.FileHandler(LOG_FILE, encoding='utf-8')  # File
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'nip-checker-secret-key-2026'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max

# Column mapping between SIMPEG and SIASN
COLUMN_MAP = {
    'simpeg': {
        'nip': 'NIP',
        'nama': 'Nama Pegawai',
        'jenjang_pendidikan': 'Jenjang Pendidikan',
        'nama_pendidikan': 'Nama Pendidikan',
        'golru': 'Golru',
        'nama_jabatan': 'Nama Jabatan',
        'unor': 'Unor',
        'unor_induk': 'Unor Induk',
        'jenis_pegawai': 'CPNS/PNS'
    },
    'siasn': {
        'nip': 'NIP BARU',
        'nama': 'NAMA',
        'jenjang_pendidikan': 'TINGKAT PENDIDIKAN NAMA',
        'nama_pendidikan': 'PENDIDIKAN NAMA',
        'golru': 'GOL AKHIR NAMA',
        'nama_jabatan': 'JABATAN NAMA',
        'unor_nama': 'UNOR NAMA'
    }
}

COMPARE_FIELDS = ['jenjang_pendidikan', 'golru', 'nama_jabatan', 'satker']
FIELD_LABELS = {
    'jenjang_pendidikan': 'Jenjang Pendidikan',
    'golru': 'Golru',
    'nama_jabatan': 'Nama Jabatan',
    'satker': 'Satuan Kerja'
}

# Daftar Satker Pusat untuk ekstraksi dari SIASN
SATKER_PUSAT = [
    'BIRO SUMBER DAYA MANUSIA',
    'BIRO LOGISTIK',
    'BIRO PENGADAAN BARANG /JASA DAN BARANG MILIK NEGARA',
    'BIRO PARTISIPASI DAN HUBUNGAN MASYARAKAT',
    'BIRO TEKNIS PENYELENGGARAAN PEMILU',
    'BIRO KEUANGAN',
    'BIRO UMUM',
    'BIRO PERENCANAAN DAN ORGANISASI',
    'BIRO HUKUM',
    'PUSAT DATA DAN TEKNOLOGI INFORMASI',
    'INSPEKTORAT UTAMA',
    'PUSAT PENGEMBANGAN KOMPETENSI SUMBER DAYA MANUSIA',
]

# Prefix untuk menentukan satker SIMPEG dari kolom Unor
SATKER_PREFIXES = ['BIRO', 'SEKRETARIAT', 'PUSAT', 'INSPEKTORAT UTAMA']

# Server-side storage (instead of session cookies which have size limits)
DATA_STORE = {
    'discrepancies': [],
    'stats': {},
    'discrepancies_dict': {},  # Indexed by NIP for fast lookup
    'only_in_simpeg': [],  # NIPs that exist only in SIMPEG
    'only_in_siasn': [],   # NIPs that exist only in SIASN
    'field_counts': {}     # Count of discrepancies per field type
}

# Job title equivalency dictionary (loaded from DatayangSama.xlsx)
JOB_TITLE_EQUIVALENCIES = {}

# Provinsi mapping dictionary (loaded from Provinsi.xlsx)
PROVINSI_MAPPING = {}


def load_job_title_equivalencies():
    """
    Load job title equivalencies from DatayangSama.xlsx
    Creates bidirectional lookup dictionary
    """
    global JOB_TITLE_EQUIVALENCIES
    try:
        excel_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'DatayangSama.xlsx')
        if os.path.exists(excel_path):
            df = pd.read_excel(excel_path, engine='openpyxl')
            # Create bidirectional mapping
            for _, row in df.iterrows():
                jab1 = str(row.get('Jabatan 1', '')).strip().upper()
                jab2 = str(row.get('Jabatan 2', '')).strip().upper()
                if jab1 and jab2 and jab1 != 'nan' and jab2 != 'nan':
                    JOB_TITLE_EQUIVALENCIES[jab1] = jab2
                    JOB_TITLE_EQUIVALENCIES[jab2] = jab1
            logger.info(f"✓ Loaded {len(JOB_TITLE_EQUIVALENCIES)} job title equivalencies")
        else:
            logger.warning(f"⚠ DatayangSama.xlsx not found at {excel_path}")
    except Exception as e:
        logger.error(f"❌ Error loading job title equivalencies: {e}")

def normalize_job_title(title):
    """
    Normalize job title for comparison:
    - Convert to uppercase
    - Normalize 'SUB BAGIAN' to 'SUBBAGIAN'
    - Normalize 'KOMISI PEMILIHAN UMUM' to 'KPU'
    - Normalize 'KOMISI INDEPENDEN PEMILIHAN' to 'KIP'
    - Normalize 'ASSESSOR' to 'ASESSOR'
    - Normalize 'PEMILIHAN UMUM' to 'PEMILU'
    - Normalize functional position patterns
    - Remove extra whitespace
    - Handle special characters
    """
    if not title:
        return ''
    normalized = str(title).strip().upper()
    # Remove special characters like Â (non-breaking space)
    normalized = normalized.replace('\xa0', ' ').replace('Â', '')
    # Normalize SUB BAGIAN to SUBBAGIAN
    normalized = re.sub(r'SUB\s+BAGIAN', 'SUBBAGIAN', normalized)
    # Normalize KOMISI PEMILIHAN UMUM to KPU
    normalized = re.sub(r'KOMISI\s+PEMILIHAN\s+UMUM', 'KPU', normalized)
    # Normalize KOMISI INDEPENDEN PEMILIHAN to KIP
    normalized = re.sub(r'KOMISI\s+INDEPENDEN\s+PEMILIHAN', 'KIP', normalized)
    # Normalize ASSESSOR/ASESSOR to ASESOR (standardize to single S)
    normalized = re.sub(r'ASSESSOR', 'ASESOR', normalized)
    normalized = re.sub(r'ASESSOR', 'ASESOR', normalized)
    # Normalize PEMILIHAN UMUM to PEMILU
    normalized = re.sub(r'PEMILIHAN\s+UMUM', 'PEMILU', normalized)
    # Normalize multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip()

def normalize_functional_position(title):
    """
    Normalize functional position patterns to a standard form:
    - 'AHLI PERTAMA - X' → 'X AHLI PERTAMA'
    - 'AHLI MUDA - X' → 'X AHLI MUDA'
    - 'AHLI MADYA - X' → 'X AHLI MADYA'
    - 'TERAMPIL - X' → 'X TERAMPIL'
    """
    normalized = normalize_job_title(title)
    
    # Pattern: "AHLI PERTAMA - PENATA KELOLA PEMILU" → "PENATA KELOLA PEMILU AHLI PERTAMA"
    patterns = [
        (r'^AHLI\s+PERTAMA\s*-\s*(.+)$', r'\1 AHLI PERTAMA'),
        (r'^AHLI\s+MUDA\s*-\s*(.+)$', r'\1 AHLI MUDA'),
        (r'^AHLI\s+MADYA\s*-\s*(.+)$', r'\1 AHLI MADYA'),
        (r'^TERAMPIL\s*-\s*(.+)$', r'\1 TERAMPIL'),
        # Also handle the reverse pattern to normalize both directions
        (r'^(.+)\s+AHLI\s+PERTAMA$', r'\1 AHLI PERTAMA'),
        (r'^(.+)\s+AHLI\s+MUDA$', r'\1 AHLI MUDA'),
        (r'^(.+)\s+AHLI\s+MADYA$', r'\1 AHLI MADYA'),
        (r'^(.+)\s+TERAMPIL$', r'\1 TERAMPIL'),
    ]
    
    for pattern, replacement in patterns:
        match = re.match(pattern, normalized)
        if match:
            normalized = re.sub(pattern, replacement, normalized)
            break
    
    return normalized.strip()

def job_titles_are_equal(title1, title2):
    """
    Check if two job titles are equivalent:
    1. Direct match after normalization
    2. Match after functional position normalization
    3. Lookup in equivalency dictionary (with normalized keys)
    """
    norm1 = normalize_job_title(title1)
    norm2 = normalize_job_title(title2)
    
    # Direct match after basic normalization
    if norm1 == norm2:
        return True
    
    # Try functional position normalization
    func_norm1 = normalize_functional_position(title1)
    func_norm2 = normalize_functional_position(title2)
    
    if func_norm1 == func_norm2:
        return True
    
    # Check equivalency dictionary with normalized keys
    if norm1 in JOB_TITLE_EQUIVALENCIES:
        equiv = normalize_job_title(JOB_TITLE_EQUIVALENCIES[norm1])
        if equiv == norm2:
            return True
    
    if norm2 in JOB_TITLE_EQUIVALENCIES:
        equiv = normalize_job_title(JOB_TITLE_EQUIVALENCIES[norm2])
        if equiv == norm1:
            return True
    
    # Also try with functional normalization on equivalencies
    if func_norm1 in JOB_TITLE_EQUIVALENCIES:
        equiv = normalize_functional_position(JOB_TITLE_EQUIVALENCIES.get(func_norm1, ''))
        if equiv == func_norm2:
            return True
    
    if func_norm2 in JOB_TITLE_EQUIVALENCIES:
        equiv = normalize_functional_position(JOB_TITLE_EQUIVALENCIES.get(func_norm2, ''))
        if equiv == func_norm1:
            return True
    
    return False

# Load equivalencies at startup
load_job_title_equivalencies()

HARDCODED_PROVINSI_MAPPING = {
    # 1. Provinsi Aceh
    "KABUPATEN ACEH BARAT": "ACEH",
    "KABUPATEN ACEH BARAT DAYA": "ACEH",
    "KABUPATEN ACEH BESAR": "ACEH",
    "KABUPATEN ACEH JAYA": "ACEH",
    "KABUPATEN ACEH SELATAN": "ACEH",
    "KABUPATEN ACEH SINGKIL": "ACEH",
    "KABUPATEN ACEH TAMIANG": "ACEH",
    "KABUPATEN ACEH TENGAH": "ACEH",
    "KABUPATEN ACEH TENGGARA": "ACEH",
    "KABUPATEN ACEH TIMUR": "ACEH",
    "KABUPATEN ACEH UTARA": "ACEH",
    "KABUPATEN BENER MERIAH": "ACEH",
    "KABUPATEN BIREUEN": "ACEH",
    "KABUPATEN GAYO LUES": "ACEH",
    "KABUPATEN NAGAN RAYA": "ACEH",
    "KABUPATEN PIDIE": "ACEH",
    "KABUPATEN PIDIE JAYA": "ACEH",
    "KABUPATEN SIMEULUE": "ACEH",
    "KOTA BANDA ACEH": "ACEH",
    "KOTA LANGSA": "ACEH",
    "KOTA LHOKSEUMAWE": "ACEH",
    "KOTA SABANG": "ACEH",
    "KOTA SUBULUSSALAM": "ACEH",

    # 2. Provinsi Bali
    "KABUPATEN BADUNG": "BALI",
    "KABUPATEN BANGLI": "BALI",
    "KABUPATEN BULELENG": "BALI",
    "KABUPATEN GIANYAR": "BALI",
    "KABUPATEN JEMBRANA": "BALI",
    "KABUPATEN KARANGASEM": "BALI",
    "KABUPATEN KLUNGKUNG": "BALI",
    "KABUPATEN TABANAN": "BALI",
    "KOTA DENPASAR": "BALI",

    # 3. Provinsi Banten
    "KABUPATEN LEBAK": "BANTEN",
    "KABUPATEN PANDEGLANG": "BANTEN",
    "KABUPATEN SERANG": "BANTEN",
    "KABUPATEN TANGERANG": "BANTEN",
    "KOTA CILEGON": "BANTEN",
    "KOTA SERANG": "BANTEN",
    "KOTA TANGERANG": "BANTEN",
    "KOTA TANGERANG SELATAN": "BANTEN",

    # 4. Provinsi Bengkulu
    "KABUPATEN BENGKULU SELATAN": "BENGKULU",
    "KABUPATEN BENGKULU TENGAH": "BENGKULU",
    "KABUPATEN BENGKULU UTARA": "BENGKULU",
    "KABUPATEN KAUR": "BENGKULU",
    "KABUPATEN KEPAHIANG": "BENGKULU",
    "KABUPATEN LEBONG": "BENGKULU",
    "KABUPATEN MUKOMUKO": "BENGKULU",
    "KABUPATEN REJANG LEBONG": "BENGKULU",
    "KABUPATEN SELUMA": "BENGKULU",
    "KOTA BENGKULU": "BENGKULU",

    # 5. Provinsi D.I. Yogyakarta
    "KABUPATEN BANTUL": "DAERAH ISTIMEWA YOGYAKARTA",
    "KABUPATEN GUNUNGKIDUL": "DAERAH ISTIMEWA YOGYAKARTA",
    "KABUPATEN KULON PROGO": "DAERAH ISTIMEWA YOGYAKARTA",
    "KABUPATEN SLEMAN": "DAERAH ISTIMEWA YOGYAKARTA",
    "KOTA YOGYAKARTA": "DAERAH ISTIMEWA YOGYAKARTA",

    # 6. Provinsi DKI Jakarta
    "KABUPATEN KEPULAUAN SERIBU": "DKI JAKARTA",
    "KOTA JAKARTA BARAT": "DKI JAKARTA",
    "KOTA JAKARTA PUSAT": "DKI JAKARTA",
    "KOTA JAKARTA SELATAN": "DKI JAKARTA",
    "KOTA JAKARTA TIMUR": "DKI JAKARTA",
    "KOTA JAKARTA UTARA": "DKI JAKARTA",

    # 7. Provinsi Gorontalo
    "KABUPATEN BOALEMO": "GORONTALO",
    "KABUPATEN BONE BOLANGO": "GORONTALO",
    "KABUPATEN GORONTALO": "GORONTALO",
    "KABUPATEN GORONTALO UTARA": "GORONTALO",
    "KABUPATEN PAHUWATO": "GORONTALO",
    "KOTA GORONTALO": "GORONTALO",

    # 8. Provinsi Jambi
    "KABUPATEN BATANGHARI": "JAMBI",
    "KABUPATEN BUNGO": "JAMBI",
    "KABUPATEN KERINCI": "JAMBI",
    "KABUPATEN MERANGIN": "JAMBI",
    "KABUPATEN MUARO JAMBI": "JAMBI",
    "KABUPATEN SAROLANGUN": "JAMBI",
    "KABUPATEN TANJUNG JABUNG BARAT": "JAMBI",
    "KABUPATEN TANJUNG JABUNG TIMUR": "JAMBI",
    "KABUPATEN TEBO": "JAMBI",
    "KOTA JAMBI": "JAMBI",
    "KOTA SUNGAI PENUH": "JAMBI",

    # 9. Provinsi Jawa Barat
    "KABUPATEN BANDUNG": "JAWA BARAT",
    "KABUPATEN BANDUNG BARAT": "JAWA BARAT",
    "KABUPATEN BEKASI": "JAWA BARAT",
    "KABUPATEN BOGOR": "JAWA BARAT",
    "KABUPATEN CIAMIS": "JAWA BARAT",
    "KABUPATEN CIANJUR": "JAWA BARAT",
    "KABUPATEN CIREBON": "JAWA BARAT",
    "KABUPATEN GARUT": "JAWA BARAT",
    "KABUPATEN INDRAMAYU": "JAWA BARAT",
    "KABUPATEN KARAWANG": "JAWA BARAT",
    "KABUPATEN KUNINGAN": "JAWA BARAT",
    "KABUPATEN MAJALENGKA": "JAWA BARAT",
    "KABUPATEN PANGANDARAN": "JAWA BARAT",
    "KABUPATEN PURWAKARTA": "JAWA BARAT",
    "KABUPATEN SUBANG": "JAWA BARAT",
    "KABUPATEN SUKABUMI": "JAWA BARAT",
    "KABUPATEN SUMEDANG": "JAWA BARAT",
    "KABUPATEN TASIKMALAYA": "JAWA BARAT",
    "KOTA BANDUNG": "JAWA BARAT",
    "KOTA BANJAR": "JAWA BARAT",
    "KOTA BEKASI": "JAWA BARAT",
    "KOTA BOGOR": "JAWA BARAT",
    "KOTA CIMAHI": "JAWA BARAT",
    "KOTA CIREBON": "JAWA BARAT",
    "KOTA DEPOK": "JAWA BARAT",
    "KOTA SUKABUMI": "JAWA BARAT",
    "KOTA TASIKMALAYA": "JAWA BARAT",

    # 10. Provinsi Jawa Tengah
    "KABUPATEN BANJARNEGARA": "JAWA TENGAH",
    "KABUPATEN BANYUMAS": "JAWA TENGAH",
    "KABUPATEN BATANG": "JAWA TENGAH",
    "KABUPATEN BLORA": "JAWA TENGAH",
    "KABUPATEN BOYOLALI": "JAWA TENGAH",
    "KABUPATEN BREBES": "JAWA TENGAH",
    "KABUPATEN CILACAP": "JAWA TENGAH",
    "KABUPATEN DEMAK": "JAWA TENGAH",
    "KABUPATEN GROBOGAN": "JAWA TENGAH",
    "KABUPATEN JEPARA": "JAWA TENGAH",
    "KABUPATEN KARANGANYAR": "JAWA TENGAH",
    "KABUPATEN KEBUMEN": "JAWA TENGAH",
    "KABUPATEN KENDAL": "JAWA TENGAH",
    "KABUPATEN KLATEN": "JAWA TENGAH",
    "KABUPATEN KUDUS": "JAWA TENGAH",
    "KABUPATEN MAGELANG": "JAWA TENGAH",
    "KABUPATEN PATI": "JAWA TENGAH",
    "KABUPATEN PEKALONGAN": "JAWA TENGAH",
    "KABUPATEN PEMALANG": "JAWA TENGAH",
    "KABUPATEN PURBALINGGA": "JAWA TENGAH",
    "KABUPATEN PURWOREJO": "JAWA TENGAH",
    "KABUPATEN REMBANG": "JAWA TENGAH",
    "KABUPATEN SEMARANG": "JAWA TENGAH",
    "KABUPATEN SRAGEN": "JAWA TENGAH",
    "KABUPATEN SUKOHARJO": "JAWA TENGAH",
    "KABUPATEN TEGAL": "JAWA TENGAH",
    "KABUPATEN TEMANGGUNG": "JAWA TENGAH",
    "KABUPATEN WONOGIRI": "JAWA TENGAH",
    "KABUPATEN WONOSOBO": "JAWA TENGAH",
    "KOTA MAGELANG": "JAWA TENGAH",
    "KOTA PEKALONGAN": "JAWA TENGAH",
    "KOTA SALATIGA": "JAWA TENGAH",
    "KOTA SEMARANG": "JAWA TENGAH",
    "KOTA SURAKARTA": "JAWA TENGAH",
    "KOTA TEGAL": "JAWA TENGAH",

    # 11. Provinsi Jawa Timur
    "KABUPATEN BANGKALAN": "JAWA TIMUR",
    "KABUPATEN BANYUWANGI": "JAWA TIMUR",
    "KABUPATEN BLITAR": "JAWA TIMUR",
    "KABUPATEN BOJONEGORO": "JAWA TIMUR",
    "KABUPATEN BONDOWOSO": "JAWA TIMUR",
    "KABUPATEN GRESIK": "JAWA TIMUR",
    "KABUPATEN JEMBER": "JAWA TIMUR",
    "KABUPATEN JOMBANG": "JAWA TIMUR",
    "KABUPATEN KEDIRI": "JAWA TIMUR",
    "KABUPATEN LAMONGAN": "JAWA TIMUR",
    "KABUPATEN LUMAJANG": "JAWA TIMUR",
    "KABUPATEN MADIUN": "JAWA TIMUR",
    "KABUPATEN MAGETAN": "JAWA TIMUR",
    "KABUPATEN MALANG": "JAWA TIMUR",
    "KABUPATEN MOJOKERTO": "JAWA TIMUR",
    "KABUPATEN NGANJUK": "JAWA TIMUR",
    "KABUPATEN NGAWI": "JAWA TIMUR",
    "KABUPATEN PACITAN": "JAWA TIMUR",
    "KABUPATEN PAMEKASAN": "JAWA TIMUR",
    "KABUPATEN PASURUAN": "JAWA TIMUR",
    "KABUPATEN PONOROGO": "JAWA TIMUR",
    "KABUPATEN PROBOLINGGO": "JAWA TIMUR",
    "KABUPATEN SAMPANG": "JAWA TIMUR",
    "KABUPATEN SIDOARJO": "JAWA TIMUR",
    "KABUPATEN SITUBONDO": "JAWA TIMUR",
    "KABUPATEN SUMENEP": "JAWA TIMUR",
    "KABUPATEN TRENGGALEK": "JAWA TIMUR",
    "KABUPATEN TUBAN": "JAWA TIMUR",
    "KABUPATEN TULUNGAGUNG": "JAWA TIMUR",
    "KOTA BATU": "JAWA TIMUR",
    "KOTA BLITAR": "JAWA TIMUR",
    "KOTA KEDIRI": "JAWA TIMUR",
    "KOTA MADIUN": "JAWA TIMUR",
    "KOTA MALANG": "JAWA TIMUR",
    "KOTA MOJOKERTO": "JAWA TIMUR",
    "KOTA PASURUAN": "JAWA TIMUR",
    "KOTA PROBOLINGGO": "JAWA TIMUR",
    "KOTA SURABAYA": "JAWA TIMUR",

    # 12. Provinsi Kalimantan Barat
    "KABUPATEN BENGKAYANG": "KALIMANTAN BARAT",
    "KABUPATEN KAPUAS HULU": "KALIMANTAN BARAT",
    "KABUPATEN KAYONG UTARA": "KALIMANTAN BARAT",
    "KABUPATEN KETAPANG": "KALIMANTAN BARAT",
    "KABUPATEN KUBU RAYA": "KALIMANTAN BARAT",
    "KABUPATEN LANDAK": "KALIMANTAN BARAT",
    "KABUPATEN MELAWI": "KALIMANTAN BARAT",
    "KABUPATEN MEMPAWAH": "KALIMANTAN BARAT",
    "KABUPATEN SAMBAS": "KALIMANTAN BARAT",
    "KABUPATEN SANGGAU": "KALIMANTAN BARAT",
    "KABUPATEN SEKADAU": "KALIMANTAN BARAT",
    "KABUPATEN SINTANG": "KALIMANTAN BARAT",
    "KOTA PONTIANAK": "KALIMANTAN BARAT",
    "KOTA SINGKAWANG": "KALIMANTAN BARAT",

    # 13. Provinsi Kalimantan Selatan
    "KABUPATEN BALANGAN": "KALIMANTAN SELATAN",
    "KABUPATEN BANJAR": "KALIMANTAN SELATAN",
    "KABUPATEN BARITO KUALA": "KALIMANTAN SELATAN",
    "KABUPATEN HULU SUNGAI SELATAN": "KALIMANTAN SELATAN",
    "KABUPATEN HULU SUNGAI TENGAH": "KALIMANTAN SELATAN",
    "KABUPATEN HULU SUNGAI UTARA": "KALIMANTAN SELATAN",
    "KABUPATEN KOTABARU": "KALIMANTAN SELATAN",
    "KABUPATEN TABALONG": "KALIMANTAN SELATAN",
    "KABUPATEN TANAH BUMBU": "KALIMANTAN SELATAN",
    "KABUPATEN TANAH LAUT": "KALIMANTAN SELATAN",
    "KABUPATEN TAPIN": "KALIMANTAN SELATAN",
    "KOTA BANJARBARU": "KALIMANTAN SELATAN",
    "KOTA BANJARMASIN": "KALIMANTAN SELATAN",

    # 14. Provinsi Kalimantan Tengah
    "KABUPATEN BARITO SELATAN": "KALIMANTAN TENGAH",
    "KABUPATEN BARITO TIMUR": "KALIMANTAN TENGAH",
    "KABUPATEN BARITO UTARA": "KALIMANTAN TENGAH",
    "KABUPATEN GUNUNG MAS": "KALIMANTAN TENGAH",
    "KABUPATEN KAPUAS": "KALIMANTAN TENGAH",
    "KABUPATEN KATINGAN": "KALIMANTAN TENGAH",
    "KABUPATEN KOTAWARINGIN BARAT": "KALIMANTAN TENGAH",
    "KABUPATEN KOTAWARINGIN TIMUR": "KALIMANTAN TENGAH",
    "KABUPATEN LAMANDAU": "KALIMANTAN TENGAH",
    "KABUPATEN MURUNG RAYA": "KALIMANTAN TENGAH",
    "KABUPATEN PULANG PISAU": "KALIMANTAN TENGAH",
    "KABUPATEN SERUYAN": "KALIMANTAN TENGAH",
    "KABUPATEN SUKAMARA": "KALIMANTAN TENGAH",
    "KOTA PALANGKARAYA": "KALIMANTAN TENGAH",

    # 15. Provinsi Kalimantan Timur
    "KABUPATEN BERAU": "KALIMANTAN TIMUR",
    "KABUPATEN KUTAI BARAT": "KALIMANTAN TIMUR",
    "KABUPATEN KUTAI KARTANEGARA": "KALIMANTAN TIMUR",
    "KABUPATEN KUTAI TIMUR": "KALIMANTAN TIMUR",
    "KABUPATEN MAHAKAM ULU": "KALIMANTAN TIMUR",
    "KABUPATEN PASER": "KALIMANTAN TIMUR",
    "KABUPATEN PENAJAM PASER UTARA": "KALIMANTAN TIMUR",
    "KOTA BALIKPAPAN": "KALIMANTAN TIMUR",
    "KOTA BONTANG": "KALIMANTAN TIMUR",
    "KOTA SAMARINDA": "KALIMANTAN TIMUR",

    # 16. Provinsi Kalimantan Utara
    "KABUPATEN BULUNGAN": "KALIMANTAN UTARA",
    "KABUPATEN MALINAU": "KALIMANTAN UTARA",
    "KABUPATEN NUNUKAN": "KALIMANTAN UTARA",
    "KABUPATEN TANA TIDUNG": "KALIMANTAN UTARA",
    "KOTA TARAKAN": "KALIMANTAN UTARA",

    # 17. Provinsi Kepulauan Bangka Belitung
    "KABUPATEN BANGKA": "KEPULAUAN BANGKA BELITUNG",
    "KABUPATEN BANGKA BARAT": "KEPULAUAN BANGKA BELITUNG",
    "KABUPATEN BANGKA SELATAN": "KEPULAUAN BANGKA BELITUNG",
    "KABUPATEN BANGKA TENGAH": "KEPULAUAN BANGKA BELITUNG",
    "KABUPATEN BELITUNG": "KEPULAUAN BANGKA BELITUNG",
    "KABUPATEN BELITUNG TIMUR": "KEPULAUAN BANGKA BELITUNG",
    "KOTA PANGKALPINANG": "KEPULAUAN BANGKA BELITUNG",

    # 18. Provinsi Kepulauan Riau
    "KABUPATEN BINTAN": "KEPULAUAN RIAU",
    "KABUPATEN KARIMUN": "KEPULAUAN RIAU",
    "KABUPATEN KEPULAUAN ANAMBAS": "KEPULAUAN RIAU",
    "KABUPATEN LINGGA": "KEPULAUAN RIAU",
    "KABUPATEN NATUNA": "KEPULAUAN RIAU",
    "KOTA BATAM": "KEPULAUAN RIAU",
    "KOTA TANJUNGPINANG": "KEPULAUAN RIAU",

    # 19. Provinsi Lampung
    "KABUPATEN LAMPUNG BARAT": "LAMPUNG",
    "KABUPATEN LAMPUNG SELATAN": "LAMPUNG",
    "KABUPATEN LAMPUNG TENGAH": "LAMPUNG",
    "KABUPATEN LAMPUNG TIMUR": "LAMPUNG",
    "KABUPATEN LAMPUNG UTARA": "LAMPUNG",
    "KABUPATEN MESUJI": "LAMPUNG",
    "KABUPATEN PESAWARAN": "LAMPUNG",
    "KABUPATEN PESISIR BARAT": "LAMPUNG",
    "KABUPATEN PRINGSEWU": "LAMPUNG",
    "KABUPATEN TANGGAMUS": "LAMPUNG",
    "KABUPATEN TULANG BAWANG": "LAMPUNG",
    "KABUPATEN TULANG BAWANG BARAT": "LAMPUNG",
    "KABUPATEN WAY KANAN": "LAMPUNG",
    "KOTA BANDAR LAMPUNG": "LAMPUNG",
    "KOTA METRO": "LAMPUNG",

    # 20. Provinsi Maluku
    "KABUPATEN BURU": "MALUKU",
    "KABUPATEN BURU SELATAN": "MALUKU",
    "KABUPATEN KEPULAUAN ARU": "MALUKU",
    "KABUPATEN KEPULAUAN TANIMBAR": "MALUKU",
    "KABUPATEN MALUKU BARAT DAYA": "MALUKU",
    "KABUPATEN MALUKU TENGAH": "MALUKU",
    "KABUPATEN MALUKU TENGGARA": "MALUKU",
    "KABUPATEN SERAM BAGIAN BARAT": "MALUKU",
    "KABUPATEN SERAM BAGIAN TIMUR": "MALUKU",
    "KOTA AMBON": "MALUKU",
    "KOTA TUAL": "MALUKU",

    # 21. Provinsi Maluku Utara
    "KABUPATEN HALMAHERA BARAT": "MALUKU UTARA",
    "KABUPATEN HALMAHERA SELATAN": "MALUKU UTARA",
    "KABUPATEN HALMAHERA TENGAH": "MALUKU UTARA",
    "KABUPATEN HALMAHERA TIMUR": "MALUKU UTARA",
    "KABUPATEN HALMAHERA UTARA": "MALUKU UTARA",
    "KABUPATEN KEPULAUAN SULA": "MALUKU UTARA",
    "KABUPATEN PULAU MOROTAI": "MALUKU UTARA",
    "KABUPATEN PULAU TALIABU": "MALUKU UTARA",
    "KOTA TERNATE": "MALUKU UTARA",
    "KOTA TIDORE KEPULAUAN": "MALUKU UTARA",

    # 22. Provinsi Nusa Tenggara Barat
    "KABUPATEN BIMA": "NUSA TENGGARA BARAT",
    "KABUPATEN DOMPU": "NUSA TENGGARA BARAT",
    "KABUPATEN LOMBOK BARAT": "NUSA TENGGARA BARAT",
    "KABUPATEN LOMBOK TENGAH": "NUSA TENGGARA BARAT",
    "KABUPATEN LOMBOK TIMUR": "NUSA TENGGARA BARAT",
    "KABUPATEN LOMBOK UTARA": "NUSA TENGGARA BARAT",
    "KABUPATEN SUMBAWA": "NUSA TENGGARA BARAT",
    "KABUPATEN SUMBAWA BARAT": "NUSA TENGGARA BARAT",
    "KOTA BIMA": "NUSA TENGGARA BARAT",
    "KOTA MATARAM": "NUSA TENGGARA BARAT",

    # 23. Provinsi Nusa Tenggara Timur
    "KABUPATEN ALOR": "NUSA TENGGARA TIMUR",
    "KABUPATEN BELU": "NUSA TENGGARA TIMUR",
    "KABUPATEN ENDE": "NUSA TENGGARA TIMUR",
    "KABUPATEN FLORES TIMUR": "NUSA TENGGARA TIMUR",
    "KABUPATEN KUPANG": "NUSA TENGGARA TIMUR",
    "KABUPATEN LEMBATA": "NUSA TENGGARA TIMUR",
    "KABUPATEN MALAKA": "NUSA TENGGARA TIMUR",
    "KABUPATEN MANGGARAI": "NUSA TENGGARA TIMUR",
    "KABUPATEN MANGGARAI BARAT": "NUSA TENGGARA TIMUR",
    "KABUPATEN MANGGARAI TIMUR": "NUSA TENGGARA TIMUR",
    "KABUPATEN NAGEKEO": "NUSA TENGGARA TIMUR",
    "KABUPATEN NGADA": "NUSA TENGGARA TIMUR",
    "KABUPATEN ROTE NDAO": "NUSA TENGGARA TIMUR",
    "KABUPATEN SABU RAIJUA": "NUSA TENGGARA TIMUR",
    "KABUPATEN SIKKA": "NUSA TENGGARA TIMUR",
    "KABUPATEN SUMBA BARAT": "NUSA TENGGARA TIMUR",
    "KABUPATEN SUMBA BARAT DAYA": "NUSA TENGGARA TIMUR",
    "KABUPATEN SUMBA TENGAH": "NUSA TENGGARA TIMUR",
    "KABUPATEN SUMBA TIMUR": "NUSA TENGGARA TIMUR",
    "KABUPATEN TIMOR TENGAH SELATAN": "NUSA TENGGARA TIMUR",
    "KABUPATEN TIMOR TENGAH UTARA": "NUSA TENGGARA TIMUR",
    "KOTA KUPANG": "NUSA TENGGARA TIMUR",

    # 24. Provinsi Papua
    "KABUPATEN BIAK NUMFOR": "PAPUA",
    "KABUPATEN JAYAPURA": "PAPUA",
    "KABUPATEN KEEROM": "PAPUA",
    "KABUPATEN KEPULAUAN YAPEN": "PAPUA",
    "KABUPATEN MAMBERAMO RAYA": "PAPUA",
    "KABUPATEN SARMI": "PAPUA",
    "KABUPATEN SUPIORI": "PAPUA",
    "KABUPATEN WAROPEN": "PAPUA",
    "KOTA JAYAPURA": "PAPUA",

    # 25. Provinsi Papua Barat
    "KABUPATEN FAKFAK": "PAPUA BARAT",
    "KABUPATEN KAIMANA": "PAPUA BARAT",
    "KABUPATEN MANOKWARI": "PAPUA BARAT",
    "KABUPATEN MANOKWARI SELATAN": "PAPUA BARAT",
    "KABUPATEN PEGUNUNGAN ARFAK": "PAPUA BARAT",
    "KABUPATEN TELUK BINTUNI": "PAPUA BARAT",
    "KABUPATEN TELUK WONDAMA": "PAPUA BARAT",

    # 26. Provinsi Papua Barat Daya
    "KABUPATEN MAYBRAT": "PAPUA BARAT DAYA",
    "KABUPATEN RAJA AMPAT": "PAPUA BARAT DAYA",
    "KABUPATEN SORONG": "PAPUA BARAT DAYA",
    "KABUPATEN SORONG SELATAN": "PAPUA BARAT DAYA",
    "KABUPATEN TAMBRAUW": "PAPUA BARAT DAYA",
    "KOTA SORONG": "PAPUA BARAT DAYA",

    # 27. Provinsi Papua Pegunungan
    "KABUPATEN JAYAWIJAYA": "PAPUA PEGUNUNGAN",
    "KABUPATEN LANNY JAYA": "PAPUA PEGUNUNGAN",
    "KABUPATEN MAMBERAMO TENGAH": "PAPUA PEGUNUNGAN",
    "KABUPATEN NDUGA": "PAPUA PEGUNUNGAN",
    "KABUPATEN PEGUNUNGAN BINTANG": "PAPUA PEGUNUNGAN",
    "KABUPATEN TOLIKARA": "PAPUA PEGUNUNGAN",
    "KABUPATEN YAHUKIMO": "PAPUA PEGUNUNGAN",
    "KABUPATEN YALIMO": "PAPUA PEGUNUNGAN",

    # 28. Provinsi Papua Selatan
    "KABUPATEN ASMAT": "PAPUA SELATAN",
    "KABUPATEN BOVEN DIGOEL": "PAPUA SELATAN",
    "KABUPATEN MAPPI": "PAPUA SELATAN",
    "KABUPATEN MERAUKE": "PAPUA SELATAN",

    # 29. Provinsi Papua Tengah
    "KABUPATEN DEIYAI": "PAPUA TENGAH",
    "KABUPATEN DOGIYAI": "PAPUA TENGAH",
    "KABUPATEN INTAN JAYA": "PAPUA TENGAH",
    "KABUPATEN MIMIKA": "PAPUA TENGAH",
    "KABUPATEN NABIRE": "PAPUA TENGAH",
    "KABUPATEN PANIAI": "PAPUA TENGAH",
    "KABUPATEN PUNCAK": "PAPUA TENGAH",
    "KABUPATEN PUNCAK JAYA": "PAPUA TENGAH",

    # 30. Provinsi Riau
    "KABUPATEN BENGKALIS": "RIAU",
    "KABUPATEN INDRAGIRI HILIR": "RIAU",
    "KABUPATEN INDRAGIRI HULU": "RIAU",
    "KABUPATEN KAMPAR": "RIAU",
    "KABUPATEN KEPULAUAN MERANTI": "RIAU",
    "KABUPATEN KUANTAN SINGINGI": "RIAU",
    "KABUPATEN PELALAWAN": "RIAU",
    "KABUPATEN ROKAN HILIR": "RIAU",
    "KABUPATEN ROKAN HULU": "RIAU",
    "KABUPATEN SIAK": "RIAU",
    "KOTA DUMAI": "RIAU",
    "KOTA PEKANBARU": "RIAU",

    # 31. Provinsi Sulawesi Barat
    "KABUPATEN MAJENE": "SULAWESI BARAT",
    "KABUPATEN MAMASA": "SULAWESI BARAT",
    "KABUPATEN MAMUJU": "SULAWESI BARAT",
    "KABUPATEN MAMUJU TENGAH": "SULAWESI BARAT",
    "KABUPATEN PASANGKAYU": "SULAWESI BARAT",
    "KABUPATEN POLEWALI MANDAR": "SULAWESI BARAT",

    # 32. Provinsi Sulawesi Selatan
    "KABUPATEN BANTAENG": "SULAWESI SELATAN",
    "KABUPATEN BARRU": "SULAWESI SELATAN",
    "KABUPATEN BONE": "SULAWESI SELATAN",
    "KABUPATEN BULUKUMBA": "SULAWESI SELATAN",
    "KABUPATEN ENREKANG": "SULAWESI SELATAN",
    "KABUPATEN GOWA": "SULAWESI SELATAN",
    "KABUPATEN JENEPONTO": "SULAWESI SELATAN",
    "KABUPATEN KEPULAUAN SELAYAR": "SULAWESI SELATAN",
    "KABUPATEN LUWU": "SULAWESI SELATAN",
    "KABUPATEN LUWU TIMUR": "SULAWESI SELATAN",
    "KABUPATEN LUWU UTARA": "SULAWESI SELATAN",
    "KABUPATEN MAROS": "SULAWESI SELATAN",
    "KABUPATEN PANGKAJENE DAN KEPULAUAN": "SULAWESI SELATAN",
    "KABUPATEN PINRANG": "SULAWESI SELATAN",
    "KABUPATEN SIDENRENG RAPPANG": "SULAWESI SELATAN",
    "KABUPATEN SINJAI": "SULAWESI SELATAN",
    "KABUPATEN SOPPENG": "SULAWESI SELATAN",
    "KABUPATEN TAKALAR": "SULAWESI SELATAN",
    "KABUPATEN TANA TORAJA": "SULAWESI SELATAN",
    "KABUPATEN TORAJA UTARA": "SULAWESI SELATAN",
    "KABUPATEN WAJO": "SULAWESI SELATAN",
    "KOTA MAKASSAR": "SULAWESI SELATAN",
    "KOTA PALOPO": "SULAWESI SELATAN",
    "KOTA PARE PARE": "SULAWESI SELATAN",

    # 33. Provinsi Sulawesi Tengah
    "KABUPATEN BANGGAI": "SULAWESI TENGAH",
    "KABUPATEN BANGGAI KEPULAUAN": "SULAWESI TENGAH",
    "KABUPATEN BANGGAI LAUT": "SULAWESI TENGAH",
    "KABUPATEN BUOL": "SULAWESI TENGAH",
    "KABUPATEN DONGGALA": "SULAWESI TENGAH",
    "KABUPATEN MOROWALI": "SULAWESI TENGAH",
    "KABUPATEN MOROWALI UTARA": "SULAWESI TENGAH",
    "KABUPATEN PARIGI MOUTONG": "SULAWESI TENGAH",
    "KABUPATEN POSO": "SULAWESI TENGAH",
    "KABUPATEN SIGI": "SULAWESI TENGAH",
    "KABUPATEN TOJO UNA": "SULAWESI TENGAH",
    "KABUPATEN TOLITOLI": "SULAWESI TENGAH",
    "KOTA PALU": "SULAWESI TENGAH",

    # 34. Provinsi Sulawesi Tenggara
    "KABUPATEN BOMBANA": "SULAWESI TENGGARA",
    "KABUPATEN BUTON": "SULAWESI TENGGARA",
    "KABUPATEN BUTON SELATAN": "SULAWESI TENGGARA",
    "KABUPATEN BUTON TENGAH": "SULAWESI TENGGARA",
    "KABUPATEN BUTON UTARA": "SULAWESI TENGGARA",
    "KABUPATEN KOLAKA": "SULAWESI TENGGARA",
    "KABUPATEN KOLAKA TIMUR": "SULAWESI TENGGARA",
    "KABUPATEN KOLAKA UTARA": "SULAWESI TENGGARA",
    "KABUPATEN KONAWE": "SULAWESI TENGGARA",
    "KABUPATEN KONAWE KEPULAUAN": "SULAWESI TENGGARA",
    "KABUPATEN KONAWE SELATAN": "SULAWESI TENGGARA",
    "KABUPATEN KONAWE UTARA": "SULAWESI TENGGARA",
    "KABUPATEN MUNA": "SULAWESI TENGGARA",
    "KABUPATEN MUNA BARAT": "SULAWESI TENGGARA",
    "KABUPATEN WAKATOBI": "SULAWESI TENGGARA",
    "KOTA BAU BAU": "SULAWESI TENGGARA",
    "KOTA KENDARI": "SULAWESI TENGGARA",

    # 35. Provinsi Sulawesi Utara
    "KABUPATEN BOLAANG MONGONDOW": "SULAWESI UTARA",
    "KABUPATEN BOLAANG MONGONDOW SELATAN": "SULAWESI UTARA",
    "KABUPATEN BOLAANG MONGONDOW TIMUR": "SULAWESI UTARA",
    "KABUPATEN BOLAANG MONGONDOW UTARA": "SULAWESI UTARA",
    "KABUPATEN KEPULAUAN SANGIHE": "SULAWESI UTARA",
    "KABUPATEN KEPULAUAN SIAU TAGULANDANG BIARO": "SULAWESI UTARA",
    "KABUPATEN KEPULAUAN TALAUD": "SULAWESI UTARA",
    "KABUPATEN MINAHASA": "SULAWESI UTARA",
    "KABUPATEN MINAHASA SELATAN": "SULAWESI UTARA",
    "KABUPATEN MINAHASA TENGGARA": "SULAWESI UTARA",
    "KABUPATEN MINAHASA UTARA": "SULAWESI UTARA",
    "KOTA BITUNG": "SULAWESI UTARA",
    "KOTA KOTAMOBAGU": "SULAWESI UTARA",
    "KOTA MANADO": "SULAWESI UTARA",
    "KOTA TOMOHON": "SULAWESI UTARA",

    # 36. Provinsi Sumatera Barat
    "KABUPATEN AGAM": "SUMATERA BARAT",
    "KABUPATEN DHARMASRAYA": "SUMATERA BARAT",
    "KABUPATEN KEPULAUAN MENTAWAI": "SUMATERA BARAT",
    "KABUPATEN LIMA PULUH KOTA": "SUMATERA BARAT",
    "KABUPATEN PADANG PARIAMAN": "SUMATERA BARAT",
    "KABUPATEN PASAMAN": "SUMATERA BARAT",
    "KABUPATEN PASAMAN BARAT": "SUMATERA BARAT",
    "KABUPATEN PESISIR SELATAN": "SUMATERA BARAT",
    "KABUPATEN SIJUNJUNG": "SUMATERA BARAT",
    "KABUPATEN SOLOK": "SUMATERA BARAT",
    "KABUPATEN SOLOK SELATAN": "SUMATERA BARAT",
    "KABUPATEN TANAH DATAR": "SUMATERA BARAT",
    "KOTA BUKITTINGGI": "SUMATERA BARAT",
    "KOTA PADANG": "SUMATERA BARAT",
    "KOTA PADANG PANJANG": "SUMATERA BARAT",
    "KOTA PARIAMAN": "SUMATERA BARAT",
    "KOTA PAYAKUMBUH": "SUMATERA BARAT",
    "KOTA SAWAHLUNTO": "SUMATERA BARAT",
    "KOTA SOLOK": "SUMATERA BARAT",
    "KABUPATEN LIMA PULUH KOTA": "SUMATERA BARAT",
    "SEKRETARIAT KPU KABUPATEN LIMA PULUH KOTA": "SUMATERA BARAT",
    "SEKRETARIAT KOMISI PEMILIHAN UMUM KABUPATEN LIMA PULUH KOTA": "SUMATERA BARAT",

    # 37. Provinsi Sumatera Selatan
    "KABUPATEN BANYUASIN": "SUMATERA SELATAN",
    "KABUPATEN EMPAT LAWANG": "SUMATERA SELATAN",
    "KABUPATEN LAHAT": "SUMATERA SELATAN",
    "KABUPATEN MUARA ENIM": "SUMATERA SELATAN",
    "KABUPATEN MUSI BANYUASIN": "SUMATERA SELATAN",
    "KABUPATEN MUSI RAWAS": "SUMATERA SELATAN",
    "KABUPATEN MUSI RAWAS UTARA": "SUMATERA SELATAN",
    "KABUPATEN OGAN ILIR": "SUMATERA SELATAN",
    "KABUPATEN OGAN KOMERING ILIR": "SUMATERA SELATAN",
    "KABUPATEN OGAN KOMERING ULU": "SUMATERA SELATAN",
    "KABUPATEN OGAN KOMERING ULU SELATAN": "SUMATERA SELATAN",
    "KABUPATEN OGAN KOMERING ULU TIMUR": "SUMATERA SELATAN",
    "KABUPATEN PENUKAL ABAB LEMATANG ILIR": "SUMATERA SELATAN",
    "KOTA LUBUKLINGGAU": "SUMATERA SELATAN",
    "KOTA PAGAR ALAM": "SUMATERA SELATAN",
    "KOTA PALEMBANG": "SUMATERA SELATAN",
    "KOTA PRABUMULIH": "SUMATERA SELATAN",

    # 38. Provinsi Sumatera Utara
    "KABUPATEN ASAHAN": "SUMATERA UTARA",
    "KABUPATEN BATU BARA": "SUMATERA UTARA",
    "KABUPATEN DAIRI": "SUMATERA UTARA",
    "KABUPATEN DELI SERDANG": "SUMATERA UTARA",
    "KABUPATEN HUMBANG HASUNDUTAN": "SUMATERA UTARA",
    "KABUPATEN KARO": "SUMATERA UTARA",
    "KABUPATEN LABUHANBATU": "SUMATERA UTARA",
    "KABUPATEN LABUHANBATU SELATAN": "SUMATERA UTARA",
    "KABUPATEN LABUHANBATU UTARA": "SUMATERA UTARA",
    "KABUPATEN LANGKAT": "SUMATERA UTARA",
    "KABUPATEN MANDAILING NATAL": "SUMATERA UTARA",
    "KABUPATEN NIAS": "SUMATERA UTARA",
    "KABUPATEN NIAS BARAT": "SUMATERA UTARA",
    "KABUPATEN NIAS SELATAN": "SUMATERA UTARA",
    "KABUPATEN NIAS UTARA": "SUMATERA UTARA",
    "KABUPATEN PADANG LAWAS": "SUMATERA UTARA",
    "KABUPATEN PADANG LAWAS UTARA": "SUMATERA UTARA",
    "KABUPATEN PAKPAK BHARAT": "SUMATERA UTARA",
    "KABUPATEN SAMOSIR": "SUMATERA UTARA",
    "KABUPATEN SERDANG BEDAGAI": "SUMATERA UTARA",
    "KABUPATEN SIMALUNGUN": "SUMATERA UTARA",
    "KABUPATEN TAPANULI SELATAN": "SUMATERA UTARA",
    "KABUPATEN TAPANULI TENGAH": "SUMATERA UTARA",
    "KABUPATEN TAPANULI UTARA": "SUMATERA UTARA",
    "KABUPATEN TOBA": "SUMATERA UTARA",
    "KOTA BINJAI": "SUMATERA UTARA",
    "KOTA GUNUNGSITOLI": "SUMATERA UTARA",
    "KOTA MEDAN": "SUMATERA UTARA",
    "KOTA PADANG SIDEMPUAN": "SUMATERA UTARA",
    "KOTA PEMATANGSIANTAR": "SUMATERA UTARA",
    "KOTA SIBOLGA": "SUMATERA UTARA",
    "KOTA TANJUNG BALAI": "SUMATERA UTARA",
    "KOTA TEBING TINGGI": "SUMATERA UTARA"
}


def load_provinsi_mapping():
    """
    Load provinsi mapping from Provinsi.xlsx
    Membaca setiap sheet untuk mencari mapping KABUPATEN/KOTA -> PROVINSI
    """
    global PROVINSI_MAPPING
    PROVINSI_MAPPING.clear()
    
    excel_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'Provinsi.xlsx')
    if not os.path.exists(excel_path):
        logger.warning(f"⚠️ File mapping provinsi tidak ditemukan: {excel_path}")
        return
        
    try:
        xls = pd.ExcelFile(excel_path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            
            for _, row in df.iterrows():
                # Extract parts by index assuming specific struct (Provinsi, KPU PROVINSI, KPU KAB/KOTA)
                # Handle possible NaN
                prov = str(row.iloc[0]).strip().upper() if len(row) > 0 and pd.notna(row.iloc[0]) else ''
                kpu_prov = str(row.iloc[2]).strip().upper() if len(row) > 2 and pd.notna(row.iloc[2]) else ''
                kpu_kab = str(row.iloc[3]).strip().upper() if len(row) > 3 and pd.notna(row.iloc[3]) else ''
                
                if not prov or prov == 'NAN':
                    continue
                    
                # Kab/Kota match
                match_kab = re.search(r'(KABUPATEN|KOTA)\s+.+', kpu_kab)
                if match_kab:
                    area = match_kab.group(0)
                    area = re.sub(r'KOTA([A-Z])', r'KOTA \1', area)
                    area = re.sub(r'KABUPATEN([A-Z])', r'KABUPATEN \1', area)
                    area = re.sub(r'\s+', ' ', area).strip()
                    PROVINSI_MAPPING[area] = prov
                
                # Provinsi match
                match_prov = re.search(r'PROVINSI\s+(.+)', kpu_prov)
                if match_prov:
                    prov_name = match_prov.group(1).strip()
                    PROVINSI_MAPPING[f"PROVINSI {prov_name}"] = prov
                else:
                    PROVINSI_MAPPING[f"PROVINSI {prov}"] = prov

        logger.info(f"✅ Berhasil memuat {len(PROVINSI_MAPPING)} mapping provinsi dari {os.path.basename(excel_path)}")
    except Exception as e:
        logger.error(f"❌ Error memuat {excel_path}: {e}")

# Load provinsi mapping at startup
load_provinsi_mapping()



# ============== SATKER FUNCTIONS ==============

def extract_satker_siasn(unor_nama):
    """
    Ekstrak satker dari UNOR NAMA SIASN dengan prioritas:
    1. Sekretariat KPU/KIP Kabupaten/Kota (unit terkecil)
    2. Sekretariat KPU/KIP Provinsi
    3. Satker pusat (BIRO, PUSAT, INSPEKTORAT)
    4. Jika tidak ada pattern yang cocok, tampilkan UNOR NAMA asli
    """
    if not unor_nama or str(unor_nama).strip() == '' or str(unor_nama).lower() == 'nan':
        return ''
    
    unor_upper = str(unor_nama).strip().upper()
    
    # Priority 1: Kabupaten/Kota (smallest administrative unit)
    # Match "SEKRETARIAT KPU KABUPATEN X" or "SEKRETARIAT KIP KABUPATEN X" etc.
    pattern_kab = r'SEKRETARIAT\s+(?:KPU|KIP|KOMISI\s+PEMILIHAN\s+UMUM|KOMISI\s+INDEPENDEN\s+PEMILIHAN)\s+KABUPATEN\s+[A-Z][A-Z\s]+'
    pattern_kota = r'SEKRETARIAT\s+(?:KPU|KIP|KOMISI\s+PEMILIHAN\s+UMUM|KOMISI\s+INDEPENDEN\s+PEMILIHAN)\s+KOTA\s+[A-Z][A-Z\s]+'
    
    match_kab = re.search(pattern_kab, unor_upper)
    if match_kab:
        # Clean up - remove trailing parts after the kabupaten name
        satker = match_kab.group().strip()
        # Remove any trailing " - " and what comes after
        if ' - ' in satker:
            satker = satker.split(' - ')[0].strip()
        return satker
    
    match_kota = re.search(pattern_kota, unor_upper)
    if match_kota:
        satker = match_kota.group().strip()
        if ' - ' in satker:
            satker = satker.split(' - ')[0].strip()
        return satker
    
    # Priority 2: Provinsi
    pattern_prov = r'SEKRETARIAT\s+(?:KPU|KIP|KOMISI\s+PEMILIHAN\s+UMUM|KOMISI\s+INDEPENDEN\s+PEMILIHAN)\s+PROVINSI\s+[A-Z][A-Z\s]+'
    match_prov = re.search(pattern_prov, unor_upper)
    if match_prov:
        satker = match_prov.group().strip()
        if ' - ' in satker:
            satker = satker.split(' - ')[0].strip()
        return satker
    
    # Priority 3: Satker pusat
    for satker in SATKER_PUSAT:
        if satker in unor_upper:
            return satker
    
    # If no match found, return the original UNOR NAMA (so user can see the actual value)
    return str(unor_nama).strip()


def extract_satker_simpeg(unor, unor_induk):
    """
    Ekstrak satker dari SIMPEG:
    1. Jika Unor dimulai dengan BIRO/SEKRETARIAT/PUSAT/INSPEKTORAT UTAMA → itu satkernya
    2. Jika tidak, gunakan Unor Induk
    """
    unor_str = str(unor).strip() if unor and str(unor).lower() != 'nan' else ''
    unor_induk_str = str(unor_induk).strip() if unor_induk and str(unor_induk).lower() != 'nan' else ''
    
    if unor_str:
        unor_upper = unor_str.upper()
        for prefix in SATKER_PREFIXES:
            if unor_upper.startswith(prefix):
                return unor_str
    
    # If unor doesn't match satker pattern, use unor_induk
    return unor_induk_str


def normalize_satker_simpeg(satker):
    """
    Normalisasi satker SIMPEG yang memiliki format gabungan, misal:
    "SEKRETARIAT KPU KABUPATEN DONGGALA - SEKRETARIAT KPU PROVINSI SULAWESI TENGAH"

    Aturan prioritas (dari terkecil ke terbesar):
    1. Jika salah satu bagian mengandung KABUPATEN → ambil bagian yang mengandung KABUPATEN
    2. Jika salah satu bagian mengandung KOTA → ambil bagian yang mengandung KOTA
    3. Jika salah satu bagian mengandung PROVINSI dan bagian lain mengandung
       SEKRETARIAT JENDERAL / SETJEN / KOMISI PEMILIHAN UMUM (pusat) → ambil bagian PROVINSI
    4. Jika tidak ada pemisah " - ", kembalikan apa adanya
    """
    if not satker:
        return satker

    satker_str = str(satker).strip()

    # Cek apakah ada pemisah " - "
    if ' - ' not in satker_str:
        return satker_str

    parts = [p.strip() for p in satker_str.split(' - ')]
    parts_upper = [p.upper() for p in parts]

    # Aturan 1: Prioritas KABUPATEN
    kab_parts = [parts[i] for i, p in enumerate(parts_upper) if 'KABUPATEN' in p]
    if kab_parts:
        return kab_parts[0]

    # Aturan 2: Prioritas KOTA
    kota_parts = [parts[i] for i, p in enumerate(parts_upper) if 'KOTA' in p]
    if kota_parts:
        return kota_parts[0]

    # Aturan 3: Prioritas PROVINSI (jika ada SETJEN/PUSAT di bagian lain)
    PUSAT_KEYWORDS = ['SEKRETARIAT JENDERAL', 'SETJEN', 'JENDERAL KOMISI']
    provinsi_parts = [parts[i] for i, p in enumerate(parts_upper) if 'PROVINSI' in p]
    if provinsi_parts:
        has_pusat = any(
            any(kw in p for kw in PUSAT_KEYWORDS)
            for p in parts_upper
        )
        if has_pusat:
            return provinsi_parts[0]

    # Default: kembalikan bagian pertama (yang biasanya lebih spesifik)
    return parts[0]


def normalize_satker(satker):
    """
    Normalisasi nama satker untuk perbandingan:
    - Convert to uppercase
    - Normalize KPU ↔ Komisi Pemilihan Umum
    - Normalize KIP ↔ Komisi Independen Pemilihan
    - Fix missing space after KOTA/KABUPATEN (e.g., KOTALANGSA → KOTA LANGSA)
    - Remove extra whitespace
    """
    if not satker:
        return ''
    normalized = str(satker).strip().upper()
    # Remove special characters
    normalized = normalized.replace('\xa0', ' ').replace('Â', '')
    # Normalize KOMISI PEMILIHAN UMUM to KPU
    normalized = re.sub(r'KOMISI\s+PEMILIHAN\s+UMUM', 'KPU', normalized)
    # Normalize KOMISI INDEPENDEN PEMILIHAN to KIP
    normalized = re.sub(r'KOMISI\s+INDEPENDEN\s+PEMILIHAN', 'KIP', normalized)
    # Fix missing space after KOTA (e.g., KOTALANGSA → KOTA LANGSA)
    normalized = re.sub(r'KOTA([A-Z])', r'KOTA \1', normalized)
    # Fix missing space after KABUPATEN (e.g., KABUPATENBIREUEN → KABUPATEN BIREUEN)
    normalized = re.sub(r'KABUPATEN([A-Z])', r'KABUPATEN \1', normalized)
    # Normalize multiple spaces
    normalized = re.sub(r'\s+', ' ', normalized)
    return normalized.strip()


def satker_are_equal(satker1, satker2):
    """
    Check if two satker names are equivalent after normalization.
    Handles KPU ↔ Komisi Pemilihan Umum and KIP ↔ Komisi Independen Pemilihan
    """
    norm1 = normalize_satker(satker1)
    norm2 = normalize_satker(satker2)
    
    # Direct match after normalization
    return norm1 == norm2


def get_pusat_provinsi_category(satker):
    """
    Mengklasifikasikan satker menjadi 'PUSAT' atau 'PROVINSI [Nama Provinsi]'.
    """
    if not satker:
        return ''

    # Normalize satker to handle aliases like KOMISI PEMILIHAN UMUM -> KPU
    satker_upper = normalize_satker(satker)
    
    # Fix normalize_satker unintended behavior where KOTABARU becomes KOTA BARU
    satker_upper = satker_upper.replace("KOTA WARINGIN", "KOTAWARINGIN")
    satker_upper = satker_upper.replace("KOTA BARU", "KOTABARU")
    satker_upper = satker_upper.replace("KOTA MOBAGU", "KOTAMOBAGU")
    
    
    # Kriteria 1: PUSAT
    pusat_keywords = ['BIRO', 'PUSAT', 'INSPEKTORAT', 'SEKRETARIAT JENDERAL', 'SETJEN', 'JENDERAL KOMISI']
    if any(kw in satker_upper for kw in pusat_keywords) and 'PROVINSI' not in satker_upper and 'KABUPATEN' not in satker_upper and 'KOTA' not in satker_upper:
        return 'PUSAT'

    # Kriteria 2 & 3: KABUPATEN / KOTA / PROVINSI
    # Cari spesifik bagian kabupaten/kota/provinsi
    area_key = None
    
    # 2. Cek KABUPATEN
    # Handle specific Edge Cases that contain KOTA but are KABUPATEN or need special regex
    if "KABUPATEN KOTAWARINGIN" in satker_upper:
        match_kab = re.search(r'(KABUPATEN\s+KOTAWARINGIN\s+[A-Z\s]+)', satker_upper)
    elif "KABUPATEN KOTABARU" in satker_upper:
        match_kab = re.search(r'(KABUPATEN\s+KOTABARU)', satker_upper)
    else:    
        match_kab = re.search(r'(KABUPATEN\s+[A-Z\s]+)', satker_upper)
        
    if match_kab:
        area_key = match_kab.group(1).split(' - ')[0].strip()
        # Jika string mengandung KOTA tapi sebenarnya merupakan nama Kabupaten, pisahkan
        # Perkecualian: LIMA PULUH KOTA (Sumatera Barat) tidak boleh dipisahkan
        if "KOTA" in area_key and all(kw not in area_key for kw in ["KOTAWARINGIN", "KOTABARU", "LIMA PULUH KOTA"]):
             area_key = area_key.split('KOTA')[0].strip()
    
    # 3. Cek KOTA
    match_kota = None
    if not match_kab: # Only check for KOTA if no KABUPATEN was found
        if "KOTA KOTAMOBAGU" in satker_upper:
            match_kota = re.search(r'(KOTA\s+KOTAMOBAGU)', satker_upper)
        else:
            match_kota = re.search(r'(KOTA\s+[A-Z\s]+)', satker_upper)
            
        if match_kota:
            area_key = match_kota.group(1).split(' - ')[0].strip()
            # Hindari Kabupaten yang terpotong menjadi Kota
            if "KABUPATEN" in area_key:
                area_key = area_key.split("KABUPATEN")[0].strip()
    
    # 4. Cek PROVINSI
    match_prov = re.search(r'(PROVINSI\s+[A-Z\s]+)', satker_upper)
    if not area_key and match_prov: # Only check for PROVINSI if no KABUPATEN or KOTA was found
        area_key = match_prov.group(1).split(' - ')[0].strip()
    
    if area_key:
        if area_key in HARDCODED_PROVINSI_MAPPING:
            return HARDCODED_PROVINSI_MAPPING[area_key]
        elif area_key in PROVINSI_MAPPING:
            return PROVINSI_MAPPING[area_key]
        else:
            # Fallback jika tidak ditemukan di dictionary
            # Ekstrak kata setelah "Provinsi" jika ini adalah level provinsi
            if match_prov:
                return match_prov.group(1).replace('PROVINSI ', '').strip()
    
    # Fallback to Pusat if unsure but looks like it might be
    if any(kw in satker_upper for kw in ['BIRO', 'PUSAT', 'INSPEKTORAT']):
        return 'PUSAT'
        
    return ''


def read_excel_smart(file_path, file_label="Excel"):
    """
    Smart Excel reader that:
    - Auto-detects header row (tries row 0, then row 1)
    - Handles corrupted xlsx and HTML-as-xlsx files
    """
    logger.info(f"📖 Reading {file_label}: {os.path.basename(file_path)}")
    errors = []
    
    # Expected columns for SIMPEG
    expected_cols = ['NIP', '#', 'Nama', 'CPNS/PNS']
    
    # Try header=0 first, then header=1
    for header_row in [0, 1]:
        try:
            logger.debug(f"  Trying openpyxl engine with header={header_row}...")
            # Force NIP column to be read as string (handles text-formatted numbers in Excel)
            df = pd.read_excel(file_path, engine='openpyxl', header=header_row, dtype={'NIP': str})
            
            # Check if expected columns exist
            cols = [str(c) for c in df.columns]
            has_expected = any(exp in cols for exp in expected_cols)
            
            if has_expected:
                logger.info(f"  ✓ Success with openpyxl (header={header_row}): {len(df)} rows")
                logger.info(f"    ALL columns: {list(df.columns)}")
                return df
            else:
                logger.debug(f"    header={header_row} - expected columns not found, trying next...")
                
        except Exception as e:
            errors.append(f"openpyxl(header={header_row}): {e}")
            logger.warning(f"  ✗ openpyxl (header={header_row}) failed: {e}")
    
    # Method 2: Try calamine (fast, handles many formats including corrupted xlsx)
    for header_row in [0, 1]:
        try:
            logger.debug(f"  Trying calamine engine with header={header_row}...")
            df = pd.read_excel(file_path, engine='calamine', header=header_row, dtype={'NIP': str})
            
            # Check if expected columns exist
            cols = [str(c) for c in df.columns]
            has_expected = any(exp in cols for exp in expected_cols)
            
            if has_expected:
                logger.info(f"  ✓ Success with calamine (header={header_row}): {len(df)} rows, columns: {list(df.columns)[:5]}...")
                return df
            else:
                logger.debug(f"    header={header_row} - expected columns not found, trying next...")
                
        except Exception as e:
            errors.append(f"calamine(header={header_row}): {e}")
            logger.warning(f"  ✗ calamine (header={header_row}) failed: {e}")
    
    # Method 3: Try reading as HTML with different encodings
    for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
        try:
            logger.debug(f"  Trying read_html with {encoding} encoding...")
            with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                content = f.read()
            dfs = pd.read_html(content)
            if dfs and len(dfs) > 0:
                df = dfs[0]
                logger.info(f"  ✓ Success with read_html ({encoding}): {len(df)} rows, columns: {list(df.columns)[:5]}...")
                return df
        except Exception as e3:
            errors.append(f"read_html({encoding}): {e3}")
            logger.warning(f"  ✗ read_html ({encoding}) failed: {e3}")
    
    # Method 4: Try xlrd (older xls format)
    try:
        logger.debug(f"  Trying xlrd engine...")
        df = pd.read_excel(file_path, engine='xlrd')
        logger.info(f"  ✓ Success with xlrd: {len(df)} rows")
        return df
    except Exception as e4:
        errors.append(f"xlrd: {e4}")
        logger.warning(f"  ✗ xlrd failed: {e4}")
    
    # All methods failed
    error_msg = f"Could not read {file_label} ({os.path.basename(file_path)}). All methods failed."
    logger.error(f"  ❌ {error_msg}")
    logger.error(f"  Errors: {errors}")
    raise Exception(error_msg)


def read_csv_pipe_delimited(file_path, file_label="CSV"):
    """
    Read pipe-delimited CSV files (SIASN format)
    Handles SIASN quirks:
    - Lines ending with ';;'
    - Some lines wrapped in quotes
    """
    logger.info(f"📖 Reading {file_label}: {os.path.basename(file_path)}")
    try:
        # Read and preprocess the file
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Clean lines
        cleaned_lines = []
        for line in lines:
            # Remove trailing ;; and quotes
            line = line.rstrip('\r\n')
            if line.endswith(';;'):
                line = line[:-2]
            # Remove leading/trailing quotes
            if line.startswith('"') and line.endswith('"'):
                line = line[1:-1]
            elif line.startswith('"'):
                line = line[1:]
            cleaned_lines.append(line)
        
        # Parse as CSV
        from io import StringIO
        cleaned_content = '\n'.join(cleaned_lines)
        df = pd.read_csv(StringIO(cleaned_content), delimiter='|', dtype={'NIP BARU': str})
        
        logger.info(f"  ✓ Success: {len(df)} rows, columns: {list(df.columns)[:5]}...")
        return df
    except Exception as e:
        logger.error(f"  ❌ Failed to read CSV: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise Exception(f"Could not read {file_label} ({os.path.basename(file_path)}): {e}")


def normalize_nip_siasn(nip_value):
    """
    Normalize NIP from SIASN by keeping only digits.
    SIASN NIPs often have quote prefixes like '199012345678901234
    """
    if not nip_value:
        return ''
    nip = str(nip_value).strip()
    # Keep only digits
    nip = re.sub(r'[^0-9]', '', nip)
    return nip


def extract_fields(row, source):
    """Extract and normalize fields from a row based on source type"""
    col_map = COLUMN_MAP[source]
    
    # Get NIP
    raw_nip = row.get(col_map['nip'], '')
    
    # Only clean SIASN NIPs (remove non-digits)
    if source == 'siasn':
        cleaned_nip = normalize_nip_siasn(raw_nip)
    else:
        # SIMPEG - also normalize to digits only for consistent comparison
        cleaned_nip = re.sub(r'[^0-9]', '', str(raw_nip).strip())
    
    # Extract satker based on source
    if source == 'simpeg':
        unor = row.get(col_map['unor'], '')
        unor_induk = row.get(col_map['unor_induk'], '')
        satker = extract_satker_simpeg(unor, unor_induk)
        satker_normalized = normalize_satker_simpeg(satker)
        pusat_provinsi_kategori = get_pusat_provinsi_category(unor if str(unor).strip().upper().startswith(tuple(SATKER_PREFIXES)) else unor_induk)
        # Get jenis pegawai from SIMPEG
        jenis_pegawai = str(row.get(col_map['jenis_pegawai'], '')).strip()
    else:  # siasn
        unor_nama = row.get(col_map['unor_nama'], '')
        satker = extract_satker_siasn(unor_nama)
        satker_normalized = satker  # SIASN satker already extracted cleanly
        pusat_provinsi_kategori = '' 
        jenis_pegawai = ''  # SIASN doesn't have this column, will be filled from SIMPEG
    
    return {
        'nip': cleaned_nip,
        'nama': str(row.get(col_map['nama'], '')).strip(),
        'jenjang_pendidikan': str(row.get(col_map['jenjang_pendidikan'], '')).strip(),
        'nama_pendidikan': str(row.get(col_map['nama_pendidikan'], '')).strip(),
        'golru': str(row.get(col_map['golru'], '')).strip(),
        'nama_jabatan': str(row.get(col_map['nama_jabatan'], '')).strip(),
        'satker': satker,
        'satker_normalized': satker_normalized,
        'pusat_provinsi_kategori': pusat_provinsi_kategori,
        'jenis_pegawai': jenis_pegawai
    }


def merge_datasets(df1, df2, source, label1="File1", label2="File2"):
    """Merge two dataframes (PNS + PPPK) into a single dict keyed by NIP"""
    logger.info(f"🔗 Merging {source.upper()} data ({label1} + {label2})")
    merged = {}
    sample_nips = []
    sample_raw_nips = []
    
    col_map = COLUMN_MAP[source]
    nip_col = col_map['nip']
    
    for df, label in [(df1, label1), (df2, label2)]:
        # Log first 3 rows of NIP column for debugging
        if nip_col in df.columns:
            first_nips = df[nip_col].head(3).tolist()
            logger.info(f"  📋 {label} - First 3 raw NIPs from column '{nip_col}': {first_nips}")
        else:
            logger.error(f"  ❌ {label} - Column '{nip_col}' NOT FOUND! Available: {list(df.columns)}")
            continue
        
        count = 0
        for _, row in df.iterrows():
            fields = extract_fields(row, source)
            if fields['nip'] and fields['nip'] != 'nan':
                merged[fields['nip']] = fields
                count += 1
                # Collect first 3 sample NIPs for debugging
                if len(sample_nips) < 3:
                    raw_nip = row.get(nip_col, '')
                    sample_raw_nips.append(str(raw_nip))
                    sample_nips.append(fields['nip'])
        logger.debug(f"  {label}: {count} valid NIPs extracted")
    
    # Log sample NIPs for debugging
    if sample_nips:
        logger.info(f"  Sample RAW NIPs ({source}): {sample_raw_nips}")
        logger.info(f"  Sample CLEANED NIPs ({source}): {sample_nips}")
    
    logger.info(f"  ✓ Total merged: {len(merged)} unique NIPs")
    return merged


def compare_datasets(simpeg_data, siasn_data):
    """Compare SIMPEG and SIASN datasets, return list of discrepancies"""
    logger.info(f"🔍 Comparing datasets...")
    discrepancies = []
    field_counts = {field: 0 for field in COMPARE_FIELDS}
    
    simpeg_nips = set(simpeg_data.keys())
    siasn_nips = set(siasn_data.keys())
    common_nips = simpeg_nips & siasn_nips
    only_in_simpeg = simpeg_nips - siasn_nips
    only_in_siasn = siasn_nips - simpeg_nips
    
    logger.info(f"  Found {len(common_nips)} common NIPs")
    logger.info(f"  Found {len(only_in_simpeg)} NIPs only in SIMPEG")
    logger.info(f"  Found {len(only_in_siasn)} NIPs only in SIASN")
    
    split_discrepancies = []
    
    for nip in common_nips:
        simpeg_row = simpeg_data[nip]
        siasn_row = siasn_data[nip]
        diff_cols = []
        
        for field in COMPARE_FIELDS:
            siasn_val = siasn_row[field] if siasn_row[field] else ''
            
            # Use intelligent matching for nama_jabatan
            if field == 'nama_jabatan':
                simpeg_val = simpeg_row[field] if simpeg_row[field] else ''
                if not job_titles_are_equal(simpeg_val, siasn_val):
                    diff_cols.append(field)
                    field_counts[field] += 1
            # Use intelligent matching for satker: compare normalized SIMPEG satker with SIASN satker
            elif field == 'satker':
                simpeg_val = simpeg_row.get('satker_normalized', simpeg_row.get('satker', ''))
                if not satker_are_equal(simpeg_val, siasn_val):
                    diff_cols.append(field)
                    field_counts[field] += 1
            else:
                simpeg_val = simpeg_row[field] if simpeg_row[field] else ''
                # Standard comparison (case-insensitive)
                if simpeg_val.lower() != siasn_val.lower():
                    diff_cols.append(field)
                    field_counts[field] += 1
        
        if diff_cols:
            # Add to split_discrepancies: one entry per column difference
            for col in diff_cols:
                split_discrepancies.append({
                    'nip': nip,
                    'nama': simpeg_row['nama'] or siasn_row['nama'],
                    'diff_cols': [col], # Single column for this row
                    'all_diff_cols': diff_cols, # All columns for this NIP (useful for UI)
                    'simpeg': simpeg_row,
                    'siasn': siasn_row
                })
    
    # Prepare NIP difference lists
    only_simpeg_list = [
        {'nip': nip, 'nama': simpeg_data[nip]['nama']}
        for nip in sorted(only_in_simpeg)
    ]
    only_siasn_list = [
        {'nip': nip, 'nama': siasn_data[nip]['nama']}
        for nip in sorted(only_in_siasn)
    ]
    
    split_discrepancies.sort(key=lambda x: x['nip'])
    logger.info(f"  ✓ Found {len(split_discrepancies)} split discrepancies from {len(set(d['nip'] for d in split_discrepancies))} unique NIPs")
    logger.info(f"  Field counts: {field_counts}")
    
    return split_discrepancies, len(common_nips), only_simpeg_list, only_siasn_list, field_counts


@app.route('/')
def index():
    return render_template('upload.html')


@app.route('/upload', methods=['POST'])
def upload_files():
    logger.info("=" * 50)
    logger.info("📤 New upload request received")
    
    try:
        simpeg_pns = request.files.get('simpeg_pns')
        simpeg_pppk = request.files.get('simpeg_pppk')
        siasn_pns = request.files.get('siasn_pns')
        siasn_pppk = request.files.get('siasn_pppk')
        
        # Log uploaded files
        logger.info(f"  SIMPEG PNS: {simpeg_pns.filename if simpeg_pns else 'None'}")
        logger.info(f"  SIMPEG PPPK: {simpeg_pppk.filename if simpeg_pppk else 'None'}")
        logger.info(f"  SIASN PNS: {siasn_pns.filename if siasn_pns else 'None'}")
        logger.info(f"  SIASN PPPK: {siasn_pppk.filename if siasn_pppk else 'None'}")
        
        if not all([simpeg_pns, simpeg_pppk, siasn_pns, siasn_pppk]):
            logger.error("Missing files!")
            return jsonify({'error': 'Semua 4 file harus diupload'}), 400
        
        with tempfile.TemporaryDirectory() as tmpdir:
            logger.info(f"📁 Temp directory: {tmpdir}")
            
            # Save files
            simpeg_pns_path = os.path.join(tmpdir, secure_filename(simpeg_pns.filename))
            simpeg_pppk_path = os.path.join(tmpdir, secure_filename(simpeg_pppk.filename))
            siasn_pns_path = os.path.join(tmpdir, secure_filename(siasn_pns.filename))
            siasn_pppk_path = os.path.join(tmpdir, secure_filename(siasn_pppk.filename))
            
            simpeg_pns.save(simpeg_pns_path)
            simpeg_pppk.save(simpeg_pppk_path)
            siasn_pns.save(siasn_pns_path)
            siasn_pppk.save(siasn_pppk_path)
            logger.info("✓ All files saved to temp directory")
            
            # Read files with detailed logging
            logger.info("-" * 40)
            df_simpeg_pns = read_excel_smart(simpeg_pns_path, "SIMPEG PNS")
            df_simpeg_pppk = read_excel_smart(simpeg_pppk_path, "SIMPEG PPPK")
            df_siasn_pns = read_csv_pipe_delimited(siasn_pns_path, "SIASN PNS")
            df_siasn_pppk = read_csv_pipe_delimited(siasn_pppk_path, "SIASN PPPK")
            
            # Merge and compare
            logger.info("-" * 40)
            simpeg_merged = merge_datasets(df_simpeg_pns, df_simpeg_pppk, 'simpeg', "PNS", "PPPK")
            siasn_merged = merge_datasets(df_siasn_pns, df_siasn_pppk, 'siasn', "PNS", "PPPK")
            
            logger.info("-" * 40)
            discrepancies, total_common, only_simpeg, only_siasn, field_counts = compare_datasets(simpeg_merged, siasn_merged)
            
            # Store in server-side storage (not session - cookies have size limits)
            DATA_STORE['discrepancies'] = discrepancies
            # Create a dict of ALL discrepancies for each NIP for the Detail view
            nip_to_full_discrepancy = {}
            for d in discrepancies:
                nip = d['nip']
                if nip not in nip_to_full_discrepancy:
                    nip_to_full_discrepancy[nip] = {
                        'nip': nip,
                        'nama': d['nama'],
                        'diff_cols': d.get('all_diff_cols', d['diff_cols']),
                        'simpeg': d['simpeg'],
                        'siasn': d['siasn']
                    }
            
            DATA_STORE['discrepancies_dict'] = nip_to_full_discrepancy
            DATA_STORE['only_in_simpeg'] = only_simpeg
            DATA_STORE['only_in_siasn'] = only_siasn
            DATA_STORE['field_counts'] = field_counts
            DATA_STORE['stats'] = {
                'simpeg_count': len(simpeg_merged),
                'siasn_count': len(siasn_merged),
                'common_count': total_common,
                'discrepancy_count': len(nip_to_full_discrepancy), # Unique NIP count
                'only_simpeg_count': len(only_simpeg),
                'only_siasn_count': len(only_siasn),
                'field_counts': field_counts
            }
            
            logger.info("=" * 50)
            logger.info(f"✅ Processing complete!")
            logger.info(f"   SIMPEG: {len(simpeg_merged)} NIPs")
            logger.info(f"   SIASN: {len(siasn_merged)} NIPs")
            logger.info(f"   Common: {total_common} NIPs")
            logger.info(f"   Discrepancies: {len(discrepancies)}")
            logger.info("=" * 50)
        
        return jsonify({'success': True, 'stats': DATA_STORE['stats'], 'redirect': '/results'})
    
    except Exception as e:
        logger.error("=" * 50)
        logger.error(f"❌ ERROR: {str(e)}")
        logger.error(traceback.format_exc())
        logger.error("=" * 50)
        return jsonify({'error': str(e)}), 500


@app.route('/results')
def results():
    discrepancies = DATA_STORE['discrepancies']
    stats = DATA_STORE['stats']
    return render_template('results.html',
                           discrepancies=discrepancies,
                           stats=stats,
                           field_labels=FIELD_LABELS,
                           only_in_simpeg=DATA_STORE.get('only_in_simpeg', []),
                           only_in_siasn=DATA_STORE.get('only_in_siasn', []),
                           field_counts=DATA_STORE.get('field_counts', {}))


@app.route('/detail/<nip>')
def detail(nip):
    # Use indexed dict for fast lookup
    item = DATA_STORE['discrepancies_dict'].get(nip)
    if not item:
        return "NIP not found", 404
    return render_template('detail.html', item=item, field_labels=FIELD_LABELS, compare_fields=COMPARE_FIELDS)


# API Endpoints for testing without UI
@app.route('/api/stats')
def api_stats():
    """Get current stats"""
    return jsonify(DATA_STORE['stats'])


@app.route('/api/discrepancies')
def api_discrepancies():
    """Get list of discrepancies (paginated)"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    discrepancies = DATA_STORE['discrepancies']
    start = (page - 1) * per_page
    end = start + per_page
    
    return jsonify({
        'total': len(discrepancies),
        'page': page,
        'per_page': per_page,
        'data': discrepancies[start:end]
    })


@app.route('/api/detail/<nip>')
def api_detail(nip):
    """Get detail for specific NIP"""
    item = DATA_STORE['discrepancies_dict'].get(nip)
    if not item:
        return jsonify({'error': 'NIP not found'}), 404
    return jsonify(item)


@app.route('/api/test/load')
def api_test_load():
    """Load test dataset directly for testing (no file upload needed)"""
    global DATA_STORE
    try:
        test_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dataset', 'test_dataset')
        
        logger.info(f"🧪 Loading test dataset from: {test_dir}")
        
        # Find files
        simpeg_pns = None
        simpeg_pppk = None
        siasn_pns = None
        siasn_pppk = None
        
        for f in os.listdir(test_dir):
            if f.startswith('DaftarPegawai') and 'PNS' in f and f.endswith('.xlsx'):
                simpeg_pns = os.path.join(test_dir, f)
            elif f.startswith('DaftarPegawai') and 'PPPK' in f and f.endswith('.xlsx'):
                simpeg_pppk = os.path.join(test_dir, f)
            elif f.startswith('pns_') and f.endswith('.csv'):
                siasn_pns = os.path.join(test_dir, f)
            elif f.startswith('pppk_') and f.endswith('.csv'):
                siasn_pppk = os.path.join(test_dir, f)
        
        if not all([simpeg_pns, simpeg_pppk, siasn_pns, siasn_pppk]):
            return jsonify({'error': 'Missing test files'}), 400
        
        # Read files
        df_simpeg_pns = read_excel_smart(simpeg_pns, "SIMPEG PNS")
        df_simpeg_pppk = read_excel_smart(simpeg_pppk, "SIMPEG PPPK")
        df_siasn_pns = read_csv_pipe_delimited(siasn_pns, "SIASN PNS")
        df_siasn_pppk = read_csv_pipe_delimited(siasn_pppk, "SIASN PPPK")
        
        # Merge and compare
        simpeg_merged = merge_datasets(df_simpeg_pns, df_simpeg_pppk, 'simpeg', "PNS", "PPPK")
        siasn_merged = merge_datasets(df_siasn_pns, df_siasn_pppk, 'siasn', "PNS", "PPPK")
        discrepancies, total_common, only_simpeg, only_siasn, field_counts = compare_datasets(simpeg_merged, siasn_merged)
        
        # Store
        DATA_STORE['discrepancies'] = discrepancies
        
        # Create a dict of ALL discrepancies for each NIP for the Detail view
        nip_to_full_discrepancy = {}
        for d in discrepancies:
            nip = d['nip']
            if nip not in nip_to_full_discrepancy:
                nip_to_full_discrepancy[nip] = {
                    'nip': nip,
                    'nama': d['nama'],
                    'diff_cols': d.get('all_diff_cols', d['diff_cols']),
                    'simpeg': d['simpeg'],
                    'siasn': d['siasn']
                }
        
        DATA_STORE['discrepancies_dict'] = nip_to_full_discrepancy
        DATA_STORE['only_in_simpeg'] = only_simpeg
        DATA_STORE['only_in_siasn'] = only_siasn
        DATA_STORE['field_counts'] = field_counts
        DATA_STORE['stats'] = {
            'simpeg_count': len(simpeg_merged),
            'siasn_count': len(siasn_merged),
            'common_count': total_common,
            'discrepancy_count': len(nip_to_full_discrepancy), # Unique NIP count
            'only_simpeg_count': len(only_simpeg),
            'only_siasn_count': len(only_siasn),
            'field_counts': field_counts
        }
        
        logger.info(f"✅ Test data loaded: {len(discrepancies)} discrepancies")
        return jsonify({'success': True, 'stats': DATA_STORE['stats']})
        
    except Exception as e:
        logger.error(f"❌ Error loading test data: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/export')
def api_export():
    """Export discrepancies as CSV or Excel with optional column filter"""
    format_type = request.args.get('format', 'csv').lower()
    column_filter = request.args.get('column', '')
    
    discrepancies = DATA_STORE['discrepancies']
    
    if not discrepancies:
        return jsonify({'error': 'No data to export'}), 400
    
    # Filter by column if specified
    if column_filter:
        discrepancies = [d for d in discrepancies if column_filter in d['diff_cols']]
    
    # Prepare data for export
    export_data = []
    for d in discrepancies:
        row = {
            'NIP': d['nip'],
            'Nama': d['nama'],
            'Jenis Pegawai': d['simpeg'].get('jenis_pegawai', ''),
            'PUSAT/PROVINSI': d['simpeg'].get('pusat_provinsi_kategori', ''),
            'Satuan Kerja SIMPEG': d['simpeg'].get('satker_normalized') or d['simpeg'].get('satker', ''),
            'Kolom Tidak Konsisten': ', '.join([FIELD_LABELS.get(c, c) for c in d['diff_cols']]),
            'SIMPEG - Jenjang Pendidikan': d['simpeg'].get('jenjang_pendidikan', ''),
            'SIASN - Jenjang Pendidikan': d['siasn'].get('jenjang_pendidikan', ''),
            'SIMPEG - Golru': d['simpeg'].get('golru', ''),
            'SIASN - Golru': d['siasn'].get('golru', ''),
            'SIMPEG - Nama Jabatan': d['simpeg'].get('nama_jabatan', ''),
            'SIASN - Nama Jabatan': d['siasn'].get('nama_jabatan', ''),
            'SIMPEG - Satuan Kerja': d['simpeg'].get('satker', ''),
            'SIASN - Satuan Kerja': d['siasn'].get('satker', ''),
        }
        export_data.append(row)
    
    df = pd.DataFrame(export_data)
    
    if format_type == 'excel':
        # Excel export
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Inkonsistensi')
        output.seek(0)
        
        filename = f'inkonsistensi_data_pegawai{"_" + column_filter if column_filter else ""}.xlsx'
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
    else:
        # CSV export
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        
        filename = f'inkonsistensi_data_pegawai{"_" + column_filter if column_filter else ""}.csv'
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )


@app.route('/api/export_nip_differences')
def api_export_nip_differences():
    """Export NIP differences (only in SIMPEG or only in SIASN) as Excel"""
    only_in_simpeg = DATA_STORE.get('only_in_simpeg', [])
    only_in_siasn = DATA_STORE.get('only_in_siasn', [])
    
    if not only_in_simpeg and not only_in_siasn:
        return jsonify({'error': 'No NIP difference data to export'}), 400
    
    # Create Excel with two sheets
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Sheet 1: NIPs only in SIMPEG
        df_simpeg = pd.DataFrame(only_in_simpeg)
        if not df_simpeg.empty:
            df_simpeg.columns = ['NIP', 'Nama']
        df_simpeg.to_excel(writer, index=False, sheet_name='Hanya di SIMPEG')
        
        # Sheet 2: NIPs only in SIASN
        df_siasn = pd.DataFrame(only_in_siasn)
        if not df_siasn.empty:
            df_siasn.columns = ['NIP', 'Nama']
        df_siasn.to_excel(writer, index=False, sheet_name='Hanya di SIASN')
    
    output.seek(0)
    
    filename = 'perbedaan_nip_simpeg_siasn.xlsx'
    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


if __name__ == '__main__':
    logger.info("🚀 Starting NIP Data Checker...")
    app.run(debug=True, port=5000)
