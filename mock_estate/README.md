# Mock government estate

A small, deliberately vulnerable stand-in for a government department's IT
estate. It exists so the Phase 2 discovery scanner
(`python -m app.discovery`) has something realistic to inventory: TLS
configs pinned to old protocol versions, service code that calls RSA and MD5,
SSH configs that still accept `ssh-rsa`, a SAML metadata document signed with
`rsa-sha1`, and — as controls — a couple of things that are already
post-quantum ready.

Nothing here is real, nothing here is a secret, and nothing here should be
copied into a real system. The private keys that would accompany the public
material are intentionally absent; the scanner only needs to see the public
side to classify it.

Layout:

| Path | Represents |
|------|------------|
| `land-registry/` | The land-records web service (the Phase 5 demo app's ancestor). Nginx TLS termination + a Python records API. |
| `tax-portal/` | A citizen-facing portal with an SSH bastion and JWT sessions. |
| `records-db/` | The database tier: PostgreSQL TLS settings and a backup job. |
| `legacy-mainframe/` | A batch system whose crypto settings never moved past 2005. |
| `identity-service/` | SAML SSO and the estate's authorised SSH keys. |
| `health-records-api/` | A patient-records API: SHA-1 record IDs, a 2048-bit RSA signing key, RS256 JWTs, TLS 1.1 + RC4 at the edge, MD5 password hashing in the DB. |
| `treasury-gateway/` | A card-payment gateway on the national switch: Triple-DES PIN-block encryption, a 1024-bit RSA settlement key, HMAC-SHA1 message MACs, TLS 1.0 on the ISO 8583 connector. |
