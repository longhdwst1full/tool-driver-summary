---
name: getsub-web
description: Update the local Drive Studio dashboard and API. Use when changing web/app.js, web/styles.css, web/index.html, or HTTP and job handling in web_app.py.
---

# Getsub web

The frontend is plain HTML, CSS, and JavaScript in `web/`. `web_app.py` serves it locally and reads private reports from `drive-reports/`.

- `library()` combines the scan and processing manifests for the browser. Keep promotional documents filtered and show the status of available captions, notes, and lesson packs accurately.
- `file_content()` reads only listed IDs and validated local paths. Keep secret files and raw, unlisted paths inaccessible.
- `command_for()` lists allowed jobs. Preserve the local host check and request token in `Handler` when adding actions. Job output must not expose OAuth credentials or token contents.
- Escape source-derived text before inserting it into HTML in `web/app.js`; use the existing URL check for Drive links. Keep user-facing messages in Vietnamese.
- Lesson packs have both `.md` and `.json` outputs. Display their QA state, including `needs_review`, instead of implying every pack passed verification.
- Course summaries in `drive-reports/courses/` are listed as notes only after a verified course output exists. `file_content()` must resolve their IDs through `library()` and validate the resulting local path.

For a web change, run `python3 -m unittest tests.test_web_app -q` and `node --check web/app.js`. Check a live browser or local HTTP response when the requested behavior depends on rendering or routing.
