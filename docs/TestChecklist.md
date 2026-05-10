# Arctis Nova Pro Wireless — HID Command Test Checklist

Use `python src/listen.py` for all tests unless noted otherwise.  
Mark each item ✅ confirmed / ❌ failed / 🔬 in progress / ⬜ not yet tested.

---

## 1. Incoming Events — Physical Interaction Tests

Verify each event fires and decodes correctly. Interact with the headset/base station as described while the listener is running.

### 1.1 Headset Controls

| # | Command | How to trigger | Expected decode | Status |
|---|---------|---------------|-----------------|--------|
| 1.1.1 | `0x25` Volume | Turn the volume wheel on the headset | `Volume → N% (raw=0xXX)` — % changes with wheel | ⬜ |
| 1.1.2 | `0x25` Volume min | Scroll wheel all the way down | `Volume → 0% (raw=0x38)` | ⬜ |
| 1.1.3 | `0x25` Volume max | Scroll wheel all the way up | `Volume → 100% (raw=0x00)` | ⬜ |
| 1.1.4 | `0xBB` Mic mute — mute | Press the mic mute button | `Mic Mute → muted` | ⬜ |
| 1.1.5 | `0xBB` Mic mute — unmute | Press mic mute again | `Mic Mute → unmuted` | ⬜ |
| 1.1.6 | `0xBD` ANC — off | Cycle ANC to off | `ANC Mode → off` | ⬜ |
| 1.1.7 | `0xBD` ANC — transparency | Cycle ANC to transparency | `ANC Mode → transparency` | ⬜ |
| 1.1.8 | `0xBD` ANC — anc | Cycle ANC to ANC | `ANC Mode → anc` | ⬜ |
| 1.1.9 | `0x27` Gain — low | Press gain button to set low | `Gain Level → low (raw=1)` | ⬜ |
| 1.1.10 | `0x27` Gain — high | Press gain button to set high | `Gain Level → high (raw=2)` | ⬜ |
| 1.1.11 | `0x45` ChatMix — center | Turn ChatMix dial to center | `ChatMix → game=100 chat=100` | ⬜ |
| 1.1.12 | `0x45` ChatMix — game side | Turn ChatMix dial toward game | `game` increases toward 100, `chat` decreases | ⬜ |
| 1.1.13 | `0x45` ChatMix — chat side | Turn ChatMix dial toward chat | `chat` increases toward 100, `game` decreases | ⬜ |

### 1.2 Base Station Controls

| # | Command | How to trigger | Expected decode | Status |
|---|---------|---------------|-----------------|--------|
| 1.2.1 | `0x39` Sidetone — off | Set sidetone to off | `Sidetone → off (level=0)` | ⬜ |
| 1.2.2 | `0x39` Sidetone — low | Set sidetone to low | `Sidetone → low (level=1)` | ⬜ |
| 1.2.3 | `0x39` Sidetone — medium | Set sidetone to medium | `Sidetone → medium (level=2)` | ⬜ |
| 1.2.4 | `0x39` Sidetone — high | Set sidetone to high | `Sidetone → high (level=3)` | ⬜ |
| 1.2.5 | `0x37` Mic volume | Adjust mic volume on base station | `Mic Volume → level=N (range 1–10)` | ⬜ |
| 1.2.6 | `0x85` OLED brightness | Change OLED brightness setting | `OLED Brightness → N/10` | ⬜ |
| 1.2.7 | `0x83` Dim screen — off | Set dim screen timeout to off | `Dim Screen → off (raw=0)` | ⬜ |
| 1.2.8 | `0x83` Dim screen — 1 min | Set dim screen to 1 min | `Dim Screen → 1 min (raw=1)` | ⬜ |
| 1.2.9 | `0x83` Dim screen — 5 min | Set dim screen to 5 min | `Dim Screen → 5 min (raw=2)` | ⬜ |
| 1.2.10 | `0x83` Dim screen — 10 min | Set dim screen to 10 min | `Dim Screen → 10 min (raw=3)` | ⬜ |
| 1.2.11 | `0x83` Dim screen — 15 min | Set dim screen to 15 min | `Dim Screen → 15 min (raw=4)` | ⬜ |
| 1.2.12 | `0x83` Dim screen — 30 min | Set dim screen to 30 min | `Dim Screen → 30 min (raw=5)` | ⬜ |
| 1.2.13 | `0x83` Dim screen — 60 min | Set dim screen to 60 min | `Dim Screen → 60 min (raw=6)` | ⬜ |
| 1.2.14 | `0x89` Home screen — detailed | Set home screen to detailed | `Home Screen → detailed (raw=0)` | ⬜ |
| 1.2.15 | `0x89` Home screen — simple | Set home screen to simple | `Home Screen → simple (raw=1)` | ⬜ |
| 1.2.16 | `0xBF` Mic LED brightness | Change mic LED brightness | `Mic LED → N/10` for each of the 10 levels | ⬜ |
| 1.2.17 | `0xC1` Auto off — off | Set auto off to off | `Auto Off → off (raw=0)` | ⬜ |
| 1.2.18 | `0xC1` Auto off — 1 min | Set auto off to 1 min | `Auto Off → 1 min (raw=1)` | ⬜ |
| 1.2.19 | `0xC1` Auto off — 5 min | Set auto off to 5 min | `Auto Off → 5 min (raw=2)` | ⬜ |
| 1.2.20 | `0xC1` Auto off — 10 min | Set auto off to 10 min | `Auto Off → 10 min (raw=3)` | ⬜ |
| 1.2.21 | `0xC1` Auto off — 15 min | Set auto off to 15 min | `Auto Off → 15 min (raw=4)` | ⬜ |
| 1.2.22 | `0xC1` Auto off — 30 min | Set auto off to 30 min | `Auto Off → 30 min (raw=5)` | ⬜ |
| 1.2.23 | `0xC1` Auto off — 60 min | Set auto off to 60 min | `Auto Off → 60 min (raw=6)` | ⬜ |

