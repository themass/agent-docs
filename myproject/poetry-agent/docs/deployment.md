# Deployment

## Local

`make content-up` (the `content-agent` project) starts only the BFF and Domain MCP. This default is intentional: it validates the service boundary without silently provisioning a duplicate database or an unconfigured LLM runtime. Enable DeerFlow only after configuring model/auth secrets. The reviewed static `poetry-editor-lead` package is mounted read-only at DeerFlow's runtime agent path; all dynamic user-defined agents stay disabled for this profile:


```bash
./scripts/content-agent/up.sh --profile deerflow
```

## Staging

1. Build immutable images with `scripts/deploy/build-images.sh <git-sha>`.
2. Inject secrets through the deployment platform; never commit a `.env` file.
3. Run `make content-profile-check` and Java-side domain contract checks.
4. Apply `content-agent/deploy/k8s/staging.yaml` with the immutable image tag.
5. Validate `/health/ready`, MCP initialization, and one non-mutating `get_integrity_gap_report` call.

## Production topology

- BFF: horizontally scalable; use an external operational-event store before scale-out.
- DeerFlow Gateway/Worker: independently scalable; Redis/checkpointer supplied by managed infrastructure.
- MCP: internal-only network service; no public ingress.
- Java Poetry API: independent authoritative service; retains content audit and state machines.
- MySQL: remains private to Java Poetry API; the Agent platform gets no DB credentials.
- Bundle/CDN: separate release pipeline; no Agent service has CDN-write credentials.

## Rollback

App rollback moves BFF/MCP image tags only. It cannot roll back facts, DRAFT applications, published Bundles or migrations. Those use their owning service's explicit audited rollback procedure.

## DeerFlow 2.2.0 deployment prerequisite

Run `make deerflow-bootstrap` once in the checked-out platform root before enabling the `deerflow`
Compose profile. It obtains the official `v2.2.0` release at the provenance recorded in
`content-agent/deploy/upstream/deerflow.lock`. Then inject actual model/provider configuration and the deployment secrets;
do not enable the profile with placeholder credentials.
