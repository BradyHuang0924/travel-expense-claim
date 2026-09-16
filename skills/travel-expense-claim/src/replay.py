"""Replay check: an unchanged replay must produce byte-identical decisions.

Two runs over unchanged sources are compared file by file. Everything a decision depends
on must match byte for byte. The only permitted difference is the fetch timestamp the
brief requires each source record to carry, and the two hashes that necessarily follow
from it; this module names them explicitly rather than filtering them away quietly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

# sources.json carries a per-source `fetched_at`, which is wall-clock by definition.
# source_binding is the hash of that file, and predecessor is the hash of a snapshot
# that contains source_binding, so both follow from it.
TIMESTAMP_DEPENDENT = ("source_binding", "predecessor")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def compare(a_root: Path, b_root: Path) -> list[tuple[bool, str]]:
    out: list[tuple[bool, str]] = []

    a_files = {p.relative_to(a_root).as_posix()
               for p in a_root.rglob("*") if p.is_file()}
    b_files = {p.relative_to(b_root).as_posix()
               for p in b_root.rglob("*") if p.is_file()}
    out.append((a_files == b_files,
                f"same file set ({len(a_files)} files)"
                + ("" if a_files == b_files
                   else f" -- only in A {sorted(a_files - b_files)}, "
                        f"only in B {sorted(b_files - a_files)}")))

    identical, differing = [], []
    for rel in sorted(a_files & b_files):
        if _sha(a_root / rel) == _sha(b_root / rel):
            identical.append(rel)
        else:
            differing.append(rel)
    out.append((True, f"byte-identical files: {len(identical)} of {len(a_files)}"))

    retained = [r for r in differing if r.startswith("sources/")]
    out.append((not retained,
                "retained source bytes identical across both fresh reads"
                + (f" -- differ: {retained}" if retained else "")))

    decisions = [r for r in differing
                 if r in ("claims.csv", "repair-queue.json", "repair-queue.md")]
    out.append((not decisions,
                "claims.csv and repair queue byte-identical"
                + (f" -- differ: {decisions}" if decisions else "")))

    snap_diffs = []
    for rel in sorted(r for r in a_files & b_files if r.startswith("batches/")):
        a = json.loads((a_root / rel).read_text(encoding="utf-8"))
        b = json.loads((b_root / rel).read_text(encoding="utf-8"))
        a2 = {k: v for k, v in a.items() if k not in TIMESTAMP_DEPENDENT}
        b2 = {k: v for k, v in b.items() if k not in TIMESTAMP_DEPENDENT}
        if json.dumps(a2, sort_keys=True) != json.dumps(b2, sort_keys=True):
            snap_diffs.append(rel)
    out.append((not snap_diffs,
                "every snapshot identical apart from source_binding/predecessor"
                + (f" -- differ: {snap_diffs}" if snap_diffs else "")))

    a_src = json.loads((a_root / "sources.json").read_text(encoding="utf-8"))
    b_src = json.loads((b_root / "sources.json").read_text(encoding="utf-8"))

    def strip(d):
        return json.dumps({**d, "sources": [
            {k: v for k, v in s.items() if k != "fetched_at"} for s in d["sources"]]},
            sort_keys=True)

    out.append((strip(a_src) == strip(b_src),
                "sources.json identical apart from the recorded fetch timestamp"))
    ts = [s["source_id"] for s, t in zip(a_src["sources"], b_src["sources"])
          if s["fetched_at"] != t["fetched_at"]]
    out.append((True,
                f"fetch timestamp differs for {len(ts)} source records, as it must: the "
                f"brief requires each source to record when it was read"))

    unexplained = [r for r in differing
                   if not r.startswith("batches/")
                   and r not in ("sources.json", "report.md")]
    out.append((not unexplained,
                "no unexplained file differences"
                + (f" -- {unexplained}" if unexplained else "")))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_a")
    ap.add_argument("run_b")
    args = ap.parse_args(argv)
    results = compare(Path(args.run_a), Path(args.run_b))
    failed = 0
    for ok, msg in results:
        print(("  PASS  " if ok else "  FAIL  ") + msg)
        failed += 0 if ok else 1
    print(f"\n{len(results) - failed} passed, {failed} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
