# Change Pen Command

This document captures the observed serial communication for the **Change Pen** action.

## Write Sequence (Host -> Device)

### Packet 1

- **Hex**: `47 31 47 39 30 20 45 37 2E 35 46 35 30 30 30 0A`
- **ASCII**: `G1G90 E7.5F5000\n`
- **Meaning**:
  - `G1` linear move
  - `G90` absolute mode token (as captured in the same line)
  - `E7.5` move E-axis to intermediate pen position (likely pen-change/transition position)
  - `F5000` feedrate

### Packet 2

- **Hex**: `47 39 30 0A 47 31 47 39 30 20 45 30 2E 30 46 35 30 30 30 0A`
- **ASCII**: `G90\nG1G90 E0.0F5000\n`
- **Meaning**:
  - `G90` set absolute positioning mode
  - `G1 ... E0.0 F5000` set E-axis to `0.0` (commonly pen-up / released position)

## Read Sequence (Device -> Host)

### Response 1

- **Hex**: `6F 6B 0A`
- **ASCII**: `ok\n`
- **Meaning**: Command accepted and executed.

### Response 2

- **Hex**: `6F 6B 0A 6F 6B 0A`
- **ASCII**: `ok\nok\n`
- **Meaning**: Two commands acknowledged (matches the second write packet that contains two commands).

## Protocol Notes

- Commands are newline-terminated (`0x0A`).
- Device replies with `ok` per command.
- The observed change-pen behavior appears to be:
  1. Move E-axis to `E7.5` (transition position),
  2. Ensure absolute mode (`G90`),
  3. Move E-axis to `E0.0` (release/up position).
