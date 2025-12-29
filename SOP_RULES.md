# CUSTOMER SUPPORT SOP – PLAIN TEXT SPECIFICATION

## GLOBAL RULE (BERLAKU UNTUK SEMUA SOP)

1. Sistem WAJIB memulai dengan verifikasi nasabah.
2. Verifikasi dilakukan menggunakan:

   * email terdaftar
   * nomor telepon terdaftar
3. Jika verifikasi GAGAL → proses DIHENTIKAN.
4. Jika verifikasi BERHASIL → proses DILANJUTKAN.
5. Setiap SOP WAJIB membuat tiket.
6. Semua status dan keputusan bisnis berbasis data sistem, bukan asumsi.
7. Eskalasi dilakukan hanya jika memenuhi kondisi yang didefinisikan.

---

## SOP 1 – TRANSFER GAGAL

### Kapan SOP ini digunakan

Gunakan SOP ini jika:

* dana terdebit
* penerima tidak menerima dana
* atau transfer antar bank gagal

### Data yang WAJIB dikumpulkan

* tanggal dan waktu transaksi
* nominal transaksi
* nama bank tujuan
* nomor rekening tujuan
* reference ID / trace ID / channel ID

### Data tambahan (opsional)

* screenshot bukti transfer

### Alur logika

1. Verifikasi nasabah.
2. Jika gagal → STOP.
3. Jika berhasil → kumpulkan data transaksi.
4. Jika data belum lengkap → STOP dan minta data.
5. Buat tiket.
6. Cek status transaksi di database.

### Keputusan berdasarkan status

* Jika status = FAILED:

  * lakukan refund otomatis
  * informasikan estimasi 1–3 hari kerja
  * tutup tiket setelah refund diterima

* Jika status = PENDING:

  * informasikan transaksi sedang diproses
  * cek ulang setelah 24 jam
  * ulangi pengecekan sampai status berubah

* Jika status = SETTLED / COMPLETED:

  * informasikan dana tidak bisa ditarik otomatis
  * tawarkan Good Faith Refund Request
  * jika nasabah setuju → eskalasi ke Agent
  * jika tidak → berikan panduan menghubungi bank penerima

### Aturan eskalasi

* Jika refund belum diterima > 3 hari kerja → eskalasi
* Jika nominal > USD 100.000 → eskalasi sebagai potensi fraud

---

## SOP 2 – DOUBLE DEBIT (PENDEBETAN GANDA)

### Kapan SOP ini digunakan

Gunakan SOP ini jika:

* terdapat dua transaksi identik
* nominal dan waktu sama

### Data yang WAJIB dikumpulkan

* tanggal dan waktu transaksi
* nominal transaksi
* bank tujuan
* rekening tujuan
* reference ID transaksi pertama
* reference ID transaksi kedua

### Alur logika

1. Verifikasi nasabah.
2. Jika gagal → STOP.
3. Kumpulkan data transaksi.
4. Jika data belum lengkap → STOP.
5. Buat tiket.
6. Cek apakah ada transaksi duplikat di sistem.

### Keputusan

* Jika duplikat ADA:

  * eskalasi ke Agent
  * informasikan proses 3–5 hari kerja

* Jika duplikat TIDAK ADA:

  * informasikan tidak ada transaksi ganda di sistem
  * tawarkan investigasi lanjutan

### Aturan eskalasi

* Jika nasabah minta investigasi lanjutan → eskalasi sebagai potensi fraud

---

## SOP 3 – TRANSFER PENDING / TIMEOUT

### Kapan SOP ini digunakan

Gunakan SOP ini jika:

* transfer belum selesai
* penerima belum menerima dana melewati waktu normal

### Data yang WAJIB dikumpulkan

* tanggal dan waktu transaksi
* nominal transaksi
* bank tujuan
* rekening tujuan
* reference ID

### Alur logika

1. Verifikasi nasabah.
2. Kumpulkan data transaksi.
3. Jika data belum lengkap → STOP.
4. Buat tiket.
5. Cek status transaksi.
6. Informasikan nasabah untuk menunggu 24 jam.
7. Cek ulang status setelah 24 jam.

### Aturan eskalasi

* Jika setelah 48 jam status tidak berubah → eskalasi ke Agent

---

## SOP 4 – TRANSFER KE REKENING SALAH

### Kapan SOP ini digunakan

Gunakan SOP ini jika:

* transaksi sudah settled
* rekening tujuan valid
* tetapi penerima salah

### Data yang WAJIB dikumpulkan

* tanggal dan waktu transaksi
* nominal transaksi
* bank tujuan
* rekening tujuan
* reference ID

### Alur logika

