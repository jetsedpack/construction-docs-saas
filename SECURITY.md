# Security disclosure & data handling

> **Target design vs current implementation (18.11.2026):** the approved product intends to send a *sanitized structured representation* (fields, relationships, layout and vetted metadata) through a future policy gateway. That pathway, alias vault and local rehydration are NOT implemented or cleared for real customer data. Today the code only sends enum issue categories and numeric metrics. See [decision contract](docs/decisions/2026-11-18-product-contract.md) and [draft roundtrip](docs/functional/04-structured-roundtrip-contract.md).

**Status:** prototyping only. NOT approved for real production documents, legal signing, regulated processing, or multi-user installation.

- Do not add genuine CHGES documents, contracts, configuration archives, personal identifiers, private certificates, network credentials or customer records to Git.
- An encrypted local storage prototype is not the same as enterprise-grade security or legal compliance.
- All original documents and extracted data stay on Windows. Offline-first is the default.
- Remote GPUGO calls only send **strictly allowlisted issue category/severity and numerical counters**. Never send arbitrary snippets, CAD, PDF, full text, equipment serials or protected organization/person information.
- The GPUGO Edge code is for **loopback development** only. Do not expose it to the public internet until auth, quotas, ingress, audit, tenant isolation and penetration testing are completed.
- Model responses are untrusted and cannot authorize edits, approval, acceptance, or signatures.
- Protect the device with BitLocker, NTFS permissions, endpoint security and user access control. Use a dedicated incident/backup policy before pilot deployment.
- If you find a vulnerability, disclose it privately to the repository maintainers; do not upload a sample containing customer data.

See [Threat model](docs/implementation/04-security.md) and [GPUgo deployment](docs/implementation/05-gpugo-inference.md).
