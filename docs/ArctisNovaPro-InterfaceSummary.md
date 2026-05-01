# Arctis Nova Pro — Interface Summary

| IF | UsagePage | Usage | Path |
|---|---|---|---|
| 3 | 0x000C | 0x0001 | `\\?\HID#VID_1038&PID_12E0&MI_03#8&f3afa48&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}` |
| 4 | 0xFF00 | 0x0001 | `\\?\HID#VID_1038&PID_12E0&MI_04&Col02#8&26fe868d&0&0001#{4d1e55b2-f16f-11cf-88cb-001111000030}` ← **COMMAND INTERFACE** |
| 4 | 0xFFC0 | 0x0001 | `\\?\HID#VID_1038&PID_12E0&MI_04&Col01#8&26fe868d&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}` ← **COMMAND INTERFACE** |

## Interface 4 Paths for HID Reads/Writes

```
\\?\HID#VID_1038&PID_12E0&MI_04&Col02#8&26fe868d&0&0001#{4d1e55b2-f16f-11cf-88cb-001111000030}
\\?\HID#VID_1038&PID_12E0&MI_04&Col01#8&26fe868d&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}
```