### 1.3 Connectivity Events

| # | Command | How to trigger | Expected decode | Status |
|---|---------|---------------|-----------------|--------|
| 1.3.1 | `0xB5` Wireless connect | Turn headset on while base plugged in | `Connectivity → wireless=True bluetooth=False` | ⬜ |
| 1.3.2 | `0xB5` Wireless disconnect | Turn headset off | `Connectivity → wireless=False` | ⬜ |
| 1.3.3 | `0xB5` BT connect | Connect phone/device via Bluetooth | `Connectivity → bluetooth=True` | ⬜ |
| 1.3.4 | `0xB5` BT disconnect | Disconnect Bluetooth source | `Connectivity → bluetooth=False` | ⬜ |
| 1.3.5 | `0xB7` Battery — docked | Place headset in dock | `Battery → headset=N% dock=M%  [4]=0x08` | ⬜ |
| 1.3.6 | `0xB7` Battery — removed | Lift headset out of dock | `Battery → headset=0% dock=M%  [4]=0x01` | ⬜ |
| 1.3.7 | `0xB7` Battery — in use | Leave headset on head, watch for periodic update | `Battery → headset=N% dock=M%` | ⬜ |

---

## 2. Query Commands — Startup Response Tests

Run `python src/listen.py` and check the startup output lines.

| # | Command | Expected field | Expected value | Status |
|---|---------|---------------|----------------|--------|
| 2.1 | `0xB0` Status | `headset_bat` | Matches headset battery indicator | ⬜ |
| 2.2 | `0xB0` Status | `dock_bat` | Matches dock battery indicator | ⬜ |
| 2.3 | `0xB0` Status | `conn` | `2.4GHz` or `2.4GHz+BT` | ⬜ |
| 2.4 | `0xB0` Status | `mic_mute` | `unmuted` when mic is up | ⬜ |
| 2.5 | `0xB0` Status | `anc` | `off` / `transparency` / `anc` matches headset ANC state | ⬜ |
| 2.6 | `0x20` Mic/EQ | `gain` | `low` or `high` matches current gain setting | ⬜ |
| 2.7 | `0x20` Mic/EQ | `mic_vol` | 1–10 matches current mic volume | ⬜ |
| 2.8 | `0x20` Mic/EQ | `sidetone` | `off`/`low`/`medium`/`high` matches current sidetone | ⬜ |
| 2.9 | `0x20` Mic/EQ | `vol` | Matches current headset volume % | ⬜ |
| 2.10 | `0x20` Mic/EQ | `chatmix_game` | Matches dial position (center=100) | ⬜ |
| 2.11 | `0x20` Mic/EQ | `chatmix_chat` | Matches dial position (center=100) | ⬜ |
| 2.12 | `0x20` Mic/EQ | `eq_bands` | 10 hex values; `14 14 14 14 14 14 14 14 14 14` = flat | ⬜ |
| 2.13 | `0x10` Firmware | ASCII string | Firmware version string present, no garbage | ⬜ |
| 2.14 | `0x12` Serial | ASCII string | Serial number string present | ⬜ |
| 2.15 | `0x80` Display | `dim_timeout` | Matches base-station dim screen timeout setting | ⬜ |
| 2.16 | `0x80` Display | `oled_brightness` | 1–10, matches current OLED brightness in GG | ⬜ |
| 2.17 | `0x80` Display | `home_screen_mode` | `detailed` or `simple`, matches GG setting | ⬜ |

