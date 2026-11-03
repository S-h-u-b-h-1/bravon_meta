# v0.1 local demo: 90 seconds

**Open** localhost:8000. Point at green topology and 5/5 probes. Say: *This is a simulated disposable environment — not live infrastructure.*

**Inject:** Click `DNS record drift`. Highlight the failed DNS and end-to-end checks, while proxy/backend checks remain green. Explain fault localization.

**Diagnose:** Click `Analyze`. Highlight the cited failure and allowlisted `restore_dns` plan. If Meta is not connected, explicitly call this the **deterministic evidence engine**, not an AI diagnosis.

**Verify:** Click `Verify`. The UI shows `5/5` on a cloned state while the live environment remains broken. Explain the distinction between *proposal* and *verified proposal*.

**Approve:** Click `Approve & repair`, confirm, and show green checks and the recorded recovery. Explain the explicit approval and stale-state prevention.

**Repeat:** Show `Gateway misroute` and `Primary backend crash` briefly. Explain that the latter switches traffic to standby; it doesn't claim to restart the failed process.

**Caveat:** This verifies the workflow mechanics; replace simulated probes with real Docker DNS/HTTP/Nginx checks before competing.
