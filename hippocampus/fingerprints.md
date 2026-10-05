---
title: Fingerprints
type: fingerprints
---

# Fingerprints

A SHA-256 hash of every file in `senses/`, recorded when it is encoded, one
line each: `YYYY-MM-DD <sha256> <path>`. Written only by `brain fingerprint`
(which `/ingest` runs); `brain check` fails when an input no longer matches
its hash, with or without git. Append only; never edit a previous line.
