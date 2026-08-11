#!/usr/bin/env python3
"""Report word-runs this repository shares with an outside corpus.

Skills here are distilled from private notes and internal write-ups. The rules
travel; the sentences are not ours to publish. Removing figures and domain
nouns is not enough — distinctive phrasing carries just as much of someone
else's document, and it survives a search for numbers untouched.

    python3 scripts/borrowed_prose.py --corpus ~/notes skills/foo/SKILL.md

Any run of >= 7 words shared with the corpus is reported. Universal Python
boilerplate is filtered; everything else is a passage to rewrite in your own
words or drop. Exit 0 clean, 1 findings, 2 no readable corpus.

This is a local authoring aid, never CI: the corpus is private and must not
enter the repository.
"""
import argparse
import re
import sys
from pathlib import Path
BOILER = re.compile(
    r"^(from future import|import |parser add argument|if name main|tempfile import|"
    r"path write text|re import sys|args parser parse args|else 0 if name|"
    r"json loads path read text|read text encoding utf 8|int m group|"
    r"str set str return|re compile r a za z0 9|verdict if name main|"
    r"parent mkdir parents true exist ok|subprocess import sys from pathlib|"
    r"return 0 if name main|r for r in rows if r|"
    r"self assertequal|self assertin|self asserttrue|def test )")
def norm(t): return re.sub(r"\s+"," ", re.sub(r"[^a-z0-9 ]+"," ", t.lower())).strip()
ap = argparse.ArgumentParser(description=__doc__,
                             formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("files", nargs="+", help="repository files to check")
ap.add_argument("--corpus", action="append", required=True, type=Path,
                help="a private file or directory to compare against; repeatable")
ap.add_argument("--words", type=int, default=7, help="shortest run to report")
args = ap.parse_args()

files=[]
for root in args.corpus:
    if root.is_file(): files.append(root)
    elif root.is_dir():
        files += [q for q in root.rglob("*") if q.is_file()
                  and q.suffix in {".md",".py",".json",".txt",".rst"}
                  and q.stat().st_size < 400_000 and "/.git/" not in str(q)]
if not files:
    sys.exit("borrowed-prose: no readable corpus files found")
N=args.words; grams=set()
for p in files:
    try: w=norm(p.read_text(errors="replace")).split()
    except Exception: continue
    grams.update(" ".join(w[i:i+N]) for i in range(len(w)-N+1))
total=0
for f in args.files:
    w=norm(Path(f).read_text()).split(); i=0; runs=[]
    while i<=len(w)-N:
        if " ".join(w[i:i+N]) in grams:
            j=i+N
            while j<len(w) and " ".join(w[j-N+1:j+1]) in grams: j+=1
            run=" ".join(w[i:j])
            if not BOILER.match(run): runs.append(run)
            i=j
        else: i+=1
    if runs:
        print(f"=== {f}")
        for r in runs: print(f"   [{len(r.split())}w] {r}")
        total+=len(runs)
print(f"TOTAL: {total} non-boilerplate run(s) of >= {N} words")
sys.exit(1 if total else 0)
