# PACE 7.0.0 validation

## Baseline

The complete 6.5.0 Workspace Candidate plus the 6.5.1 Dialog and 6.5.2 Contrast fixes. Historical v4 source was consulted solely to recover the exact hexagon logo markup and CSS. No old application baseline replaced newer functionality.

## Completed checks

- 61 Python unit tests passed: original project/PDF selection, metadata, PDF form state, import, search, backup/restore, update staging, maps, settings and ordering; V7 image deduplication/migration, saved appearance, deletion boundaries, first-run behavior and listener switching.
- Python compilation and JavaScript syntax validation passed.
- Chromium 155 browser checks passed at 390x844, 768x1024 and 1440x1000 for Cards, Canvas, Radial Map and Roadmap: no horizontal page overflow or uncaught page errors.
- Light and Dark themes tested against both a bright pastel wallpaper and dark navy wallpaper. Header, counts, headings and footer have solid theme surfaces with opacity 1. Main text contrast: Light #1b2d46 on #ffffff; Dark #e7edf7 on #1a2431. Secondary text uses the existing theme palette.
- Browser flows checked saved Custom appearance, icon selection, root-title persistence across three map types, centered layout selection embedded PDF rendering and form-value persistence after reload, plus card and Reorder deletion. A refresh race found during rapid successive edits was fixed and the deletion flows rechecked.
- HDR failure path verified: a headless browser without a compatible GPU reports Legacy active and keeps the dashboard usable. This is not proof of physical HDR output.
- Four synthetic one-page PDFs with editable note fields created. Sample content contains no personal projects.
- New generated wallpapers: two 1672x941 landscape PNGs and one independently composed 941x1672 portrait PNG. These are native output sizes, not native 4K or upscaled substitutes.

## Required Windows acceptance checks

1. On a clean Windows x64 computer: run Setup without installing Python; open the dashboard, tray settings and PDFs; close/reopen PACE.
2. On a computer with existing Python: repeat, verifying PACE uses its bundled runtime and existing Python/PATH remain unchanged.
3. Exit the older PACE instance before launching V7. Use a copied data folder to verify migration, project files, forms and preferences; retain the original as a backup.
4. Check LAN browsing from phone/iPad with private-network firewall permission. Check Tailscale with connected authorized devices. Switch back to computer-only and verify remote access closes.
5. On HDR hardware: enable Windows HDR, use a compatible browser at localhost, compare Legacy and HDR highlights and verify GPU fallback. Remote HDR is deliberately disabled in V7.
6. Install again into the same folder and confirm existing data is preserved. Delete a sample, restart, and verify it does not return. Uninstall and verify data remains.

Installer compiled on Linux; Windows execution and code signing were not performed. Live tailnet routing, firewall prompts and device-specific graphics cannot be certified from this environment. The package is a V7 test build for these acceptance checks, not a claim that all Windows hardware has been validated.

## V7.1

The existing manifest/checksum updater and rollback mechanism remain present. The release repository and manifest URL have not been configured. A real hosted 7.0.0 to 7.1.0 upgrade and forced-failure rollback must be tested before public update rollout. See UPDATE_HOSTING.md.
