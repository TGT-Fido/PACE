# Connecting update hosting later

PACE consumes a plain HTTPS JSON manifest. GitHub Releases is the proposed distribution location; nothing has been published or connected by this build.

Example manifest (replace the example URL and checksum with real release values):

```json
{
  "format": "PACE-update-1",
  "version": "7.1.0",
  "url": "https://YOUR-HOST/PACE_App_7.1.0.zip",
  "sha256": "SHA256_OF_THE_EXACT_ZIP_64_HEX_CHARACTERS",
  "notes": "Describe the changes and required manual checks."
}
```

The update ZIP must contain only app/... files. It must include app/server.py and app/VERSION, whose contents match the manifest version. Each release should ship its new notes in app/release-notes. No real data or project PDFs belong in release packages. Use docs/tools/build_update.py to produce the app-only ZIP and a manifest after editing its version and URL arguments.

Publish the ZIP and latest.json to a trusted location. Paste the stable HTTPS URL of latest.json into Backup & updates. PACE will follow HTTPS download redirects. URLs requiring interactive sign-in are not supported. A public source must contain only sanitized software artifacts. Hosting/account creation and publication were not performed.

The checksum detects corruption or mismatched packages. It is not a developer signature: anyone controlling the configured manifest source can publish executable updates. Use only a source you control/trust. Signed releases are a possible future improvement.

Before enabling updates on the working installation, use an isolated test copy and a test release to exercise the full hosted download, Windows shutdown/restart, healthy startup and intentional failed-startup rollback flow. The worker retains result.txt and previous app/data snapshots in the chosen external backup location. No automatic background installs occur.
