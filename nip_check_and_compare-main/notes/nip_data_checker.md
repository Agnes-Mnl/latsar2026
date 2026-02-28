---
created: 2026-01-10 15:47
tags:
  - quick-notes
topic: "Use case 3 untuk membantu latsar sang pacar"
review_needed: true
urgency: High
---
## 🧨 Problem / Context
*Apa masalah intinya? Kenapa note ini dibuat?*
- Ada banyak NIP, yang masing-masing dari mereka punya data yang tidak konsisten. Tujuannya ingin dibangun sebuah sistem yang mampu melakukan komparasi antara data SIMPEG dengan SIASN untuk melihat siapa/NIP mana beserta data yang tidak konsisten.

## 🗺️ Plan / Strategy
*Langkah taktis untuk menyelesaikannya:*
1. Membuat script Python untuk program website
2. Gabungkan terlebih dahulu file PNS dengan PPPK dari masing-masing sumber (SIMPEG dan SIASN)
3. Hasilnya digabungkan antara SIMPEG dengan SIASN
	1. Minta AI untuk membuat website agar hasilnya bisa seperti pengecekkan dari website [Diffchecker](https://www.diffchecker.com/)

## 🎯 Expected Output / Success Criteria
*Done apabila:*
- [ ] Data yang diintegrasikan konsisten
- [ ] Website dapat diakses dan digunakan dengan mudah

---
File ada di folder dataset, penjelasan metadata file nya adalah sebagai berikut:
1. File yang memiliki prefix **DaftarPegawai_Pegawai** atau dengan format **xlsx** adalah *SIMPEG*.
2. File yang memiliki **hashing pada nama file** nya atau dengan format **csv** adalah *SIASN*

Ada beberapa kategori yang harus dicocokkan:
- Satker,
- Jenjang pendidikan,
- Nama pendidikan,
- Golru (golongan ruang),
- Nama Jabatan

Berikut cara treatment kolomnya:
1. Satker
	Notes: Kolom satker ini agak sulit treatment nya, bisa kita skip dulu.
2. Jenjang pendidikan
	Data SIMPEG: Jenjang Pendidikan
	Data SIASN: TINGKAT PENDIDIKAN NAMA
3. Nama Pendidikan
	Data SIMPEG: Nama Pendidikan
	Data SIASN: PENDIDIKAN NAMA
4. Golru
	Data SIMPEG: Golru
	Data SIASN: GOL AKHIR NAMA
5. Nama Jabatan
	Data SIMPEG: Nama Jabatan
	Data SIASN: JABATAN NAMA

Dari sini, data perlu digabung untuk yang *SIMPEG* dengan *SIMPEG*
> **DaftarPegawai_Pegawai PNS** dengan **DaftarPegawai_Pegawai PPPK**

Dan juga *SIASN* dengan *SIASN*
> **pppk_** dengan **pns_**

Kolom yang digunakan untuk join per orang adalah dengan menggunakan NIP di SIMPEG dan NIP BARU di SIASN.

Gabung saja dengan append only, dan simpan output nya sebagai temp_simpeg dan temp_siasn, selanjutnya ambil 4 kolom dengan mapping yang saya sebutkan di atas.

Nah kemudian anda dapat menggunakan file code reference.html untuk hasil checker nya. Tapi berikan 1 halaman awalnya untuk upload 2 data SIMPEG dan 2 data SIASN, selanjutnya masuk ke halaman website referensi itu.