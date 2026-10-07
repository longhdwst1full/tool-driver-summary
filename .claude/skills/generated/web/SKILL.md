---
name: web
description: "Skill for the Web area of tool-driver-summary. 24 symbols across 1 files."
---

# Web

24 symbols | 1 files | Cohesion: 85%

## When to Use

- Working with code in `web/`
- Understanding how esc, number, metric work
- Modifying web-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `web/app.js` | esc, number, metric, pageHead, statusTag (+19) |

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `esc` | Function | `web/app.js` | 9 |
| `number` | Function | `web/app.js` | 12 |
| `metric` | Function | `web/app.js` | 25 |
| `pageHead` | Function | `web/app.js` | 28 |
| `statusTag` | Function | `web/app.js` | 31 |
| `overview` | Function | `web/app.js` | 39 |
| `toolbar` | Function | `web/app.js` | 50 |
| `filtered` | Function | `web/app.js` | 54 |
| `videos` | Function | `web/app.js` | 59 |
| `documents` | Function | `web/app.js` | 64 |
| `notes` | Function | `web/app.js` | 69 |
| `activity` | Function | `web/app.js` | 74 |
| `toast` | Function | `web/app.js` | 16 |
| `api` | Function | `web/app.js` | 18 |
| `render` | Function | `web/app.js` | 78 |
| `readFile` | Function | `web/app.js` | 88 |
| `closeDrawer` | Function | `web/app.js` | 119 |
| `runJob` | Function | `web/app.js` | 121 |
| `pollJobs` | Function | `web/app.js` | 140 |
| `initialize` | Function | `web/app.js` | 155 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Documents → Esc` | intra_community | 3 |
| `Videos → Esc` | intra_community | 3 |
| `Overview → Esc` | intra_community | 3 |

## How to Explore

1. `context({name: "esc"})` — see callers and callees
2. `query({search_query: "web"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
