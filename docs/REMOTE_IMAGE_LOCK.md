# Remote Docker supply-chain lock

**Scope:** Only Bravon's controlled, disposable Compose lab. This document records
the reviewed external image identities used by the remote-qualification prototype.
It does **not** certify those images as vulnerability-free or safe for production.

## Immutable image references

| Service / build | Source tag | Pinned multi-platform digest |
| --- | --- | --- |
| CoreDNS | `coredns/coredns:1.12.4` | `sha256:986f04c2e15e147d00bdd51e8c51bcef3644b13ff806be7d2ff1b261d6dfbae1` |
| Nginx edge | `nginx:1.30.6-alpine3.24` | `sha256:0e52bd054126cdc040b1276c0af347aeb02a41b9cfe305d6094767ac30e97949` |
| Alpine probe | `alpine:3.22` | `sha256:2e0b81d60597f449baa56dc25d355367869d2dca4cd57e866f1e2b52af3eb55f` |
| Backend Python base | `python:3.12-alpine` | `sha256:b658b05ce9c4eb97ec6fc19424818a1f31993659c2b505a532f470e83807815d` |

These digest values were checked against the relevant image/tag pages at the
time of this change. The Python backend base matches Bravon's previously used
pinned Python image; it intentionally does not switch runtime versions in
this security-only change.

Reference sources:
- CoreDNS Docker Hub: https://hub.docker.com/layers/coredns/coredns/1.12.4/images/sha256-d86c83e95bd44f145f52dc37a1f3bdcb9cb910d76c2653b5910ccbb7b7987d64
- Nginx 1.30.6 Docker Hub index/amd64: https://hub.docker.com/layers/library/nginx/1.30.6-alpine3.24/images/sha256-84ed8c0dd296c188bfc24ed506f46589e9285fb0b11cf3a04d91d524d3067e11
- Alpine Docker Official Image tag metadata: https://github.com/docker-library/repo-info/blob/master/repos/alpine/tag-details.md
- Python Docker Hub: https://hub.docker.com/layers/library/python/3.12.15-alpine/images/sha256-2055081c860db8c842b663415b795b026e7e5cc63b59c5193fcc9997713ea5b8

## Mandatory verification before owner-authorized remote dispatch

1. Confirm each digest resolves for the intended `linux/amd64` GitHub runner
   using `docker manifest inspect` or `docker buildx imagetools inspect`.
2. The previous Nginx 1.28-alpine digest corresponded to a stale image
   with multiple known high/critical vulnerability findings. On October 14,
   2026, the upstream project released **NGINX 1.30.6 stable** with security
   fixes; the new official Docker image is pinned to its **2026-10-30
   `1.30.6-alpine3.24` multi-platform index digest** above.
   Primary references:
   - https://nginx.org/
   - https://hub.docker.com/layers/library/nginx/1.30.6-alpine3.24/images/sha256-84ed8c0dd296c188bfc24ed506f46589e9285fb0b11cf3a04d91d524d3067e11
   The new image is **not vulnerability-free**: current Docker Hub reports
   remaining security findings. Perform a full pinned **linux/amd64 SBOM and
   image vulnerability assessment**, document accepted/resolved findings, and
   execute the five-probe physical requalification before enabling the remote
   workflow. No real image pull/build has been performed in this session.
3. Build the backend image from its pinned base and ensure it runs as the
   declared non-root user.
4. Check that Compose can create the fixed private network, start every
   service, pass the five baseline probes, and tear down both active and
   verification stacks cleanly.
5. Capture the actual successful or failed physical experiment result.
   Mocked or self-digested controller evidence never upgrades into third-party
   attestation simply because the digests are pinned.

The GitHub Actions workflow remains disabled without the owner-set repository
variable, manually confirmed dispatch and matching owner identity. No images were pulled and no physical Docker run was
performed as part of committing these version-lock files.
