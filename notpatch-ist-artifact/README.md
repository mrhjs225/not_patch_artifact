# NotPatch Replication Package

This package accompanies the article *NotPatch: When "Resolved" Does Not Establish Patch Decidability in Repository-level Program Repair*.
It contains the annotation records, manifests, and deterministic scripts behind every generated table in the article and its supplement.
A single command regenerates these outputs and checks them byte for byte against the archived checksums.

Public repository: https://github.com/mrhjs225/not_patch_artifact (this directory is `notpatch-ist-artifact/` there).
Built from research-repository commit `ee09b13f3998` on 2026-10-27.

## Quick start

Requirements: Python 3.12 or newer. Only the standard library is used, so no installation is needed.
Run the commands from this directory.
Python 3.11 also runs every step, but two weighted-kappa values then differ in the last floating-point digit because Python 3.12 changed float summation, so the byte comparison reports them.

```bash
python3 reproduce.py --check-only   # verify every shipped file against MANIFEST.json
python3 reproduce.py                # unpack inputs, run all analysis steps, verify outputs
```

`reproduce.py` first restores the `.xz`-compressed inputs and the release assets to the paths the scripts expect.
It then runs the steps below in order and compares all 54 outputs with `MANIFEST.json`.
A step whose release asset is absent is skipped and reported; its shipped outputs are still checked.

## Paper-to-artifact map

Table numbers refer to the submitted article and supplement.

| Step | Script | What it computes | Paper location |
| --- | --- | --- | --- |
| `boundary_validation` | `scripts/analyze_repo480_boundary_validation.py` | Independent boundary-validation panel estimate (RQ1) | Article Table 8 (validation rows) and Section 5.1 |
| `prevalence` | `scripts/analyze_repo480_prevalence.py` | Frozen-rule prevalence, reviewer-aggregation and cluster sensitivities (RQ1) | Article Table 8; Supplement Tables 1 and 3 |
| `transition` | `scripts/analyze_repo480_transition.py` | Issue-packet to repository-packet label transition (RQ1) | Section 5.1 text |
| `reporting_diagnostics` | `scripts/analyze_repo480_reporting_diagnostics.py` | Sampling flow and raw-label reliability (RQ1) | Article Tables 4 and 9 |
| `construct_validity` | `scripts/analyze_repo480_construct_validity.py --adjudication-return …/repo480_construct_validity_adjudication.jsonl` | Bidirectional construct-validity audit (RQ1) | Article Table 11; Supplement Table 4 |
| `p1_typology` | `scripts/analyze_repo480_p1_typology.py` | Initial typology of non-strict P1 and boundary-discordant rows (RQ1 threats) | Section 7 (Threats to Validity) text |
| `bv_prior_exposure` | `scripts/analyze_repo480_bv_prior_exposure.py` | Boundary-validation sensitivity to the panel's earlier construct-validity exposure (RQ1 threats) | Section 7 (Threats to Validity) text; Supplement Section 2 |
| `rre_verification` | `scripts/analyze_repo480_rre_verification.py --analyzed-on 2026-10-19` | Independent expert verification of the typology (RQ1 threats) | Section 7 (Threats to Validity) text |
| `rre_adjudication` | `scripts/analyze_repo480_rre_adjudication.py --analyzed-on 2026-10-19` | Final typology after adjudication (RQ1 threats) | Supplement Table 6 |
| `rq2_masking` | `scripts/analyze_repo480_rq2_masking.py` | Oracle-masking panel on solved P2/P3 rows (RQ2) | Article Tables 13 and 14; Supplement Tables 9, 10, and 14 |
| `rq2_control` | `scripts/analyze_repo480_rq2_control.py` | Matched negative-control panel (RQ2) | Article Table 15; Supplement Table 11 |
| `expanded_retrieval` | `scripts/analyze_repo480_unbudgeted_retrieval.py --analyzed-on 2026-10-21` | Expanded-view retrieval sensitivity (RQ1) | Supplement Table 7 |
| `external_frame` | `scripts/analyze_rrl_ext120_panel.py --analyzed-on 2026-10-26` | SWE-bench-Live external-frame check (RQ1) | Supplement Table 8 |

Most scripts refuse to run if a frozen input no longer matches its recorded SHA-256, and `reproduce.py` checks every shipped file before running any step.

## Release assets

Two large files are kept outside this directory, in `release-assets/` at the top of the GitHub repository, with their checksums in `release-assets/SHA256SUMS`.
When that folder sits next to this directory, as in a clone of the repository, `reproduce.py` restores each file to the listed path and checks its SHA-256.
Otherwise place each file at the listed path yourself, or run without it.

