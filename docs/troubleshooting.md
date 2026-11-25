# Troubleshooting

- **503 from station endpoints**. Use `multipart/form-data` and submit a smartphone image instead.
- **HOLD or recapture requested**. Follow the returned view and lighting instructions. Capture the whole sample against a uniform matte background and check focus and exposure.
- **422 on upload**. Verify the selected leather profile, required metadata, MIME type, decode integrity and supported dimensions.
- **401 on LAN**. Check that both processes have the same environment token.
- **Arduino CLI or serial device missing**. Check the environment report and identify the hardware before provisioning the board toolchain.

- **Directional image rejected with 409**. Use the view and lighting in the pending action for that inspection. Reuploading identical original bytes is rejected.
- **Cross-light registration unverified**. Keep the phone and item fixed, restore the requested framing and remove background clutter. Upload a fresh directional capture while the job still has attempts available. Review the originals when the budget is exhausted.
- **COM5 visible but indicator unavailable**. USB detection confirms the bridge. The indicator also needs the approved status firmware and a versioned acknowledgment. Close exclusive serial monitors before use. To enter the bootloader manually when needed, hold BOOT, tap EN or RESET, then release BOOT.
- **Mask or overlay returns 404**. The capture may predate mask storage or have failed foreground segmentation. The original image remains available if its evidence record exists.
- **Phone or Laptop 2 cannot connect**. Confirm the current Laptop 1 address and the selected transport. The default loopback binding is only reachable by the laptop itself or through a configured Android USB tunnel. LAN use requires the approved network configuration and matching trusted HTTPS for live camera capture.