---

## 3. Query Field Validation — Change Then Re-query

For each test: set the value on the headset/base station, stop the listener, restart it, and confirm the startup query reflects the new value.

| # | Setting to change | Query to check | Byte | How to verify |
|---|------------------|---------------|------|---------------|
| 3.1 | Set mic mute ON | `0xB0` | `[9]` | Expect `0x01` (muted) at startup |
| 3.2 | Set mic mute OFF | `0xB0` | `[9]` | Expect `0x00` (unmuted) at startup |
| 3.3 | Set ANC = off | `0xB0` | `[10]` | Expect `0x00` |
| 3.4 | Set ANC = transparency | `0xB0` | `[10]` | Expect `0x01` |
| 3.5 | Set ANC = anc | `0xB0` | `[10]` | Expect `0x02` |
| 3.6 | Set volume to 0% | `0x20` | `[3]` | Expect `0x38` |
| 3.7 | Set volume to 50% | `0x20` | `[3]` | Expect `0x1C` (28) |
| 3.8 | Set volume to 100% | `0x20` | `[3]` | Expect `0x00` |
| 3.9 | Set gain = low | `0x20` | `[4]` | Expect `0x01` |
| 3.10 | Set gain = high | `0x20` | `[4]` | Expect `0x02` |
| 3.11 | Set mic volume = 1 | `0x20` | `[17]` | Expect `0x01` |
| 3.12 | Set mic volume = 10 | `0x20` | `[17]` | Expect `0x0A` |
| 3.13 | Set sidetone = off | `0x20` | `[18]` | Expect `0x00` |
| 3.14 | Set sidetone = high | `0x20` | `[18]` | Expect `0x03` |
| 3.15 | Turn ChatMix dial to game | `0x20` | `[20]`/`[21]` | game→100, chat decreases |
| 3.16 | Turn ChatMix dial to chat | `0x20` | `[20]`/`[21]` | chat→100, game decreases |

---

## 4. Write Commands — Send and Verify

Write a Python snippet for each (template at bottom of this section). Send the command, then run a query to confirm the device state changed. Send `0x09` after each write to persist.

**Write packet template:** `[0x06, CMD, PARAM, 0x00, ..., 0x00]` (64 bytes total)

### 4.1 Safe / reversible writes

| # | Command | Param | What to do | Verify via | Status |
|---|---------|-------|-----------|------------|--------|
| 4.1.1 | `0x39` Sidetone | `0x00` (off) | Send, listen for `0x39` echo event | `0x20`[18] = `0x00` | ⬜ |
| 4.1.2 | `0x39` Sidetone | `0x01` (low) | Send, listen for `0x39` echo event | `0x20`[18] = `0x01` | ⬜ |
| 4.1.3 | `0x39` Sidetone | `0x02` (medium) | Send, listen for `0x39` echo event | `0x20`[18] = `0x02` | ⬜ |
| 4.1.4 | `0x39` Sidetone | `0x03` (high) | Send, listen for `0x39` echo event | `0x20`[18] = `0x03` | ⬜ |
| 4.1.5 | `0x37` Mic volume | `0x01`–`0x0A` | Send each level, listen for `0x37` echo | `0x20`[17] = sent value ✅ |
| 4.1.6 | `0x85` OLED brightness | `0x01`–`0x0A` | Send, check base station display changes | write-only; no `0xB0` readback | ⬜ |
| 4.1.7 | `0x09` Save/persist | — | Send after any successful write; power-cycle headset; re-query to verify setting survived | All changed fields match after reboot | ⬜ |

### 4.2 Display and audio setting writes

