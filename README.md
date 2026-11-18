# GTA 6 Clipper — Streamer Moments → YouTube Shorts

> **English summary below.** Dibuat untuk zeze: jadi clipper streamer besar
> yang main GTA VI, posting klip ke YouTube Shorts.

Alat + skill AI untuk mengubah stream GTA VI yang panjang jadi Shorts vertikal
15–60 detik: deteksi momen dari **lonjakan chat Twitch**, potong vertikal
9:16, kasih caption (EN→ID), lalu posting ke YouTube Shorts.

**Diadaptasi dari** [op7418/Youtube-clipper-skill](https://github.com/op7418/Youtube-clipper-skill)
(MIT) — lihat [ATTRIBUTION.md](ATTRIBUTION.md). Yang ditambah di sini:
deteksi chat-spike Twitch, potong vertikal 9:16, caption faster-whisper,
subtitle EN→ID, dan workflow khusus clipper GTA VI.

---

## Kenapa chat, bukan nonton VOD 6 jam?

Saat ada momen gila di stream, **chat meledak beberapa detik SETELAH momen
itu terjadi**. Jadi lonjakan pesan per 10 detik = penanda momen, dan klip
harus mulai ~20 detik LEBIH AWAL dari spike. Itu rahasia workflow ini —
dan kenapa kecepatan posting di launch week menentukan siapa yang menang.

## Workflow — 2 rute

### Rute A — VOD (setelah stream selesai)

```text
1. Pilih streamer      -> streamers.md (cek izin clip dulu!)
2. Download VOD + chat -> TwitchDownloaderCLI
                          videodownload --id <vod_id>
                          chatdownload  --id <vod_id> -o chat.json -E
3. Deteksi momen        -> python3 scripts/twitch_chat_spikes.py --chat chat.json
                          (output: kandidat momen, clip_start = spike - 20 dtk)
4. Review kandidat      -> pilih 3-10 momen terbaik (jangan semua spike)
5. Potong vertikal      -> python3 scripts/vertical_cut.py --input vod.mp4 \
                             --start <clip_start> --duration 30 --layout gameplay
6. Caption              -> python3 scripts/caption_whisper.py --input clip.mp4 \
                             --output clip.srt   (atau subtitle YouTube + translate)
                          -> terjemah EN->ID: scripts/translate_subtitles.py
                          -> bakar ke video (vertical_cut.py --srt clip_id.srt)
7. Copy Shorts          -> python3 scripts/generate_summary.py --streamer Lacy
8. Upload ke Shorts     -> YouTube Studio / YouTube Data API (manual dulu)
```

### Rute B — LIVE (saat stream masih jalan, paling cepat)

```text
1. Streamlink rekam live begitu streamer live
2. Baca chat anonim via IRC (tanpa akun/token)
3. Hitung pesan per 10 detik -> spike -> FFmpeg potong otomatis
4. Whisper caption -> upload dalam hitungan menit
```

Rute B butuh mesin yang selalu nyala saat stream jalan. Rute A cukup
dijalankan setelah VOD tersedia — ini rute yang direkomendasikan buat mulai.

## Instalasi

```bash
git clone https://github.com/0x-zeze/gta6-clipper.git
cd gta6-clipper
pip install -r requirements.txt
cp .env.example .env   # sesuaikan bila perlu
```

Butuh di sistem: **Python 3.8+**, **yt-dlp**, **FFmpeg (dengan libass
untuk bakar subtitle)**, dan **TwitchDownloaderCLI** untuk VOD + chat
Twitch (lihat [references/twitch-guide.md](references/twitch-guide.md)).

Opsional: `faster-whisper` untuk caption otomatis
(`pip install faster-whisper`). Tanpa itu, pakai subtitle YouTube +
`translate_subtitles.py`.

### Sebagai skill (Muse / Claude Code)

```bash
npx skills add https://github.com/0x-zeze/gta6-clipper
```

atau salin folder ini ke `~/.claude/skills/gta6-clipper/`. Lalu tinggal
bilang ke agen: "Clip momen GTA 6 dari VOD ini".

## ⚠️ HARDWARE — baca dulu

**JANGAN proses video berat di VM kecil.** VM ini (~1 GB RAM bebas, tanpa
GPU) hanya untuk nulis script, tes logika spike detector, dan potong klip
pendek. Download VOD ber-GB, transkrip Whisper, dan render vertikal
**jalan di PC/laptop kamu** (disarankan: 8 GB+ RAM, GPU bila ada).
`caption_whisper.py` default model `tiny` supaya masih jalan di CPU lemah.

## Aturan clip — keras

1. **Hanya clip streamer yang mengizinkan.** Izin = campaign aktif yang
   aturannya kamu ikuti (mis. Lacy GTA VI Marathon Pool di Content Rewards),
   atau pernyataan eksplisit streamer. Tanpa itu = JANGAN posting.
   Daftar + status izin: [streamers.md](streamers.md).
2. **Footage GTA VI milik Rockstar.** Content ID bisa klaim monetisasi.
   Selalu kredit streamer di caption + deskripsi.
3. **Jangan re-upload mentah.** Klip = momen 15–60 detik, vertikal,
   ada edit/caption — bukan VOD utuh.
4. **Ikuti brief campaign sampai titik.** Kalau ikut campaign berbayar
   (Content Rewards / Reach): tag wajib, disclosure, batas views, dan
   tenggat submit link (≤30 menit setelah posting) harus dipatuhi —
   satu pelanggaran = klip tidak di-approve.

## Struktur repo

```text
gta6-clipper/
├── README.md                  # file ini
├── SKILL.md                   # workflow 6 tahap buat AI agent
├── ATTRIBUTION.md             # atribusi MIT + apa yang diubah
├── streamers.md               # shortlist streamer + status izin (launch day)
├── .env.example               # konfigurasi
├── requirements.txt
├── scripts/
│   ├── twitch_chat_spikes.py  # BARU: deteksi momen dari chat Twitch
│   ├── vertical_cut.py        # BARU: potong 9:16 (gameplay / facecam)
│   ├── caption_whisper.py     # BARU: transkrip faster-whisper -> .srt
│   ├── translate_subtitles.py # EN -> Bahasa Indonesia (diadaptasi)
│   ├── generate_summary.py    # copy Shorts EN+ID (diadaptasi)
│   ├── download_video.py      # yt-dlp download (dari repo asal)
│   ├── clip_video.py          # potong FFmpeg presisi (dari repo asal)
│   ├── burn_subtitles.py      # bakar subtitle libass (dari repo asal)
│   ├── extract_subtitle_clip.py
│   ├── analyze_subtitles.py   # analisis chapter semantik (dari repo asal)
│   ├── merge_bilingual_subtitles.py
│   └── utils.py
└── references/
    ├── twitch-guide.md        # BARU: TwitchDownloader + chat JSON
    ├── ffmpeg-guide.md
    ├── yt-dlp-guide.md
    └── subtitle-formatting.md
```

## Kampanye clipping GTA 6 (saat repo ini dibuat, 18–19 Nov 2026)

- Content Rewards: 5 kampanye GTA 6. 3 bayar **$0,70–$2,00 / 1.000 views**,
  2 bagi pool. Kreator: Tomo, Lacy, Clix, Dasgasd3m.
- **Lacy GTA VI Marathon Pool: $12.500**, butuh ≥1.000.000 approved views,
  Lacy fokus utama, caption wajib nama + #LACY. (Cek brief terbaru
  sebelum posting — kampanye buka-tutup cepat.)
- Fee Content Rewards 10%. Klip menghasilkan 7 hari setelah approve.

## Lisensi

MIT — lihat [LICENSE](LICENSE). Atribusi ke op7418/Youtube-clipper-skill
dipertahankan di [ATTRIBUTION.md](ATTRIBUTION.md).

---

## English summary

GTA VI clipper toolkit: detect viral moments from Twitch chat spikes,
cut them into 9:16 vertical Shorts, caption them (EN→ID), and post to
YouTube Shorts. Two routes: **VOD** (download VOD + chat with
TwitchDownloader, detect spikes, cut, caption, upload) and **LIVE**
(record + spike-cut while streaming). Adapted from
op7418/Youtube-clipper-skill (MIT). Only clip streamers who allow it —
see streamers.md. Heavy video work runs on your own PC, not a thin VM.
