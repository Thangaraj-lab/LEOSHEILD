# Wiring verification record

Wiring design is blocked pending the exact ESP32 model and pinout, both strip datasheets and load, adapter voltage/current/polarity, and inventory of suitable power and switching components. Verify wiring current ratings and protection before producing the final diagram.

The project brief prohibits connecting a 5 V WS2812B strip to a 12 V adapter or powering a full strip from ESP32 GPIO or laptop USB. Preserve the disconnected state until the plan is verified and the user approves energizing. Verify appropriate supply, level shifting, switching, common ground, power wiring and overcurrent protection for the identified parts.
