# valid_training_data — JacLLM v1.3

Built by `scripts/gen/build_valid_training_data.py` (seed 3407, tokenizer ornith-ai/Ornith-1.5-9B).
Plan: JacLLM v1.3 Dataset & Training Plan (Claude Docs). Tokens: CPT = text; SFT = full chat template.

| dataset | rows | train | valid | tokens | avg | median | p95 | max | rejected | spot-check |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `cpt/composer-fn` | 14,220 | 14,220 | 0 | 1,926,127 | 135 | 111 | 295 | 1138 | 924 | 10/10 |
| `cpt/farm` | 1,558 | 1,558 | 0 | 1,054,701 | 677 | 462 | 2056 | 5485 | 173 | 10/10 |
| `cpt/jachacks` | 1,776 | 1,776 | 0 | 3,167,720 | 1784 | 723 | 6666 | 53615 | 44 | 3/10 ⚠ |
| `cpt/js2jac` | 2,620 | 2,620 | 0 | 827,482 | 316 | 214 | 918 | 4294 | 2,575 | 10/10 |
| `cpt/osp` | 2,454 | 2,454 | 0 | 2,785,401 | 1135 | 675 | 2945 | 4931 | 150 | 10/10 |
| `cpt/osp-compile-only` | 5,157 | 5,157 | 0 | 9,882,249 | 1916 | 2064 | 3362 | 6618 | 81 | 8/10 ⚠ |
| `sft/code_completion/composer-fn` | 11,478 | 11,478 | 0 | 2,637,773 | 230 | 197 | 447 | 1644 | 3,666 | 10/10 |
| `sft/code_fix/osp-repair` | 795 | 795 | 0 | 1,713,511 | 2155 | 2203 | 3936 | 4088 | 209 | 10/10 |
| `sft/farm/farm` | 1,557 | 1,557 | 0 | 1,125,594 | 723 | 512 | 2102 | 3241 | 174 | 10/10 |
| `sft/js2jac/js2jac` | 2,627 | 2,627 | 0 | 1,924,836 | 733 | 522 | 2117 | 4023 | 2,568 | 10/10 |
| `sft/osp/osp-merged` | 1,933 | 1,933 | 0 | 2,145,782 | 1110 | 538 | 2908 | 4051 | 263 | 10/10 |
| `sft/py2osp/osp-lift-gold` | 325 | 325 | 0 | 569,317 | 1752 | 1527 | 3190 | 4069 | 218 | 10/10 |
| `sft/test_gen/osp-repair` | 1,436 | 1,436 | 0 | 2,754,393 | 1918 | 1759 | 3236 | 4095 | 13 | 10/10 |

CPT total tokens: 19,643,680  ·  SFT total tokens: 12,871,206

## Reject reasons

- `cpt/composer-fn`: eval_denylist 762, audit_fail 157, duplicate 5
- `cpt/farm`: duplicate 165, audit_fail 8
- `cpt/jachacks`: duplicate 44
- `cpt/js2jac`: status_in=reject 2,186, hollow 340, duplicate 38, audit_fail 6, status_in=None 5
- `cpt/osp`: duplicate 132, osp_holdout 18
- `cpt/osp-compile-only`: osp_holdout 32, duplicate 25, v21_candidate 24
- `sft/code_completion/composer-fn`: weak_tail_cpt_only 2,733, eval_denylist 762, audit_fail 157, no_def 10, duplicate 4
- `sft/code_fix/osp-repair`: too_long>4096 157, empty 27, duplicate 25
- `sft/farm/farm`: duplicate 165, audit_fail 8, too_long>4096 1
- `sft/js2jac/js2jac`: status_in=reject 2,186, hollow 340, duplicate 21, too_long>4096 10, audit_fail 6, status_in=None 5
- `sft/osp/osp-merged`: guard_fail 113, duplicate_of=osp_B_22__mm3_v10 40, duplicate_of=osp_B_22 20, osp_holdout 18, duplicate_of=osp_A_01__composer_v31 10, duplicate_of=osp_A_08__composer_v1 8, duplicate_of=osp_A_08__composer_v33 8, duplicate_of=osp_B_22__mm3_v42 6, duplicate_of=osp_A_01__mm3_v9 5, duplicate_of=osp_A_01__composer_v27 4, duplicate_of=osp_A_01__composer_v2 4, duplicate_of=osp_A_01__composer_v3 4, duplicate_of=osp_A_08__composer_v6 3, duplicate_of=osp_A_08__composer_v38 3, too_long>4096 3, duplicate_of=osp_A_01__mm3_v2 2, duplicate_of=osp_A_08__composer_v54 2, duplicate_of=osp_A_12__composer_v1 2, duplicate_of=osp_A_12__composer_v40 2, duplicate_of=osp_A_01__composer_v44 1, duplicate_of=osp_B_22__mm3_v21 1, duplicate_of=osp_A_04__composer_v5 1, duplicate_of=osp_A_08__composer_v32 1, duplicate_of=osp_A_12__composer_v35 1, duplicate_of=osp_A_12__composer_v14 1
- `sft/py2osp/osp-lift-gold`: no_input_source 194, guard_fail 22, too_long>4096 2
- `sft/test_gen/osp-repair`: too_long>4096 13