| # | Command | Param | What to do | Verify via | Status |
|---|---------|-------|-----------|------------|--------|
| 4.2.1 | `0x83` Dim screen off | `0x00` | Send; confirm OLED dim timer disabled | `0x83` event echo or OLED stays on ✅ |
| 4.2.2 | `0x83` Dim screen 5 min | `0x02` | Send; leave idle 5 min | OLED dims at 5 min ✅ |
| 4.2.3 | `0x89` Home screen detailed | `0x00` | Send; check OLED home screen style | OLED shows detailed view ✅ |
| 4.2.4 | `0x89` Home screen simple | `0x01` | Send; check OLED home screen style | OLED shows simple view ✅ |
| 4.2.5 | `0xBF` Mic LED brightness | `0x01`–`0x0A` | Send each level; confirm LED changes | Visual ✅ |
| 4.2.6 | `0xC1` Auto off off | `0x00` | Send; leave idle | Headset stays on ✅ |
| 4.2.7 | `0xC1` Auto off 5 min | `0x02` | Send; leave idle 5 min | Headset powers off ✅ |
| 4.2.8 | `0x27` Gain high | `0x02` | Send; confirm gain is high | `0x20`[4] = `0x02`; `0x27` event fires with `0x02` ✅ |
| 4.2.9 | `0x27` Gain low | `0x01` | Send; confirm gain is low | `0x20`[4] = `0x01`; `0x27` event fires with `0x01` ✅ |

> **`0x27` write encoding:** `0x01`=low, `0x02`=high — same as event and query encoding.

### 4.3 ANC mode and transparency level writes

Use `python src/probe_write.py --cmd CMD --param PARAM` or the snippet in §4.7.

| # | Command | Param | What to do | Verify via | Status |
|---|---------|-------|-----------|------------|--------|
| 4.3.1 | `0xBD` ANC off | `0x00` | Send; confirm headset OLED shows ANC off | `0xB0`[10] = `0x00` ✅ |
| 4.3.2 | `0xBD` ANC transparency | `0x01` | Send; confirm headset OLED shows Transparency | `0xB0`[10] = `0x01` ✅ |
| 4.3.3 | `0xBD` ANC anc | `0x02` | Send; confirm headset OLED shows ANC | `0xB0`[10] = `0x02` ✅ |
| 4.3.4 | `0xB9` Transparency level 1 | `0x01` | Set ANC=transparency first; send; confirm OLED level changes | Visual / `0xB9` event echo ✅ |
| 4.3.5 | `0xB9` Transparency level 10 | `0x0A` | Same setup; confirm max level | Visual / `0xB9` event echo ✅ |
| 4.3.6 | `0xBD` + `0x09` persist | any | Send ANC mode, send save `0x09`, power-cycle headset, query `0xB0`[10] | Setting survives reboot ✅ |
| 4.3.7 | `0xB9` + `0x09` persist | any | Send transparency level, save, power-cycle, confirm OLED shows same level | Setting survives reboot ✅ |

### 4.3 ChatMix / connectivity writes

| # | Command | Param | What to do | Verify via | Status |
|---|---------|-------|-----------|------------|--------|
| 4.3.1 | `0x49` ChatMix enable | `[2]=0x01` | Enable ChatMix; confirm `0x45` events fire when dial moves | `0x45` events appear ✅ |
| 4.3.2 | `0x49` ChatMix disable | `[2]=0x00` | Disable ChatMix; confirm `0x45` events stop | `0x45` events stop ✅ |

### 4.4 Timeout / power writes

| # | Command | Param | What to do | Verify via | Status |
|---|---------|-------|-----------|------------|--------|
| 4.4.1 | `0xA3` Idle timeout | `0x05` (5 min) | Send; let headset idle; confirm it powers off at 5 min | Headset auto-off | ⬜ |
| 4.4.2 | `0xA3` Idle timeout | `0x00` (never) | Send; verify headset no longer auto-off after idle | Headset stays on | ⬜ |

### 4.5 Write packet snippet

```python
import hid, time

VID, PID = 0x1038, 0x12E0
CTRL_USAGE = 0xFFC0
IFACE = 4

dev_info = next(
    d for d in hid.enumerate()
    if d["vendor_id"] == VID and d["product_id"] == PID
    and d["interface_number"] == IFACE and d["usage_page"] == CTRL_USAGE
)

dev = hid.device()
dev.open_path(dev_info["path"])
dev.set_nonblocking(1)

def send(cmd: int, *params: int):
    pkt = bytearray(64)
    pkt[0] = 0x06
    pkt[1] = cmd
    for i, p in enumerate(params):
        pkt[2 + i] = p
    dev.write(list(pkt))
    time.sleep(0.08)
    return dev.read(64, 200)

# Example: set sidetone to high (3), then save
send(0x39, 0x03)
send(0x09)
```

