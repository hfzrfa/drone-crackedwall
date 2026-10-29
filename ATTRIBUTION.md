# Attribution and distribution provenance

## Developer identity

- Primary mark: **Developed by hfzrfa**
- Evidence-image mark: **by hfzrfa**
- Android About identity: **Developed by Hafiz Rafie Aditya · @hfzrfa**
- Original repository: <https://github.com/hfzrfa/drone-crackedwall>

Runtime source stores these labels as masked byte arrays and reconstructs them only when displayed. This is lightweight obfuscation intended to make a simple string search less useful. It is not encryption, DRM, tamper-proofing, or anti-removal: the decoder and decoding material are distributed with the application, so the labels can be recovered, copied, changed, or removed by anyone who inspects the code carefully. Removing or changing a mark does not disable or damage the application.

The source tree deliberately keeps this document and README attribution in clear text. Existing Git history, licenses, and third-party notices must remain intact.

## Copy fingerprint

`distribution/copy_id.json` contains a random, non-personal package ID. The backend loads it without network access and adds it to detection JSON, health/statistics JSON, and session CSV output. It is generated during package preparation, never at startup, and contains no recipient name or other personal data.

For every separately prepared recipient package, run this once inside that package's staging copy:

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_copy_id.py
```

Record the printed ID with the package archive. Do not rerun the command on every launch. The ID is only a supporting provenance clue: a recipient can copy it to another package or remove it.

## Integrity manifest

First make a sanitized staging directory or final archive containing exactly what will be delivered. Never include `.env`, credentials, private keys, logs, databases, virtual environments, runtime evidence, local videos/datasets, or Android build/local configuration. Then hash the final archive itself:

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_distribution_manifest.py .\distribution\recipient-package.zip --output .\distribution\recipient-package.sha256
```

For a directory delivery, pass the staging directory instead. Directory mode automatically excludes common secrets, `.env`, logs, databases, virtual environments, build output, evidence images, and other changing runtime files:

```powershell
.\.venv\Scripts\python.exe .\scripts\generate_distribution_manifest.py D:\staging\recipient-package --output .\distribution\recipient-package.sha256
```

Archive together in a controlled location:

1. the exact distributed archive or directory snapshot;
2. its `.sha256` manifest;
3. the corresponding `copy_id` and preparation date;
4. the full source commit hash (`git rev-parse HEAD`), branch, and repository URL.

Verify later with `Get-FileHash -Algorithm SHA256` for an archive, or regenerate the directory manifest and compare it byte-for-byte. Matching hashes establish file equality with the archived package, not authorship or ownership by themselves.

No part of this mechanism uses telemetry, hidden access, a remote kill switch, sabotage, or network tracking.
