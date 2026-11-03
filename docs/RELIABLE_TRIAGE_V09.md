# Minimum customer-impact evidence before a final decision (v0.9.0 hotfix)

## Observed failure
On the disposable real-Docker DNS incident at controller revision 32, two hosted
Nemotron runs observed the wrong DNS IP and healthy gateway/backends but skipped
`customer_path`. With no `customer-path` evidence, no repair action was eligible
for presentation, so the model chose `final_none`. Both runs were safe but missed
a recoverable fault. These failures must remain visible in evaluation reports.

## Change
The free-model probe-selection protocol withholds *all final decisions*, including
`final_none`, until the read-only `customer_path` observation exists. The model
chooses that tool (it isn't silently injected) and then makes a new decision with
the additional evidence. The rule is independent of synthetic labels and does
not select an action, supply citations, or bypass the independent evidence gate.
If no customer-path probe is available, a safe abstention is still offered.

## Boundaries
- No code in this patch changes Docker mutation, the repair allowlist, sandbox
  verification, approvals, or the evidence gate.
- A final `none` remains possible after customer-path evidence. The model may
  still make a wrong decision; this is a coverage fix, not an accuracy claim.
- Live model results are NOT established by offline tests.
- The CLI progress label still says "synthetic inference" during live disposable
  Docker investigations; that is a separate presentation bug.

## Test and run
```
patch --batch --forward --dry-run -p1 < ~/Downloads/proofops-v0.9.0-minimum-triage-hotfix.patch
patch --batch --forward -p1 < ~/Downloads/proofops-v0.9.0-minimum-triage-hotfix.patch
python -m pytest -q
```

Then, with an active disposable Docker incident and explicit cloud consent:
```
python -u -m proofops.real_lab investigate \
  --investigator openrouter-free \
  --confirm-cloud 'SEND DISPOSABLE LAB PROBE DATA TO OPENROUTER'
```
This makes model requests (up to ten for the configured investigation).
Do not reset or reinject the fault. After the run, inspect its proposed action
and the independent evidence gate; do not claim success from `allowed: true`
on `none`, which is merely a safe abstention.
