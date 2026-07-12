# Graph Report - wii-tennis-ai  (2026-07-11)

## Corpus Check
- 8 files · ~1,577 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 27 nodes · 25 edges · 9 communities (4 shown, 5 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- SimTennisEnv
- run
- MemoryScanner
- wii-tennis-ai
- 01-gymnasium-contract.md
- 02-ram-scanning.md
- wii-tennis-ai

## God Nodes (most connected - your core abstractions)
1. `MemoryScanner` - 7 edges
2. `SimTennisEnv` - 5 edges
3. `run()` - 5 edges
4. `wii-tennis-ai` - 3 edges
5. `main()` - 2 edges
6. `Simplified singles-rally tennis simulator standing in for real Wii Sports Tennis` - 1 edges
7. `Interactive Cheat-Engine-style RAM scanner for a running native Dolphin instance` - 1 edges
8. `Narrows a set of candidate addresses over successive scans.      Takes a `read_b` - 1 edges
9. `Status` - 1 edges
10. `Setup` - 1 edges

## Surprising Connections (you probably didn't know these)
- `run()` --calls--> `MemoryScanner`  [EXTRACTED]
  scripts/memory_scan.py → scripts/memory_scan.py  _Bridges community 2 → community 1_

## Import Cycles
- None detected.

## Communities (9 total, 5 thin omitted)

### Community 1 - "run"
Cohesion: 0.50
Nodes (3): main(), Interactive Cheat-Engine-style RAM scanner for a running native Dolphin instance, run()

### Community 3 - "wii-tennis-ai"
Cohesion: 0.50
Nodes (3): Setup, Status, wii-tennis-ai

## Knowledge Gaps
- **5 isolated node(s):** `wii-tennis-ai`, `Status`, `Setup`, `Step 1: the environment contract`, `Phase B groundwork: RAM address scanning`
  These have ≤1 connection - possible missing edges or undocumented components.
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MemoryScanner` connect `MemoryScanner` to `run`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `run()` connect `run` to `MemoryScanner`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **What connects `Simplified singles-rally tennis simulator standing in for real Wii Sports Tennis`, `wii-tennis-ai`, `Interactive Cheat-Engine-style RAM scanner for a running native Dolphin instance` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._