1. Verifikasi nasabah.
2. Kumpulkan data transaksi.
3. Jika data belum lengkap → STOP.
4. Buat tiket.
5. Informasikan dana tidak bisa ditarik otomatis.
6. Tawarkan Good Faith Refund Request.
7. Jika nasabah setuju → eskalasi ke Agent.
8. Jika tidak → berikan panduan menghubungi bank penerima.

### Aturan eskalasi

* Jika transaksi tidak ditemukan dan terindikasi fraud → eskalasi

---

## SOP 5 – PEMBAYARAN MERCHANT / GATEWAY GAGAL

### Kapan SOP ini digunakan

Gunakan SOP ini jika:

* saldo terpotong
* pembayaran ditolak merchant
* transaksi tidak tercatat di merchant

### Data yang WAJIB dikumpulkan

* tanggal dan waktu transaksi
* nama merchant
* transaction ID dari merchant
* payment channel (transfer/debit/credit)

### Alur logika

1. Verifikasi nasabah.
2. Kumpulkan data transaksi.
3. Jika data belum lengkap → STOP.
4. Buat tiket.
5. Eskalasi ke Agent.
6. Informasikan proses hingga 7 hari kerja.
7. Update status setiap 24 jam.

---

## SOP 6 – PEMBATALAN / REVERSAL TRANSAKSI

### Kapan SOP ini digunakan

Gunakan SOP ini jika:

* nasabah meminta pembatalan segera setelah transaksi dibuat
* transaksi belum settlement

### Data yang WAJIB dikumpulkan

* tanggal dan waktu transaksi
* transaction ID
* reference ID
* alasan pembatalan

### Alur logika

1. Verifikasi nasabah.
2. Kumpulkan data transaksi.
3. Jika data belum lengkap → STOP.
4. Buat tiket.
5. Cek status transaksi.

### Keputusan

* Jika status = PENDING:

  * ajukan reversal
  * informasikan proses 1x24 jam

* Jika status = SETTLED:

  * arahkan ke SOP 4

### Aturan eskalasi

* Jika reversal gagal → eskalasi ke Agent

---

## SOP 7 – AUTO-DEBIT / SUBSCRIPTION ISSUE

### Kapan SOP ini digunakan

Gunakan SOP ini jika:

* auto-debit tidak sah
* double charge subscription

### Data yang WAJIB dikumpulkan

* tanggal dan waktu transaksi
* nama merchant / merchant ID
* transaction ID
* bukti aktivasi auto-debit

### Alur logika

1. Verifikasi nasabah.
2. Kumpulkan data transaksi.
3. Jika data belum lengkap → STOP.
4. Buat tiket.
5. Eskalasi ke Agent.
6. Update status setiap 24 jam.

### Aturan eskalasi

* Jika terindikasi penipuan → eskalasi sebagai fraud

---

## SOP 8 – SALDO TERPOTONG KARENA ERROR

### Kapan SOP ini digunakan

Gunakan SOP ini jika:

* saldo berubah
* tidak ada transaksi yang dilakukan nasabah

### Data yang WAJIB dikumpulkan

* nomor rekening
* saldo sebelum terpotong
* saldo setelah terpotong
* tanggal dan waktu perubahan saldo

### Alur logika

1. Verifikasi nasabah.
2. Kumpulkan data saldo.
3. Jika data belum lengkap → STOP.
4. Buat tiket.
5. Eskalasi ke Agent.
6. Update status setiap 24 jam.

### Aturan eskalasi

* Jika terindikasi penipuan → eskalasi sebagai fraud

---

## SOP 9 – PERMINTAAN BUKTI TRANSAKSI

### Kapan SOP ini digunakan

Gunakan SOP ini jika:

* nasabah meminta mutasi / receipt

### Data yang WAJIB dikumpulkan

* nomor rekening
* salah satu:

  * transaction ID
  * atau periode waktu transaksi

### Aturan khusus

* periode maksimum = 30 hari
* jika lebih → arahkan ke kantor cabang

### Alur logika

1. Verifikasi nasabah.
2. Kumpulkan data permintaan.
3. Jika data belum lengkap → STOP.
4. Ambil data transaksi.
5. Masking PII:

   * rekening → 4 digit terakhir
   * nama penerima → 4 huruf depan & belakang
6. Kirim bukti via email terdaftar.

---

## FINAL NOTE (UNTUK COPILOT)

* SOP ini adalah **aturan sistem**
* Tidak boleh diinterpretasi bebas
* Semua IF / THEN harus diimplementasikan eksplisit
* Missing data = STOP execution
* Eskalasi hanya jika kondisi terpenuhi