---

## 5. EQ Commands — Write and Query

| # | Command | What to do | Verify via | Status |
|---|---------|-----------|------------|--------|
| 5.1 | `0x32` Query EQ | Send `[0x06, 0x32, profile, 0x00…]` with profile=`0x00` (2.4 GHz) | Response should echo 10 band values | ⬜ |
| 5.2 | `0x32` Query EQ BT | Send with profile=`0x01` (Bluetooth) | Response for BT profile | ⬜ |
| 5.3 | `0x33` Set EQ flat | Send flat bands (`0x14` × 10) for profile=`0x00` | `0x20`[7–16] = `14 14 14 14 14 14 14 14 14 14` | ⬜ |
| 5.4 | `0x33` Set EQ boost bass | Send `0x28` for bands 0–2, `0x14` for rest | `0x20`[7–9] reflect the boost | ⬜ |
| 5.5 | `0x33` Set EQ BT | Same as 5.3 but profile=`0x01` | Separate BT profile persists | ⬜ |
| 5.6 | `0xA6` Query preset name | Send with profile=`0x00` | ASCII preset name returned | ⬜ |
| 5.7 | `0xA7` Set preset name | Send with profile=`0x00` + ASCII string | Query back with `0xA6` to confirm | ⬜ |

---

## 6. Unknown / Candidate Query Commands — Probe for Responses

Send each command byte and observe whether the device responds. Log the raw response.

| # | Command | Origin | Send | Observation needed | Status |
|---|---------|--------|------|--------------------|--------|
| 6.1 | `0xA0` | Nova 7X | `[0x06, 0xA0, 0x00×62]` | No response expected (already confirmed on Nova Pro) | ✅ No response |
| 6.2 | `0x95` | HeadsetControl | `[0x06, 0x95, 0x00×62]` | Returns OLED control to GG — now confirmed, see §10 | ✅ |
| 6.3 | `0x93` | HeadsetControl | feature report, 1024 bytes | Draws bitmap frame — now confirmed, see §10 | ✅ |
| 6.4 | `0xB2` | Adjacent to `0xB0` | `[0x06, 0xB2, 0x00×62]` | Response? | ⬜ |
| 6.5 | `0x22` | Adjacent to `0x20` | `[0x06, 0x22, 0x00×62]` | Response? | ⬜ |
| 6.6 | `0x30` | Adjacent to `0x32` | `[0x06, 0x30, 0x00×62]` | Response? | ⬜ |
| 6.7 | `0xBE` | Adjacent to `0xBD`/`0xBF` | `[0x06, 0xBE, 0x00×62]` | Response? | ⬜ |
| 6.8 | `0xC0` | Adjacent to `0xC1` | `[0x06, 0xC0, 0x00×62]` | Response? | ⬜ |

---

## 10. OLED Draw Commands (`0x93` / `0x95`) — Phase 3

