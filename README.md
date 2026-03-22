**TUTORIAL PENGGUNAAN MINI SISTEM & DASHBOARD MONITORING**

**💻A. MINI SISTEM**

I. Instalasi Mini Sistem di PC/Komputer

Berikut langkah-langkah instalasi Mini Sistem
**1. Unduh Source Code**
- Download folder Mini Sistem dalam format .zip melalui Github : _https://github.com/Agnes-Mnl/latsar2026_ 
<img width="1895" height="877" alt="image" src="https://github.com/user-attachments/assets/67ce1804-d5e5-422c-8d88-0317f34a6083" />

**2. Install Visual Studio Code**
- Unduh dan install melalui : https://code.visualstudio.com/download
  
**3. Install python** 
- Pastikan Python sudah terpasang di komputer melalui : _https://www.python.org/downloads/_

**4. Menjalankan Mini Sistem**
- Buka folder Mini Sistem menggunakan Visual Studio Code
- Masuk ke terminal, lalu jalankan perintah berikut secara berurutan : 
   cd code
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
  
**5. Akses Mini Sistem**
- Setelah berhasil dijalankan, akan muncul link berikut : http://127.0.0.1:5000
- Buka link tersebut di browser (hanya dapat diakses secara lokal)
- Berikut tampilan mini sistem yang dapat digunakan
   <img width="1908" height="918" alt="image" src="https://github.com/user-attachments/assets/f59720e7-bf99-471b-b93d-1b24935f64c0" />

**6. Penggunaan Bersama**
- Mini Sistem juga dapat digunakan bersama dalam satu jaringan yang sama. Operator yang melakukan instalasi mini sistem dapat membagikan link lokal berikut : http://127.0.0.1:5000 kepada pengguna yang ingin menggunakan mini sistem.
- Pengguna lain tidak perlu instalasi dan hanya perlu mengakses link http://127.0.0.1:5000 saja

**7. Input Data**
- Upload data dengan cara :
   a. Upload file excel untuk data SIMPEG dan Upload file CSV untuk data SIASN
  <img width="1903" height="921" alt="image" src="https://github.com/user-attachments/assets/fb27882a-364d-44bc-9c47-b521972f37fa" />

  **8. Hasil Output**
  - Sistem akan menampilkan hasil perbandingan data
  - Hasil tersebut juga dapat diunduh dalam bentuk file excel
    <img width="1883" height="935" alt="image" src="https://github.com/user-attachments/assets/85e32423-1ef9-4086-9e00-fd44b65d5c7c" />


**💻B. DASHBOARD MONITORING**
Dashboard monitoring akan dikelola oleh Sub Bagian Pengelolaan Data dan dapat diakses oleh Operator di Satuan Kerja.

**Pegawai di Sub Bagian Pengelolaan Data Pegawai**

**1. Buka File Hasil**
- Gunakan file Excel hasil unduhan dari Mini Sistem
<img width="1911" height="435" alt="image" src="https://github.com/user-attachments/assets/07378896-d594-4c55-89b2-ac9a79a5aa42" />

**2. Input ke Dashboard**
- Copy seluruh isi data dari file tersebut
- Paste ke Sheet "Data" pada Dashboard Monitoring
<img width="1915" height="827" alt="image" src="https://github.com/user-attachments/assets/637920fd-ba42-457e-bf35-92436b0edfcb" />

**3. Lihat Hasil Rekap**
- Dashboard akan otomatis ter-update pada sheet "REKAPDATA"
<img width="1902" height="780" alt="image" src="https://github.com/user-attachments/assets/2f425f0d-0fb5-4512-ba88-e9fcb03adfc5" />

- Tidak perlu input manual tambahan 

**Operator SIMPEG dan SIASN**

1. Akses Dashboard Online
- Buka Link Berikut : https://docs.google.com/spreadsheets/d/1ykaF5QE5HAhVb7GVTYdBmCZa3rghxwDgBCfpR6KL66Q/edit?usp=sharing

2. Analisis Data
- Operator dapat elihat perbedaan data antara SIMPEG dan SIASN

3. fIlter berdasarkan Provinsi
- Pilih Provinsi sesuai satuan kerja masing-masing
- Data akan otomatis menyesaikan 
<img width="572" height="116" alt="image" src="https://github.com/user-attachments/assets/2115d121-fab0-4509-82c0-a0b9602fe14c" />
   
Mini Sistem dan Dashboard Monitoring ini dirancang untuk mempermudah proses identifikasi dan pemantauan perbedaan data kepegawaian antara SIMPEG dan SIASN secara lebih cepat, terstruktur, dan terintegrasi 🚀✨



