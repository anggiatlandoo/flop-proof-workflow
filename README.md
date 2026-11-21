# Flop Proof Workflow

A GitHub Actions workflow that automatically creates a Flop Labs
proof-of-contribution record (`flop-proofs/*.json` + `.md`) on every push
to the default branch and on every published release. It uses the scripts
from the **Flop Contribution Proof Generator** skill
(`scripts/generate_contribution_record.py` and
`scripts/verify_contribution.py`).

## Setup

1. This repo already contains the workflow (`.github/workflows/`) and the
   skill's `scripts/` folder — there is nothing to copy.
2. Create a secret named **FLOP_DID**:
   - Open the repository on GitHub → **Settings** → **Secrets and
     variables** → **Actions** → **New repository secret**.
   - Name: `FLOP_DID`
   - Value: your public Technocore DID, for example `did:key:z6Mk...`
   - The DID is public by design (it is not a private key), but it is
     stored as a secret so it is not written in the workflow file.
3. Allow the workflow to push: **Settings** → **Actions** → **General** →
   **Workflow permissions** → select **Read and write permissions**.
   (The workflow also requests `permissions: contents: write`.)
4. Push to `main` or publish a release — the workflow generates the
   record, verifies it, and commits the result to the `flop-proofs/`
   folder on the default branch with a `[skip ci]` message.

## What it produces

- `flop-proofs/proof-<tag>.json` + `.md` for releases.
- `flop-proofs/proof-main-<sha>.json` + `.md` for pushes to main.
- Every record is verified first with `verify_contribution.py --json`;
  if it is INVALID, the workflow fails and nothing is committed.
- A summary of the proof is shown in the Actions log and on the run
  summary page. Note: GitHub automatically masks secret values in logs,
  so the DID appears as `***` in the log — the real value is still in
  the committed file.

## Troubleshooting

- `FLOP_DID secret is not set` — create the secret as described in
  step 2 above.
- `git push` rejected (403) — check the Workflow permissions (step 3),
  and make sure the default branch is not protected by a rule that
  forbids direct pushes (branch protection requiring pull requests will
  block the bot's push).
- `INVALID` at the verify step — read the reason in the log; usually
  the URL or description failed a guardrail (see the skill's SKILL.md).

## License

MIT — see the `LICENSE` file.
