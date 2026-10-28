# Public release checklist — AFFICHO v1.2.0

- [ ] Copy only the final production Python modules into `src/` (`houston_display.py`, `houston_import.py`, `houston_campaign.py`, `houston_audio.py` if present).
- [ ] Verify these files are the *exported production* versions, including the AFFICHO branding and the correct source campaign directory.
- [ ] Review all source code for embedded passwords, tokens, emails, access details and sensitive absolute paths.
- [ ] Do not copy the Raspberry Pi SD card image, OS configuration, private logs, local backups or paid/third-party music.
- [ ] Confirm that `git status` / `git diff --cached --name-only` lists only intended public files.
- [ ] Consider adding a rights-cleared, privacy-reviewed demonstration photo or video later.
- [ ] No LICENSE file is supplied: publishing code publicly does not automatically grant open-source reuse rights.
- [ ] Create the tag `v1.2.0` after the public version is reviewed.
