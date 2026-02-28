# NIP Data Checker

Aplikasi web untuk membandingkan data pegawai antara **SIMPEG** (Sistem Informasi Kepegawaian Lokal) dan **SIASN** (Sistem Informasi ASN Nasional).

## 📋 Fitur

- Upload file Excel (SIMPEG) dan CSV (SIASN)
- Perbandingan otomatis data PNS dan PPPK
- Deteksi perbedaan pada field: Jenjang Pendidikan, Nama Pendidikan, Golru, dan Nama Jabatan
- Tampilan hasil yang interaktif dan mudah dibaca

## 🛠️ Teknologi

- **Backend**: Flask (Python)
- **Frontend**: HTML, TailwindCSS
- **Data Processing**: Pandas, OpenPyXL, Calamine

---

## 🚀 Cara Menjalankan

### Windows

#### Dengan Virtual Environment (Recommended)

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

#### Tanpa Virtual Environment

```powershell
# Masuk ke folder code
cd code

# Install dependencies secara global
pip install -r requirements.txt

# Jalankan aplikasi
python app.py
```

---

### Linux / macOS

#### Dengan Virtual Environment (Recommended)

```bash
# Masuk ke folder code
cd code

# Buat virtual environment
python3 -m venv .venv

# Aktifkan virtual environment
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Jalankan aplikasi
python app.py
```

#### Tanpa Virtual Environment

```bash
# Masuk ke folder code
cd code

# Install dependencies secara global
pip3 install -r requirements.txt

# Jalankan aplikasi
python3 app.py
```

---

### Menggunakan UV (Package Manager Modern)

Jika Anda menggunakan [uv](https://github.com/astral-sh/uv):

```bash
# Masuk ke folder code
cd code

# Sync dependencies dari pyproject.toml
uv sync

# Jalankan aplikasi
uv run python app.py
```

---

## 🌐 Akses Aplikasi

Setelah menjalankan aplikasi, buka browser dan akses:

```
http://localhost:5000
```

## 📁 Struktur Folder

```
├── code/
│   ├── app.py              # Flask application
│   ├── requirements.txt    # Python dependencies
│   ├── pyproject.toml      # Project configuration (uv)
│   ├── uv.lock             # Lock file (uv)
│   └── templates/
│       ├── upload.html     # Halaman upload file
│       ├── results.html    # Halaman hasil perbandingan
│       └── index.html      # Halaman utama
├── dataset/                # Data sample (opsional)
└── README.md               # Dokumentasi ini
```

## 📝 Format File yang Didukung

| Sumber | Jenis Pegawai | Format | Nama File |
|--------|---------------|--------|-----------|
| SIMPEG | PNS | Excel (.xlsx, .xls) | DaftarPegawai_Pegawai PNS |
| SIMPEG | PPPK | Excel (.xlsx, .xls) | DaftarPegawai_Pegawai PPPK |
| SIASN | PNS | CSV (pipe-delimited) | pns_*.csv |
| SIASN | PPPK | CSV (pipe-delimited) | pppk_*.csv |

## ⚠️ Troubleshooting

### Error: ModuleNotFoundError
Pastikan semua dependencies terinstall:
```bash
pip install -r requirements.txt
```

### Error: Port 5000 already in use
Hentikan aplikasi lain yang menggunakan port 5000, atau ubah port di `app.py`:
```python
app.run(debug=True, port=5001)  # Ganti ke port lain
```

---

## 📄 Lisensi

MIT License
