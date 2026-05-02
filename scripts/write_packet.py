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

# Sidetone: Off (0), then save -> working
# send(0x39, 0x00)
# send(0x09)

# Sidetone: low (1), then save -> working
# send(0x39, 0x01)
# send(0x09)

# Sidetone: med (2), then save -> working
# send(0x39, 0x02)
# send(0x09)

# Sidetone: high (3), then save -> working
# send(0x39, 0x03)
# send(0x09)

# Mic Volume: min (1), then save -> working
# send(0x37, 0x01)
# send(0x09)

# Mic Volume: max (10), then save -> working
# send(0x37, 0x0A)
# send(0x09)

# OLED Brightness: 1 (1), then save -> working
# send(0x85, 0x01)
# send(0x09)

# OLED Brightness: 10 (10), then save -> working
# send(0x85, 0x0A)
# send(0x09)

# OLED Brightness: 1 (1), then save -> working
send(0xB2, 0x00)
send(0x09)