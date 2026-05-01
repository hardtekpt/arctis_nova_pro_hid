# Arctis Nova Pro - HID

This is an API that fully exposes the HID capabilities of the Arctis Nova Pro Wireless Headset

## Technologies

- Python3 
- Fast and light backend API package (nothing fancy)
- Simple CLI for testing/querying the API

## References

Analyze these refrences in detail and understand how applicable and useful they can be here:

- **Headset User Manual**: https://downloads.steelseriescdn.com/guides/arctis_nova_pro_wl_x_pig_cs_cz.pdf
- **Arctis Nova 7X HID Protocol**: https://github.com/cheahkhing/arctis-headset-hid/blob/main/docs/PROTOCOL.md
- **HeadsetControl repo**: https://github.com/Sapd/HeadsetControl

## Plan

Use an incremental approach. Start with a minimal example and implement features step by step. I want to follow allong and understand the development.

Before creating the API you need to first discover the HID command mapping. So start by checking which commands, actions, features, etc are available on the HID read and write commnucation and create a step by step plan to discover the HID commands and necessary information for full control of the headset. You can create helper scripts to help me find the mapping.

### PHASE 1 - Discovering the HID commands

- The first step is to identify the usb interfaces related top the headset and understand what are the available options and interfaces.
- List all the available read and write HID commands. Look for:
    - Headset Volume
    - Chat Mix
    - Mic Mute
    - ANC/Transparency
    - Mic Volume
    - Sidetone
    - OLED Brightness
    - USB Input
    - Gain
    - Transparent Level
    - Wireless Mode
    - Headset and charging batteries
    - Connectivity
- Look for query commands as well and other control commands
- Start by just listening and decoding the received commands
- Create a helper script to record and log the HID commands when the user triggers the commands by interacting with the headset

