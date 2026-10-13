# Review Once — Proposal / Approval Contract (v1)

> **Status: staged.** This change only implements the deterministic, read-only review packet. It does **not** authorize execution or skip human gates. The existing Interactive workflow is unchanged.

## Goal

Prepare one reviewable snapshot of Spec + DB + Architecture before any formal CREW state transition. The Human reads the **actual proposal** (not just a hash) and may request changes. On change, create a new packet with a new digest. Only a trusted Host-mediated explicit approval event could authorize its application.

## Packet lifecycle

1. Use `delegate_readonly` for discovery of spec / db / arch draft (no writes to application, plan.md, state.json, Git or Notion).
2. Compose a JSON draft with the exact fields of `review_once_packet.py`. Require `feature`, `review_once`, `14400` seconds, complete 40-char base commit SHA, exact per-stage decisions and AC lines, an explicit file scope, and test policy `with_test` or `bdd`.
3. Save draft under gitignored `.spec/.drafts/{proposal_id}/draft.json`; run `review_once_packet.py prepare --draft ... --output .spec/.drafts/{proposal_id}/packet.json`. It fails rather than overwriting an existing packet.
4. Show the user the complete Goal, Scope, AC/Sxx, SQL/design changes, Architecture, affected paths, denied operations, test policy and `packet_sha256`. The digest is an integrity / identity marker; **it is not an approval**.
5. If user requests changes, regenerate the draft and create a new packet. Discard prior approval assumptions and do not reuse the previous hash.
6. PR-B must bind explicit Human approval to this exact packet via a Host-trusted proof before any gate may be auto-applied. **Without such a trust boundary, fail closed to Interactive.**

## Semantic boundaries

- `spec.decisions[0]` must start with `- D-1 [spec]` (CREW's D-1 contract).
- `spec.ac` is <=15 single-line `- [ ] AC-n ...` entries; Sxx examples remain inline.
- `db.required=false` forbids deploy.sql and DB decisions.
- `architecture.decisions` are distinct `[arch]` entries.
- `scope.allowed_paths` is a *proposed* limit, not a filesystem sandbox; enforcement belongs to Host and the future Runner. No git push/merge, production deploy, production SQL, secrets, permission change, or automatic UAT.
- `stage_sha256` and `packet_sha256` use UTF-8 canonical JSON: sorted keys, no extra whitespace, no NaN.
- Packet creation is not a claim of an active background process. Four hours **start only upon trusted Human approval**, not packet preparation.
- Existing `crew-state.py next`, `work_unit`, Approval Gates, BDD and Human UAT contracts remain intact.