Protocol confirmed via [ggoled](https://github.com/JerwuQu/ggoled) source.  
Tests require `pip install 'arctis-hid[oled]'` (adds Pillow).  
Run with `python package/examples/oled_demo.py <subcommand>` or via Python code.

### 10.1 Brightness (interrupt write, no Pillow needed)

| # | Test | Command | Expected | Status |
|---|------|---------|----------|--------|
| 10.1.1 | Set brightness 1 | `h.set_oled_brightness(1)` | OLED visibly dim | ⬜ |
| 10.1.2 | Set brightness 10 | `h.set_oled_brightness(10)` | OLED visibly bright | ⬜ |
| 10.1.3 | Out-of-range (0) | `h.set_oled_brightness(0)` | Device ignores or clamps | ⬜ |

### 10.2 Release control (`0x95`)

| # | Test | Command | Expected | Status |
|---|------|---------|----------|--------|
| 10.2.1 | Release after custom draw | `h.oled.release()` | GG home screen returns | ⬜ |
| 10.2.2 | Context-manager auto-release | `with h.oled: ...` | Screen returns on `__exit__` | ⬜ |

### 10.3 Static image draw (`0x93`)

| # | Test | Command | Expected | Status |
|---|------|---------|----------|--------|
| 10.3.1 | Clear (all-black frame) | `h.oled.clear()` | Screen goes blank | ⬜ |
| 10.3.2 | All-white frame | `h.oled.draw_raw(b'\xff' * 1024)` | Screen fully lit | ⬜ |
| 10.3.3 | Draw PNG | `h.oled.draw_image("test.png")` | Image visible on screen | ⬜ |
| 10.3.4 | Draw JPEG | `h.oled.draw_image("test.jpg")` | Image visible on screen | ⬜ |
| 10.3.5 | Custom threshold | `h.oled.draw_image("grey.png", threshold=64)` | More pixels lit vs default 128 | ⬜ |
| 10.3.6 | Oversized image | Image larger than 128×64 | Resized to fit, no crash | ⬜ |
| 10.3.7 | Undersized image | Image smaller than 128×64 | Scaled up to fit, no distortion | ⬜ |

### 10.4 Text rendering

| # | Test | Command | Expected | Status |
|---|------|---------|----------|--------|
| 10.4.1 | Default font | `h.oled.draw_text("Hello")` | Readable text on screen | ⬜ |
| 10.4.2 | Custom position | `h.oled.draw_text("Hi", x=10, y=20)` | Text offset correctly | ⬜ |
| 10.4.3 | Inverted | `h.oled.draw_text("Hi", invert=True)` | White background, black text | ⬜ |
| 10.4.4 | Custom TTF font | `font = ImageFont.truetype("myfont.ttf", 20); h.oled.draw_text("Hi", font=font)` | Custom font renders | ⬜ |
| 10.4.5 | Text overflow | Very long string | No crash; text clipped at screen edge | ⬜ |

### 10.5 Scroll text

| # | Test | Command | Expected | Status |
|---|------|---------|----------|--------|
| 10.5.1 | Scroll short text | `h.oled.scroll_text("Hello")` | Text enters right, exits left | ⬜ |
| 10.5.2 | Scroll long text | `h.oled.scroll_text("The quick brown fox")` | Full text scrolls across | ⬜ |
| 10.5.3 | Custom FPS | `h.oled.scroll_text("Hi", fps=5)` | Visibly slower scroll | ⬜ |

### 10.6 Animation (frame sequence)

| # | Test | Command | Expected | Status |
|---|------|---------|----------|--------|
| 10.6.1 | Two-frame flip | `h.oled.play_animation([img1, img2], fps=2, loops=5)` | Alternates 5×, then stops | ⬜ |
| 10.6.2 | File paths as frames | `h.oled.play_animation(["f1.png","f2.png"], fps=10)` | Same as above, loaded from disk | ⬜ |
| 10.6.3 | Infinite loop | `h.oled.play_animation([img1, img2], fps=10, loops=0)` | Runs until Ctrl-C | ⬜ |

### 10.7 GIF playback

| # | Test | Command | Expected | Status |
|---|------|---------|----------|--------|
| 10.7.1 | Single-frame GIF | `h.oled.play_gif("single.gif")` | Static frame appears | ⬜ |
| 10.7.2 | Animated GIF (embedded delays) | `h.oled.play_gif("anim.gif")` | Plays at GIF's own delays | ⬜ |
| 10.7.3 | Override FPS | `h.oled.play_gif("anim.gif", fps=15)` | Plays faster than embedded delays | ⬜ |
| 10.7.4 | Loop count | `h.oled.play_gif("anim.gif", loops=3)` | Plays exactly 3 times | ⬜ |
| 10.7.5 | Infinite GIF loop | `h.oled.play_gif("anim.gif", loops=0)` | Loops until Ctrl-C | ⬜ |

### 10.8 Bitmap encoding correctness

| # | Test | Method | Expected | Status |
|---|------|--------|----------|--------|
| 10.8.1 | White pixel at (0,0) | `encode_frame(white_img)[0] & 0x01` | Bit 0 set = `True` | ⬜ |
| 10.8.2 | White pixel at (0,7) | `encode_frame(white_img)[0] & 0x80` | Bit 7 set = `True` | ⬜ |
| 10.8.3 | White pixel at (1,0) | `encode_frame(white_img)[8] & 0x01` | Bit 0 of byte 8 set | ⬜ |
| 10.8.4 | Full white frame | `all(b == 0xFF for b in encode_frame(white_img))` | `True` | ✅ |
| 10.8.5 | Full black frame | `all(b == 0x00 for b in encode_frame(black_img))` | `True` | ✅ |

---

## 7. Unresolved Fields — Targeted Experiments

| # | Unknown | Experiment | Hypothesis | Status |
|---|---------|-----------|------------|--------|
| 7.1 | `0xB0`[11] = Mic LED brightness | Change Mic LED brightness, re-query `0xB0` | Confirmed: `0xB0`[11] is Mic LED brightness (1–10) ✅ |
| 7.2 | `0xB0`[12] = `0x05`/`0x06` seen | Note exact headset battery %, re-query across multiple charge levels | Possible: state tied to charge tier, not setting | ⬜ |
| 7.3 | `0x20`[2] = constant `0x01` | Try every write command, re-query `0x20` | Does [2] ever change? If not, likely a fixed protocol version byte | ⬜ |
| 7.4 | Transparent level | `0xB9` write confirmed — same byte as the incoming event | `0xBD` sets mode, `0xB9` sets level (1–10, transparency mode only) | ✅ |
| 7.5 | USB input select | Cycle USB input on base station, watch for any event | Confirm command byte and encoding | ⬜ |
| 7.6 | `0x10` unsolicited on `0xFFC0` | Power-cycle headset wirelessly, watch for unrequested firmware packet on CTRL handle | Confirm it fires on reconnect | ⬜ |

---

## 8. Persistence Tests — Power Cycle

After confirming each write command works, verify the setting survives a full power cycle:

| # | Setting | Steps | Expected | Status |
|---|---------|-------|----------|--------|
| 8.1 | Sidetone | Set via `0x39`, send `0x09`, power off headset, power on, query `0x20`[18] | Sidetone level persists | ⬜ |
| 8.2 | Mic volume | Set via `0x37`, send `0x09`, power cycle, query `0x20`[17] | Mic volume persists ✅ |
| 8.3 | EQ | Set via `0x33`, send `0x09`, power cycle, query `0x20`[7–16] | EQ bands persist | ⬜ |
| 8.4 | Without `0x09` | Set sidetone, do NOT send `0x09`, power cycle | Setting reverts to previous value | ⬜ |

---

## 11. Factory Reset — `0xFD`

> ⚠ **DESTRUCTIVE — irreversible.** All user settings are wiped; device reboots. Run this test only on a headset that can be reconfigured afterwards.

Use `python src/scripts/test_cli.py --command factory-reset` (requires `--confirm` flag or interactive confirmation).

| # | Test | Command | Expected | Status |
|---|------|---------|----------|--------|
| 11.1 | Packet encoding | Unit test | `transport.write` called with `[0x06, 0xFD]` and no `0x09` follows | ✅ (unit) |
| 11.2 | Physical factory reset | `h.factory_reset()` on live device | Device disconnects and reboots; all settings return to factory defaults | ⬜ |
| 11.3 | Settings cleared after reset | Re-query `0xB0` after reboot | Battery/ANC/etc. fields show factory defaults | ⬜ |
| 11.4 | No `0x09` sent | Packet trace / unit test | Exactly one write call (`0xFD`); no save packet follows | ✅ (unit) |

---

## 9. Edge Cases

| # | Test | Expected | Status |
|---|------|----------|--------|
| 9.1 | Query `0xB0` / `0x20` with headset off (not connected) | Either no response or zeroed battery fields | ⬜ |
| 9.2 | Send write command while headset is off | Device should NAK or ignore; no crash | ⬜ |
| 9.3 | Rapid writes (no delay between packets) | Device handles without lock-up | ⬜ |
| 9.4 | `0x39` sidetone out of range (`0x04`) | Device ignores or clamps; no error state | ⬜ |
| 9.5 | `0x37` mic volume = `0x00` (below min) | Device ignores or clamps to 1 | ⬜ |
| 9.6 | `0x37` mic volume = `0x0B` (above max) | Device ignores or clamps to 10 | ⬜ |
| 9.7 | `0x25` event at 0% volume (check raw = `0x38`) | `Volume → 0% (raw=0x38)` exactly | ⬜ |
| 9.8 | `0x25` event at 100% volume (check raw = `0x00`) | `Volume → 100% (raw=0x00)` exactly | ⬜ |
| 9.9 | Both handles open simultaneously | No resource conflict; events and queries both arrive | ⬜ |
| 9.10 | Disconnect / reconnect USB mid-session | Script recovers or exits cleanly without traceback | ⬜ |
