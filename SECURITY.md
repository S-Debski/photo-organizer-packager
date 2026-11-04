# Security Policy

## Supported versions

Only the latest release (currently the v3.0 beta) receives fixes.

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through GitHub: on this repository go to
**Security → Report a vulnerability** (private vulnerability reporting).

Include what you found, how to reproduce it, and which version and
platform (Windows / macOS) you were using. You'll get a reply as soon as
practical; this is a personal project maintained in spare time.

## Scope notes

Photo Organizer is a local desktop app:

- Its web interface listens on `127.0.0.1` only (this computer), on ports 5000–5009.
- It reads photos from cards, drives and folders and never writes to the source.
- It writes only to the import destination you choose, the app's own data
  folders (`~/Pictures/PhotoWizard/sessions`, the cache folder) and, if you
  use *Send to phone*, the phone folder `DCIM/PhotoOrganizer`.

Issues of particular interest: any way for a web page or another program to
make the app read, write, open or delete files outside those rules.
