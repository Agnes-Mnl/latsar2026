# NIP Data Checker

Aplikasi web untuk membandingkan data pegawai antara **SIMPEG** (Sistem Informasi Kepegawaian Lokal) dan **SIASN** (Sistem Informasi ASN Nasional).

## 📋 Fitur Utama

### Perbandingan Data
- **Upload file** Excel (SIMPEG) dan CSV (SIASN)
- **Perbandingan otomatis** data PNS dan PPPK
- **Deteksi perbedaan** pada field:
  - Golru (Golongan Ruang)
  - Jenjang Pendidikan
  - Nama Jabatan

### Dashboard
- Jumlah pegawai SIMPEG
- Jumlah pegawai SIASN
- Perbandingan jumlah NIP antara kedua sistem
- NIP yang hanya ada di SIMPEG (tidak ada di SIASN)
- NIP yang hanya ada di SIASN (tidak ada di SIMPEG)

### Pencocokan Nama Jabatan Cerdas
Sistem mengenali variasi penulisan yang sama artinya:
- **SUB BAGIAN** = **SUBBAGIAN**
- **KPU** = **Komisi Pemilihan Umum**
- **KIP** = **Komisi Independen Pemilihan**
- **Assessor** = **Asessor**
- **AHLI PERTAMA - PENATA KELOLA PEMILU** = **Penata Kelola Pemilihan Umum Ahli Pertama**
- **Arsiparis Terampil** = **TERAMPIL - ARSIPARIS**
- Dan 1000+ equivalensi jabatan lainnya dari file `DatayangSama.xlsx`

### Fitur Lainnya
- **Filter** berdasarkan jenis perbedaan
- **Export** ke CSV atau Excel
- **Pagination** (50 data per halaman)
- Tampilan jumlah perbedaan per jenis saat filter aktif

---

## 🛠️ Teknologi

- **Backend**: Flask (Python)
- **Frontend**: HTML, TailwindCSS
- **Data Processing**: Pandas, OpenPyXL, Calamine

---

## 🚀 Cara Menjalankan

### Windows (dengan Virtual Environment)

```powershell
# Masuk ke folder code
cd code

# Buat virtual environment
python -m venv .venv

# Aktifkan virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Jalankan aplikasi
python app.py
```

### Linux / macOS

```bash
cd code
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

### Menggunakan UV

```bash
cd code
uv sync
uv run python app.py
```

---

## 🌐 Akses Aplikasi

Setelah menjalankan aplikasi, buka browser:

```
http://localhost:5000
```

---

## 📁 Struktur Folder

```
├── app.py              # Flask application
├── requirements.txt    # Python dependencies
├── pyproject.toml      # Project configuration
├── templates/
│   ├── upload.html     # Halaman upload file
│   ├── results.html    # Halaman hasil perbandingan
│   ├── detail.html     # Halaman detail per NIP
│   └── index.html      # Halaman utama
└── ../DatayangSama.xlsx  # Database equivalensi nama jabatan
```

---

## 📝 Format File yang Didukung

| Sumber | Jenis Pegawai | Format | Nama File |
|--------|---------------|--------|-----------|
| SIMPEG | PNS | Excel (.xlsx, .xls) | DaftarPegawai_Pegawai PNS |
| SIMPEG | PPPK | Excel (.xlsx, .xls) | DaftarPegawai_Pegawai PPPK |
| SIASN | PNS | CSV (pipe-delimited) | pns_*.csv |
| SIASN | PPPK | CSV (pipe-delimited) | pppk_*.csv |

---

## 🔧 API Endpoints

| Endpoint | Deskripsi |
|----------|-----------|
| `GET /api/stats` | Statistik perbandingan |
| `GET /api/discrepancies?page=1&per_page=50` | Daftar perbedaan (pagination) |
| `GET /api/detail/<nip>` | Detail per NIP |
| `GET /api/export?format=csv&column=` | Export data |

---

## ⚠️ Troubleshooting

### Error: ModuleNotFoundError
```bash
pip install -r requirements.txt
```

### Error: Port 5000 already in use
Ubah port di `app.py`:
```python
app.run(debug=True, port=5001)
```

---

## 📄 Lisensi

MIT License
