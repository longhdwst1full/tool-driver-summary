---
name: cluster-7
description: "Skill for the Cluster_7 area of tool-driver-summary. 6 symbols across 1 files."
---

# Cluster_7

6 symbols | 1 files | Cohesion: 82%

## When to Use

- Understanding how start_job, respond, json_response work
- Modifying cluster_7-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web_app.py` | start_job, respond, json_response, allowed_host, do_GET (+1) |

## Entry Points

Start here when exploring this area:

- **`start_job`** (Function) — `web_app.py:179`
- **`respond`** (Method) — `web_app.py:226`
- **`json_response`** (Method) — `web_app.py:238`
- **`allowed_host`** (Method) — `web_app.py:242`
- **`do_GET`** (Method) — `web_app.py:245`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `start_job` | Function | `web_app.py` | 179 |
| `respond` | Method | `web_app.py` | 226 |
| `json_response` | Method | `web_app.py` | 238 |
| `allowed_host` | Method | `web_app.py` | 242 |
| `do_GET` | Method | `web_app.py` | 245 |
| `do_POST` | Method | `web_app.py` | 270 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Do_GET → Respond` | intra_community | 3 |
| `Do_POST → Respond` | intra_community | 3 |

## Connected Areas

| Area | Connections |
|------|-------------|
| Tests | 3 calls |

## How to Explore

1. `context({name: "start_job"})` — see callers and callees
2. `query({search_query: "cluster_7"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
