# UAT Document — Plotter Signature

| | |
|---|---|
| **Version** | 1.4 |
| **Date** | 2026-06-03 |
| **Product** | plotter-signature |

---

## Purpose

Confirm plotter-signature features work before the client accepts delivery of the software and plotter.

**Client (user):** ____________________  
**Date tested:** ____________________

---

## Features

| Check | Feature | Description |
|-------|---------|-------------|
| ☐ | **Flask Server** | Web service starts with API key and serves the plotter-signature app. |
| ☐ | **CMD APIs** | Print, bulk print, void, bulk stop, health, and status (`/api/cmd/*`) work as documented. |
| ☐ | **Config APIs** | Oneshot capture, UI profile, pen change, pen distance, serial connect, and related routes (`/api/config/*`) work as documented. |
| ☐ | **Technical APIs Reference (docx)** | API reference document is complete, accurate, and matches the live endpoints. |
| ☐ | **Pen Kiosk** | Fullscreen app shows status and supports pen down/up and distance reset. |

---

## Result

| ☐ | Pass |
| ☐ | Fail |

**Notes:**

---

## Sign-off

The **developer** delivers the system; the **client** tests it on the received plotter and signs to accept or reject.

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Developer | | | |
| Client (user) | | | |
