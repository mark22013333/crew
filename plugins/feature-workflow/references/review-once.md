# Review Once — Proposal / Approval Contract (v1)

> **Scope:** This document defines the deterministic, read-only review packet. The packet by itself does **not** authorize execution or skip human gates; authorization comes only from a bound grant (see step 6). The existing Interactive workflow is unchanged.

## Goal

Prepare one reviewable snapshot of Spec + DB + Architecture before any formal CREW state transition. The Human reads the **actual proposal** (not just a hash) and may request changes. On change, create a new packet with a new digest. Only a trusted Host-mediated explicit approval event could authorize its application.

## Packet lifecycle

1. Use `delegate_readonly` for discovery of spec / db / arch draft (no writes to application, plan.md, state.json, Git or Notion).
2. Compose a JSON draft with the exact fields of `review_once_packet.py`. Require `feature`, `review_once`, `14400` seconds, complete 40-char base commit SHA, exact per-stage decisions and AC lines, an explicit file scope, and test policy `with_test` or `bdd`.
3. Save draft under gitignored `.spec/.drafts/{proposal_id}/draft.json`; run `review_once_packet.py prepare --draft ... --output .spec/.drafts/{proposal_id}/packet.json`. It fails rather than overwriting an existing packet.
4. Show the user the complete Goal, Scope, AC/Sxx, SQL/design changes, Architecture, affected paths, denied operations, test policy and `packet_sha256`. The digest is an integrity / identity marker; **it is not an approval**.
5. If user requests changes, regenerate the draft and create a new packet. Discard prior approval assumptions and do not reuse the previous hash.
6. Explicit Human approval must be bound to this exact packet before any gate may be auto-applied. Two proof kinds exist (`autonomy.proof`):
   - `dialogue`（`/plan-run` 模式 2，同 session）：使用者在主對話對整份 packet 明確選「核准並連跑」，`crew-state.py grant --slug {slug} --action issue --proof dialogue --packet <packet.json> --approved-sha <sha> --max-duration <秒> --until build|arch --project .` 綁定。
   - `signed`（`/plan-run` 模式 3，trusted-host）：工作區外 Host 簽章事件經 `review-once-proof.py` 驗證後綁定。
   Neither proof available → fail closed to Interactive.

## 誠實定位（與 `skills/plan-run/SKILL.md`、`review-once-grants.md` dialogue 節一致）

- dialogue grant 的 packet hash 只保證「**套用的＝審過的**」；信任等級等同 Interactive 的 `gate --by human`，**不是不可偽造的核准**。
- 同 session 模式**不是無人值守**：迴圈在目前對話裡同步執行，session 結束即 paused，`/plan-run resume` 續跑。
- Review Once 僅適用 **feature-workflow 的 Feature 任務**。bug-workflow 共用的 `crew-state.py` 與 `host-capabilities.md` 雖然帶有同文的 Review Once 段（共用檔逐字同步屬設計），但 `crew-state.py grant` 對非 Feature 任務一律拒絕（「Review Once v1 僅支援 Feature」），Bug 流程不會進入此路徑。

## Semantic boundaries

- `spec.decisions[0]` must start with `- D-1 [spec]` (CREW's D-1 contract).
- `spec.ac` is <=15 single-line `- [ ] AC-n ...` entries; Sxx examples remain inline.
- `db.required=false` forbids deploy.sql and DB decisions.
- `architecture.decisions` are distinct `[arch]` entries.
- `scope.allowed_paths` is a *proposed* limit, not a filesystem sandbox; enforcement belongs to Host and the future Runner. No git push/merge, production deploy, production SQL, secrets, permission change, or automatic UAT.
- `stage_sha256` and `packet_sha256` use UTF-8 canonical JSON: sorted keys, no extra whitespace, no NaN.
- Packet creation is not a claim of an active background process. The time limit never starts at packet preparation: `dialogue` starts at `grant issue`（plan-start 之後，上限為所選 4h／2h／1h）；`signed` starts at the Host-signed event's `issued_at`（≤4h）.
- Existing `crew-state.py next`, `work_unit`, Approval Gates, BDD and Human UAT contracts remain intact.
