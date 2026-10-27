# NotPatch Replication Package

Replication package for the article *NotPatch: When "Resolved" Does Not Establish Patch Decidability in Repository-level Program Repair*.

| Path | Contents |
| --- | --- |
| `notpatch-ist-artifact/` | Annotation records, manifests, analysis scripts, and outputs. Its `README.md` maps every step to the article. |
| `release-assets/` | Two large inputs and their `SHA256SUMS`; `reproduce.py` restores them automatically. |

```bash
git clone https://github.com/mrhjs225/not_patch_artifact.git
cd not_patch_artifact/notpatch-ist-artifact
python3 reproduce.py    # Python 3.12+, standard library only
```

Built from research-repository commit `ee09b13f3998` on 2026-10-27.
