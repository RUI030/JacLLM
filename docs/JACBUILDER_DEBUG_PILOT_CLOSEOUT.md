# JacBuilder debug pilot closeout

Date: 2026-10-30. Work closed within the user's five-minute limit. This closes the current data review and training preflight; the broader dataset and model-improvement objectives remain unfinished.

## Delivered

- Local dataset: `dataset/sft/jacbuilder/debug-pilot-v1/`. Two approved minimal import-edit targets in `train.jsonl`; unchanged pending-review originals in `review.jsonl`. Do not train on both files.
- Producer, reviewer and validator: `script/dataset/sft/{jacbuilder,review_jacbuilder,check_jacbuilder}.py`.
- Existing fresh-workspace replay evidence: `agent-review/` inside the dataset. Exact edits passed pinned Jac 0.34.28 compilation, original checks and seven additional integer inputs per edit. Approval covers only the edits, not every Teacher action.
- Actor history remains context-only: only each final approved Teacher edit has loss weight 1. Student failures and other historical assistant messages have weight 0.
- Raw evidence remains separately archived under `/home/ryl/Documents/Jaseci/jacbuilder-experiment-data/`; the local dataset remains gitignored. No production traces or hidden evaluation data were added.

## Final validation

Executed the existing checker again during closeout:

```bash
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TOKENIZERS_PARALLELISM=false \
  /home/ryl/miniforge3/envs/jacllm/bin/python \
  script/dataset/sft/check_jacbuilder.py \
  --dataset dataset/sft/jacbuilder/debug-pilot-v1 \
  --tokenizer output/model/JacLLM-Ornith-9B-prod-img-sft-m7
```

Result: **PASS**, exit 0. The checker verifies Arrow loading, exact request-prefix reconstruction, loss masks, rejection of a 16k truncation limit and approved-row consistency. `closeout-validation.json` preserves the command, stdout, stderr and matching before/after hashes for review/train JSONL and both manifests. Existing `training-collator-preflight.json` records CPU agreement between text and VLM token IDs and labels; it is not a GPU training test.

Three read-only subagent reviews cross-checked documentation, scripts and replay evidence. The final script review identified a missing explicit comparison of approved tool schemas against review sources. The checker now asserts equality. An executed negative control changed one tool description in a disposable copy: the checker rejected it at the new assertion; the untouched dataset passed again. Both commands, outputs and unchanged dataset hashes are preserved in `closeout-schema-validation.json`. All three dataset scripts passed Python syntax compilation. Documentation now explicitly distinguishes CPU preprocessing limits from untested GPU capacity.

## What the token counts mean

| Measure | Current value |
| --- | ---: |
| Approved examples | 2 |
| Distinct task families | 1 |
| Independent validation examples | 0 |
| Rendered input-plus-target tokens | 82,229 |
| Loss-bearing target tokens | 217 |
| Per-example sequence lengths | 41,007 / 41,222 |

The 41k sequences preserve the actual Teacher request, including substantially repeated Student system/skill context inside the handoff snapshot. They do not represent 41k tokens of repair reasoning. `TRAINING_PREFLIGHT.md` contains the measured breakdown. No shortened projection was created, and original records were not destructively deduplicated.

## Remaining work

1. Produce a separately versioned training projection with traceable, deterministic context deduplication; retain unique observations and immutable raw records.
2. Collect independently verified recovery examples across failure families, including path and read-offset errors. Maintain family-disjoint evaluation cases and token-frequency reporting. The requested 500k-token dataset has not been reached; context volume must not be mistaken for approved targets.
3. Run a bounded GPU training smoke test using the current m7 base/template and a weight-aware training path, with a separate output directory. Text `sft.py` with `packing=False` does not honor these message weights. VLM adapter architecture must match subsequent loading. Training memory fit remains untested; do not assume the shared serving allocation is available.
4. Compare the unchanged baseline and trained adapter on disjoint cases before claiming improvement. Two same-family import edits cannot establish general debugging or read-offset improvements.

No FT, paid model calls, dependency upgrades, production auto-intervention, model deployment or dataset upload were initiated during closeout. Existing serving processes were left running. No background job was scheduled to continue this work.

## Subsequent projection experiment

After this closeout, a separate user request produced the local, versioned `debug-pilot-v2-projected` training view. See its `README.md` and `projection_manifest.json`. It reduces 82,229 rendered tokens to 50,437 while retaining all 217 reviewed target token IDs. The original v1 and raw evidence remain unchanged. This addendum records later work; the closeout statements above describe the earlier point in time.
