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

## Format referensi (default) — Typical Gamer Shorts

Format yang dipakai semua klip sekarang, diverifikasi dari Shorts
Typical Gamer "The Biggest Problem with GTA 6…" (28 detik) dan
direproduksi di sini pada klip Kai Cenat (`kai-ref2.mp4`, 1080x1920):

- **Layout facecam-top**: facecam streamer di panel atas 45%
  (1080x864), gameplay di bawah 55% (1080x1056). Output 1080x1920 30fps.
- **Border oranye** di sekeliling panel facecam:
  `drawbox x=0 y=0 w=1080 h=864 color 0xFF6B00 thickness 8`.
  (Sudut membulat + glow di referensi asli = TODO, belum ronde ini.)
- **Caption kata-per-kata BESAR**: ALL-CAPS, putih tebal outline hitam,
  1 kata per event, posisi tepat di bawah facecam (tengah-atas panel
  gameplay). File `.ass` dengan PlayRes 1080x1920, font DejaVu Sans 110,
  Bold, BorderStyle 1, Outline 3, Alignment 8, MarginV 890, durasi kata
  minimal 0,12 detik.
- **Durasi target 25–35 detik; hook = kata-kata pertama yang diucapkan**
  (bukan judul statis di atas).
- **JANGAN** bakar caption besar via filter `subtitles` + `.srt`:
  SRT dikonversi ke ASS dengan PlayRes default 384x288 sehingga FontSize
  diskalakan ~6,7x dan huruf jadi raksasa (sudah terbukti gagal di render
  pertama). Selalu pakai file `.ass` asli + filter `ass`.

Resep FFmpeg (angka crop facecam contoh klip Kai Cenat; beda streamer
beda angka — jadikan parameter `--facecam x:y:w:h`):

```bash
[0:v]split[a][b];
[a]crop=736:720:272:0,scale=1080:1056[game];
[b]crop=255:198:15:520,scale=1080:864[cam];
[cam][game]vstack,drawbox=x=0:y=0:w=1080:h=864:color=0xFF6B00:t=8,ass='kai-words.ass'[v]
```

Perintah lengkap:

```bash
# 1. Transkrip kata-per-kata -> .ass (faster-whisper tiny, CPU, int8)
~/workspace/whisper-venv/bin/python scripts/caption_whisper.py \
    --input clip.mp4 --output clip.ass --model tiny --language en
# 2. Potong vertikal format referensi
python3 scripts/vertical_cut.py --input clip.mp4 --start 0 --duration 30 \
    --style ref --facecam 15:520:255:198 --ass clip.ass --output clip_01.mp4
```

**Penting — sinkronisasi timestamp:** `.ass` harus ditranskrip dari
file segmen yang SAMA yang dipakai `vertical_cut.py`, dan `--start`
harus 0 (atau offset yang sama). Kalau `.ass` dibuat dari VOD utuh,
timestamp katanya tidak cocok dengan hasil `-ss` dan caption tidak muncul.

Catatan transkripsi: PyAV 19 menolak kwarg `metadata_errors` yang
dipakai faster-whisper — `caption_whisper.py` sudah mem-patch `av.open`
untuk membuang kwarg itu sebelum transcribe. Model tiny ter-download ke
`~/.cache/huggingface`.

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
5. Potong segmen mentah -> potong dulu segmen 16:9 (scripts/clip_video.py)
                          atau pakai file klip Twitch langsung (clip.mp4)
6. Caption kata-per-kata-> ~/workspace/whisper-venv/bin/python scripts/caption_whisper.py \
                             --input clip.mp4 --output clip.ass
                          (atau subtitle YouTube + translate EN->ID)
7. Potong vertikal      -> python3 scripts/vertical_cut.py --input clip.mp4 \
                             --start 0 --duration 30 --style ref \
                             --facecam <x:y:w:h> --ass clip.ass
                          (format referensi = default; layout lama
                          gameplay/facecam-top/facecam-bottom tetap ada;
                          .ass harus dari file segmen yang sama — lihat
                          "Format referensi" di atas)
8. Copy Shorts          -> python3 scripts/generate_summary.py --streamer Lacy
9. Upload ke Shorts     -> youtube-upload skill (yt-upload CLI, Data API v3,
                          private dulu, dry-run + approval per video;
                          butuh setup OAuth sekali oleh kamu) atau manual
                          via YouTube Studio kalau belum di-setup
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
(`pip install faster-whisper` — di VM ini sudah ada di
`~/workspace/whisper-venv/`). Tanpa itu, pakai subtitle YouTube +
`translate_subtitles.py`.

### Sebagai skill (Muse / Claude Code)

```bash
npx skills add https://github.com/0x-zeze/gta6-clipper
```

atau salin folder ini ke `~/.claude/skills/gta6-clipper/`. Lalu tinggal
bilang ke agen: "Clip momen GTA 6 dari VOD ini".

## Skill pendukung (diinstal 19 Nov 2026)

Empat skill dari GitHub (semua MIT) yang menunjang pipeline ini — ada di
`~/workspace/custom-skills/`:

- **viral-hooks** (rediumvex/viral-hooks-skill, 137★) — 100 formula hook
  dari 10 trigger psikologi. Dipakai untuk judul + baris pertama deskripsi
  Shorts. Hook video tetap kata pertama yang diucapkan (format referensi);
  skill ini menulis teks kemasannya.
- **video-to-shorts** (social-media-skills, MIT) — rubrik skor klip
  100 poin + hard gates untuk menilai kandidat momen dari chat-spike
  (kirim yang skor ≥70), plus spek safe area caption dan audio -14 LUFS.
  Script render/posting-nya TIDAK dipakai — pipeline tetap FFmpeg format
  referensi di sini.
- **tiktok-video-skills** (iart-ai, MIT) — grammar retensi short-form:
  pattern interrupt tiap 2–4 detik (paling murah: punch-in zoom),
  safe area 9:16 (pusat 900×1400, bawah 320px kosong), teknik loop,
  caption-animation kata-per-kata. Delivery-nya Remotion — diambil
  grammar-nya, bukan renderer-nya.
- **youtube-upload** (grapeot, MIT) — auto-upload via YouTube Data API v3
  resmi. Private by default, dry-run dulu, tidak pernah publish.
  CLI `yt-upload` sudah terinstal di `~/workspace/yt-upload-venv/`
  (tes offline repo: 217 passed). Butuh setup satu kali oleh kamu:
  Google Cloud project + OAuth Desktop client + `yt-upload auth`.

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
│   │                            # + style ref (format referensi default)
│   ├── caption_whisper.py     # BARU: transkrip faster-whisper ->
│   │                            # .ass kata-per-kata (format referensi)
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
