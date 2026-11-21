# Flop Proof Workflow

GitHub Actions workflow yang otomatis membuat proof-of-contribution Flop Labs
(`flop-proofs/*.json` + `.md`) setiap kali ada push ke branch utama atau
release baru diterbitkan. Memakai skrip dari skill **Flop Contribution Proof
Generator** (`scripts/generate_contribution_record.py` dan
`scripts/verify_contribution.py`).

## Cara pakai

1. Repo ini sudah berisi workflow (`.github/workflows/`) dan folder `scripts/`
   dari skill — tidak perlu menyalin apa pun.
2. Buat secret **FLOP_DID**:
   - Buka repository di GitHub → **Settings** → **Secrets and variables** →
     **Actions** → **New repository secret**.
   - Name: `FLOP_DID`
   - Value: DID publik Technocore kamu, contoh `did:key:z6Mk...`
   - DID ini publik by design (bukan private key), tapi disimpan sebagai
     secret supaya tidak tertulis di file workflow.
3. Pastikan workflow boleh push: **Settings** → **Actions** → **General** →
   **Workflow permissions** → pilih **Read and write permissions**.
   (Workflow ini juga meminta `permissions: contents: write`.)
4. Push ke `main` atau terbitkan release — workflow akan membuat record,
   memverifikasinya, lalu meng-commit hasilnya ke folder `flop-proofs/`
   di branch utama dengan pesan `[skip ci]`.

## Yang dihasilkan

- `flop-proofs/proof-<tag>.json` + `.md` untuk release.
- `flop-proofs/proof-main-<sha>.json` + `.md` untuk push ke main.
- Setiap record diverifikasi dulu dengan `verify_contribution.py --json`;
  kalau INVALID, workflow gagal dan tidak ada file yang di-commit.
- Ringkasan proof tampil di log Actions dan di halaman ringkasan run.
  Catatan: GitHub otomatis menyamarkan nilai secret di log, jadi DID akan
  tampil sebagai `***` di log — nilai aslinya tetap ada di file yang
  di-commit.

## Troubleshooting

- `FLOP_DID secret is not set` — buat secret seperti langkah 2 di atas.
- `git push` ditolak (403) — cek Workflow permissions (langkah 3), dan
  pastikan branch utama tidak dilindungi aturan yang melarang push langsung
  (branch protection yang mewajibkan pull request akan memblokir push bot).
- `INVALID` di langkah verify — baca alasan di log; biasanya URL atau
  deskripsi tidak lolos guardrail (lihat SKILL.md skill ini).

## Lisensi

MIT — lihat file `LICENSE`.
