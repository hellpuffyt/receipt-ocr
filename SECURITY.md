# Security policy

## Supported versions

Only the latest commit on `main` receives fixes. There are no maintained release branches.

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub's advisory form:
https://github.com/hellpuffyt/receipt-ocr/security/advisories/new

Do not open a public issue for a suspected vulnerability. Include the version or commit,
a minimal reproduction, and the impact you observed. You should receive an acknowledgement
within a few days; fixes are released as soon as they are verified.

## Scope

receipt-ocr reads local OCR JSON files or (optionally) images via the system Tesseract binary, and prints JSON. It makes no network calls. Relevant reports include: crafted input that executes code or writes files, or a parsing error that produces a wrong amount with high confidence.
