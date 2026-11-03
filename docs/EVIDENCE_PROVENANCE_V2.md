# Evidence provenance v2

Bravon accepts runner evidence only when its HMAC authenticates the envelope's
runner ID, key ID, case ID, nonce, issue time, observations, and environment
binding. Evidence expires after five minutes and allows at most 30 seconds of
future clock skew.

Production consumers must use `SQLiteReplayStore` on persistent storage shared
by every verifier process on that host. Its primary-key insert atomically
accepts a runner/case/nonce tuple once and survives restarts. Database errors
fail closed. `MemoryReplayStore` is only for tests and single-process tools.

Runner secrets must contain at least 32 random bytes. Store them outside the
repository, identify each with a unique key ID, rotate by adding the new key,
then remove the old key after the maximum evidence lifetime. Never give signing
keys to the verifier dashboard or untrusted execution jobs.

This proves envelope integrity and signer possession. It does not prove runner
independence, workload isolation, test quality, or truthful measurement. Those
claims require a separately controlled execution worker and infrastructure
attestation.
