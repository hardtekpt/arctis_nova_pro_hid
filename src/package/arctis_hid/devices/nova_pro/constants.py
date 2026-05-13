# ── Device identification ──────────────────────────────────────────────────

VID  = 0x1038
PIDS = frozenset({0x12CB, 0x12CD, 0x12E0, 0x12E5, 0x225D})

INTERFACE     = 4
USAGE_CONTROL = 0xFFC0   # Col01 — bidirectional: queries + writes
USAGE_EVENTS  = 0xFF00   # Col02 — read-only: unsolicited events

REPORT_ID   = 0x06
PACKET_SIZE = 64
POLL_TIMEOUT_MS = 50

# ── Query command bytes ────────────────────────────────────────────────────

CMD_STATUS       = 0xB0   # battery, connectivity, ANC, mic mute, mic LED, wireless mode
CMD_MIC_EQ       = 0x20   # gain, mic vol, sidetone, audio output, ChatMix, EQ bands
CMD_FIRMWARE     = 0x10   # ASCII firmware version (also pushed unsolicited on reconnect)
CMD_SERIAL       = 0x12   # ASCII serial number
CMD_DISPLAY      = 0x80   # base-station display: dim timeout, OLED brightness, home screen
CMD_CONNECTIVITY = 0xB5   # connectivity mode + BT connected state
CMD_VOL_LIMITER  = 0x26   # volume limiter state
CMD_BATTERY      = 0xB7   # battery levels: headset + dock

# ── Write command bytes ────────────────────────────────────────────────────

CMD_VOL          = 0x25   # headset volume (inverted encoding)
CMD_MIC_VOL      = 0x37   # mic volume 1–10
CMD_SIDETONE     = 0x39   # sidetone 0–3
CMD_OLED_BRIGHT  = 0x85   # OLED brightness 1–10
CMD_ANC          = 0xBD   # ANC mode 0=off 1=transparency 2=ANC
CMD_TRANSP_LEVEL = 0xB9   # transparency level 1–10
CMD_DIM_TIMEOUT  = 0x83   # dim screen timeout step 0–6
CMD_HOME_SCREEN  = 0x89   # home screen mode 0=detailed 1=simple
CMD_MIC_LED      = 0xBF   # mic LED brightness 1–10
CMD_AUTO_OFF     = 0xC1   # auto-off timeout step 0–6
CMD_GAIN         = 0x27   # gain (0x01=low, 0x02=high — same encoding for write/event/query)
CMD_USB_INPUT    = 0x23   # USB input 0x00=Input1 0x01=Input2 (silent — no Col02 event)
CMD_CHATMIX_EN   = 0x49   # ChatMix enable 0=off 1=on
CMD_WIRELESS     = 0xC3   # 2.4 GHz mode 0=performance 1=extended (silent — no Col02 event)
CMD_BT_DEFAULT   = 0xB2   # BT default 0=off 1=on
CMD_BT_AUTOMUTE  = 0xB3   # BT auto-mute 0=off 1=-12dB 2=full
CMD_AUDIO_OUT    = 0x43   # audio output 1=speakers 2=stream
CMD_STREAM_VOLS  = 0x47   # stream volumes multi-byte [main, 0x00, aux, mic]
CMD_EQ_PRESET    = 0x2E   # EQ preset index (0x04=custom)
CMD_EQ_BANDS     = 0x33   # custom EQ bands — 10 bytes at [2–11], each 0–40
CMD_SAVE         = 0x09   # persist all writes to flash — always send after writes
CMD_FACTORY_RESET = 0xFD  # ⚠ factory reset — erases all settings; do NOT send 0x09 after

# ── OLED commands (feature reports, not interrupt writes) ──────────────────
# Protocol confirmed; pixel format and display geometry to be verified by capture.

CMD_OLED_DRAW    = 0x93   # draw custom frame — 1024-byte HID feature reports, 2 per frame
CMD_OLED_RELEASE = 0x95   # return OLED control to GG / Sonar