| Asset | Place at | Size | Purpose |
| --- | --- | --- | --- |
| `repo480_unbudgeted_sources_v1.zip` | `external/notpatch_evidence/swebench-repo480-expanded-v1/repo480_unbudgeted_sources_v1.zip` | 51 MB | Every regular text file at the base commit for the seven rows of the expanded-view audit; needed to re-run that step. |
| `repo480_reviewer_views.jsonl.xz` | `external/notpatch_evidence/swebench-repo480-v1/clean/reviewer_views.jsonl` (decompress with `xz -d`) | 30 MB | Frozen task-time reviewer views for all 480 repository packets; for auditing labels, not needed by any analysis step. |

## Layout

| Path | Contents |
| --- | --- |
| `data/processed/dataset_splits/` | The 480-task random SWE-bench frame, its nested 120-task prefix, and the 120-task SWE-bench-Live frame |
| `data/annotations/raw_labels/`, `adjudicated/`, `adjudication_decisions/` | Two independent available-only passes over the 480 repository packets, the adjudication decisions, and the adjudicated labels |
| `data/annotations/oracle_gap/` | Independent boundary-validation panel, construct-validity audit, RQ2 masking panel, and matched negative-control panel returns |
| `data/annotations/typology/`, `expanded_retrieval/`, `external_frame/` | Typology coding and adjudication, the expanded-view audit, and the external-frame passes and adjudication |
| `data/annotations/worklists/` | Frozen worklists given to each panel (two large ones ship as `.xz`) |
| `data/manifests/generated/` | Package, return, and materialization manifests with checksums |
| `data/processed/oracle_masking/` | Join of the 26 repository-packet P2/P3 rows with frozen public SWE-bench run outcomes |
| `external/notpatch_evidence/` | Frozen evidence files read by the scripts; the external-frame reviewer views ship as `.xz` |
| `results/pilot/` | Analysis outputs (`.json`, `.md`, row-level `.jsonl`) |
| `paper/generated/` | LaTeX tables included verbatim in the article and supplement |
| `scripts/`, `src/notpatch/` | Analysis scripts and the small shared library they import |
| `docs/` | Annotation guideline, evidence protocol, schema errata, and panel protocols |

## Evidence boundary and labels

Annotators judged each task from a frozen task-time packet: the issue as defined by the benchmark, the repository at its base commit, and visible tests, documentation, and configuration retrieved under a fixed policy.
The merged patch, hidden tests (`test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`), and `hints_text` were withheld (`docs/repository_evidence_protocol.md`, §3.2).
Oracle evidence appears only in post-hoc records: the construct-validity audit, Phase 2 of the RQ2 panels, and the outcome join.

Primary labels are P0 (decidable), P1 (decidable with bounded assumptions), P2 (clarification needed), and P3 (not decidable from the given artifacts).
Blocker codes U1–U7 and data-quality codes (Q0–Q2, D1) are recorded separately.
Definitions are in `docs/annotation_guideline.md` (v0.5, frozen), and corrections applied to the repository packets are in `docs/task_schema.md`, §10.

Experts appear only under stable role IDs such as `repo480_r1` or `repo480_bv_adj`.
They are peer researchers with eight years of programming experience who are not authors and received no compensation.
No identity mapping is included.

## Not included

- The raw evidence corpus (about 4.1 GB of repository snapshots and inventories). The reviewer views in the release asset are the exact text shown to annotators, and `external/notpatch_evidence/swebench-repo480-v1/clean/checksums.sha256` with `data/manifests/generated/swebench_repo480_materialization_manifest_v1.json` identify the corpus they came from.
- Inputs of the pre-revision issue-packet diagnostics: the detector and utility results reported in the supplement and the second-source panel listed in the article's provenance table. Their summaries are in `results/pilot/swebench_full_prevalence_detector_eval.md`, `leakage_resistant_detector_audit.md`, `swebench_full_prevalence_real_agent_utility_replay.md`, and `swebench_extra_prevalence_random_available_only_prevalence_summary.md`; they are not regenerated here.
- Annotation request packages, coordinator records, and agent execution traces.

## Notes

- Files are copied verbatim from the research repository, so some documents link to files that are not part of this package.
- Some script and file names keep older identifiers (for example `rq1_` or `rq5_`). They are provenance only and do not follow the article's RQ numbering.
- Expert rationales, several protocol documents, and the Markdown reports are partly written in Korean. Field names, labels, codes, and the LaTeX tables are in English.
- Issue and repository text comes from public GitHub projects distributed through SWE-bench and SWE-bench-Live and remains under each project's license.
