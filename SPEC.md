# 📘 PROJECT SPECIFICATION

## Customer Support SOP Engine

### PoC – Python – LangGraph – CLI (Continuous Run)

---

## 1. Tujuan Project

Membangun **Proof-of-Concept Customer Support SOP Engine** menggunakan **Python dan LangGraph** untuk memvalidasi:

* kebenaran alur SOP
* desain node LangGraph
* branching dan decision rule
* early-exit behavior
* multi-turn data completion

Project ini **tidak ditujukan untuk produksi** dan **tidak terhubung ke sistem nyata**.

---

## 2. Model Interaksi (SANGAT PENTING)

### Continuous CLI Execution

Aplikasi berjalan **secara terus-menerus** di terminal.

Pola interaksi:

```
(loop)
  ├─ baca input user (stdin)
  ├─ jalankan LangGraph
  ├─ cetak output (stdout)
  └─ tunggu input berikutnya
```

Aturan utama:

* **Setiap input user → LangGraph dijalankan ulang dari node START**
* Graph akan berhenti jika:

  * mencapai DONE, atau
  * melakukan EARLY EXIT (misalnya butuh data tambahan)
* Setelah graph berhenti:

  * sistem mencetak output
  * sistem kembali meminta input user

Program **TIDAK exit** kecuali dihentikan manual.

---

## 3. Prinsip Desain Utama

1. LangGraph adalah **state machine**, bukan chatbot
2. Flow dikontrol oleh graph, bukan oleh LLM
3. Semua keputusan bisnis harus deterministik
4. Missing data = STOP execution
5. Graph selalu restart dari START, node akan skip sendiri
6. PoC fokus ke **alur**, bukan integrasi

---

## 4. Technology Stack

* Language: **Python**
* Orchestration: **LangGraph**
* Interface: **CLI (stdin / stdout)**
* LLM: digunakan terbatas (lihat section 8)
* Storage: **in-memory Python variable**
* Persistence: **tidak ada** (selama runtime saja)

---

## 5. State Management

Sistem menggunakan **satu shared mutable state** yang:

* diteruskan ke semua node
* disimpan di memory
* bertahan antar input user
* menentukan node mana yang dijalankan / diskip

### State Structure

```python
SOPState = {
    "sop_type": None,

    "verification": {
        "email": None,
        "phone": None,
        "status": "NOT_STARTED"  # NOT_STARTED | FAILED | VERIFIED
    },

    "collected_data": {},

    "current_step": "START",  # START | WAITING_USER | DONE

    "result": {
        "status": None,        # SUCCESS | NEED_INPUT | ERROR | ESCALATED
        "message": None,
        "missing_fields": None,
        "next_action": None
    }
}
```

---

## 6. Conversation History (LLM Memory)

* Conversation history disimpan di variable Python (list)
* History ini diteruskan ke LLM setiap kali dipanggil
* Tidak ada external memory / vector store

Contoh:

```python
conversation_history = [
    {"role": "user", "content": "transfer saya gagal"},
    {"role": "assistant", "content": "mohon data tambahan"}
]
```

History digunakan **hanya** untuk:

* intent classification
* data extraction
* natural language response

---

## 7. SOP Scope

Sistem menangani SOP berikut:

* TRANSFER_GAGAL
* DOUBLE_DEBIT
* TRANSFER_PENDING
* SALAH_REKENING
* MERCHANT_GAGAL
* PEMBATALAN_TRANSAKSI
* AUTODEBIT_ISSUE
* SALDO_ERROR
* MINTA_BUKTI_TRANSAKSI

SOP dipilih secara deterministik.

---

## 8. Aturan Penggunaan LLM (KETAT)

LLM BOLEH digunakan untuk:

1. Mengklasifikasikan SOP dari input user
2. Mengekstrak field terstruktur dari bahasa natural
3. Menghasilkan pesan output yang manusiawi

LLM TIDAK BOLEH digunakan untuk:

* menentukan refund
* menentukan eskalasi
* memilih cabang SOP
* memverifikasi kebenaran data
* menggantikan rule validation

Semua keputusan bisnis harus berbasis rule + state.

---

## 9. Model Validasi Data

Setiap SOP memiliki daftar **required fields** yang tetap.

Aturan:

* Jika satu atau lebih required field belum tersedia:

  * LangGraph HARUS berhenti
  * `current_step` = `WAITING_USER`
  * `result.status` = `NEED_INPUT`
  * `missing_fields` diisi

Tidak ada partial execution.

---

## 10. Model Eksekusi LangGraph

### Aturan Global

* Graph SELALU dimulai dari node `START`
* Tidak ada resume dari node tengah
* Node harus idempotent
* Node harus bisa diskip

### Pola Node Wajib

```python
def node(state):
    if kondisi_sudah_terpenuhi(state):
        return state  # skip node
    # lakukan kerja node
    return state
```

---

## 11. Early Exit Behavior

Early exit adalah **perilaku normal**, bukan error.

Early exit terjadi jika:

* verifikasi gagal
* data belum lengkap
* terjadi error SOP
* eskalasi dibutuhkan

Saat early exit:

* graph berhenti
* hasil dicetak ke terminal
* sistem menunggu input berikutnya

---

## 12. Side Effects (PoC Mode)

Semua side effect **DISIMULASIKAN**.

Tidak boleh ada:

* API call
* DB query
* network request

Semua side effect HARUS berupa:

```python
print("[SIDE_EFFECT]", action_name, payload)
```

Contoh:

* CREATE_TICKET
* AUTO_REFUND
* ESCALATE_AGENT
* SEND_EMAIL

---

## 13. Data Source (PoC Mode)

Semua data diambil dari **static mock data**.

Diperbolehkan:

* dictionary Python
* list hardcoded
* file mock lokal

Dilarang:

* database
* API
* LLM reasoning untuk fakta

---

## 14. Verifikasi Nasabah (PoC)

Verifikasi dilakukan secara simulasi.

Aturan:

* email harus ada di mock user list
* phone harus ada di mock user list

Jika salah satu tidak cocok:

* verifikasi gagal
* graph berhenti

---

## 15. Pola Multi-turn Interaction

Interaksi bersifat **multi-turn, satu langkah per input**.

Contoh:

Turn 1
User: “transfer saya gagal”
System: “Mohon lengkapi: nominal, reference_id”

Turn 2
User: “nominal 1 juta, ref ABC123”
System: “Refund sedang diproses (1–3 hari kerja)”

LangGraph dijalankan penuh **di setiap turn**.