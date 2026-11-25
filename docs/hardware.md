# Hardware preparation

The brief lists an ESP32 board, 60-LED addressable strip, 12 V white strip, 12 V 2 A adapter, jack, jumper wires and 1 kΩ resistor. The exact board, strip specifications, power capability and polarity are pending physical verification. Serial enumeration detected zero ports.

For identification, provide photos of the ESP32 board and module markings, both strip labels and connector markings, and the adapter output and polarity label. Confirm whether a USB data cable, a regulated strip supply, switching components, a multimeter and sample pieces are available. The ESP32 can be tested independently by USB after positive board identification and approval for any flash.

The manual software mode accepts smartphone photos and records operator-supplied lighting and view metadata. It requires no station electronics.

The prior read-only ROM query verified ESP32-D0WD-V3 revision 3.1 with 4 MB SPI flash. Windows enumerates the signed Silicon Labs CP210x bridge on COM5. The operator's close-up showed the jumper at P23 and the adjacent ground. The exact PCB vendor variant remains unidentified. The bench report says the small LED and independently powered white strip work. The status-indicator firmware is a separate GPIO23 test, and USB detection or successful compilation alone does not verify it.

Keep the white strip electrically separate from the ESP32 and breadboard. For a right-light request, switch off the strip, move it to the requested side, leave the phone and sample fixed, and turn the strip back on. Upload an original photo of the same face and tag `manual_right`. The LED status indicator has no control over the white strip.
