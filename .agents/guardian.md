# Guardian Journal

## 2026-08-31 - Bind UI production entry to a fresh main receipt

- A documentation-only planning PR may be accepted without runtime checks when
  its diff, traceability, merge tree, secret scan, and maintainer acceptance are
  explicit; it still does not authorize production edits by itself.
- UX visual work must record one current-main execution receipt and fail closed
  if `origin/main` changes before the first production edit.
- Existing project environments should be reused for reproducibility. An
  undeclared dependency upgrade is not a substitute for a fresh baseline.