OLED_REPORT_SIZE       = 1024   # bytes per feature report (including report-ID byte)
OLED_REPORTS_PER_FRAME = 2      # left half (x=0) then right half (x=64)
OLED_REPORT_SPLIT_SZ   = 64     # columns per report (max width ggoled sends per chunk)
OLED_WIDTH             = 128    # confirmed via ggoled source (ggoled SCREEN_WIDTH)
OLED_HEIGHT            = 64     # confirmed via ggoled source (ggoled SCREEN_HEIGHT)

# ── 0xB5 response byte indices ─────────────────────────────────────────────

B5_CONN         = 2   # 0x01=2.4GHz only  0x04=2.4GHz+BT (ConnectivityMode)
B5_BT_CONNECTED = 3   # 0x01=BT device connected  0x02=not connected

# ── 0x26 response byte indices ─────────────────────────────────────────────

B26_LIMITER = 2   # 0x01=limiter on  0x02=limiter off

# ── 0xB7 response byte indices ─────────────────────────────────────────────

B7_HBAT = 2   # headset battery raw (÷8×100=%)
B7_DBAT = 3   # dock battery raw   (÷8×100=%)
B7_PWR = 4   # headset powered on/in dock: 0x08=on, 0x01=off/removed

# ── 0xB0 response byte indices ─────────────────────────────────────────────

B0_BT_DEFAULT  = 2    # 0x00=off  0x01=on (BT default auto-connect) ✅ confirmed 2026-05-09
B0_BT_AUTOMUTE = 3    # 0x00=off  0x01=-12dB  0x02=full (BT auto-mute) ✅ confirmed 2026-05-09
B0_CONN        = 4    # 0x01=2.4GHz only  0x04=2.4GHz+BT
B0_BT          = 5    # 0x00=off  0x01=active
B0_HBAT        = 6    # headset battery raw (÷8×100=%)
B0_DBAT        = 7    # dock battery raw   (÷8×100=%)
B0_MUTE        = 9    # 0x00=unmuted  0x01=muted
B0_ANC         = 10   # 0x00=off  0x01=transparency  0x02=ANC
B0_MIC_LED     = 11   # mic LED brightness 1–10
B0_AUTO_OFF    = 12   # auto-off timeout 0=off 1=1min … 6=60min ✅ confirmed 2026-05-09
B0_MODE2G      = 13   # 0x00=performance  0x01=extended range
B0_PWR         = 15   # headset powered on/in dock: 0x08=on, 0x01=off/removed (same as 0xB7[4])

# ── 0x80 response byte indices ─────────────────────────────────────────────

B80_DIM_TIMEOUT = 2   # dim screen timeout 0=off 1=1min … 6=60min ✅ confirmed 2026-05-09
B80_OLED_BRIGHT = 3   # OLED brightness 1–10 ✅ confirmed 2026-05-09
B80_HOME_SCREEN = 5   # 0x00=detailed  0x01=simple ✅ confirmed 2026-05-09
B80_SONAR       = 7   # 0x00=GG Sonar not running  0x01=running

# ── 0x20 response byte indices ─────────────────────────────────────────────

M20_USB       = 2               # USB input 0x00=Input1  0x01=Input2
M20_VOL       = 3               # headset volume raw (inverted)
M20_GAIN      = 4               # 0x01=low  0x02=high
M20_EQ_PRESET = 6               # EQ preset index
M20_EQ        = slice(7, 17)    # 10 EQ band values
M20_MICVOL    = 17              # mic volume 1–10
M20_SIDETONE  = 18              # 0=off 1=low 2=medium 3=high
M20_AUDIO     = 19              # 0x01=speakers  0x02=stream
M20_GAME      = 20              # ChatMix game 0–100
M20_CHAT      = 21              # ChatMix chat 0–100
M20_SMAIN     = 22              # stream main volume 0–100
M20_SAUX      = 24              # stream aux volume 0–100
M20_SMIC      = 25              # stream mic volume 0–100
