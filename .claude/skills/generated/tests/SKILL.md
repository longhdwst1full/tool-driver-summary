---
name: tests
description: "Skill for the Tests area of tool-driver-summary. 68 symbols across 14 files."
---

# Tests

68 symbols | 14 files | Cohesion: 87%

## When to Use

- Working with code in `tests/`
- Understanding how process_captions, is_promotional_document, safe_segment work
- Modifying tests-related functionality

## Key Files

| File | Symbols |
|------|---------|
| `getsub_demo.py` | parse_time, parse_captions, format_time, citation, tokens (+3) |
| `study_pack.py` | manual_note_paths, relative_link, migrate_manual_notes, natural_key, build_index (+2) |
| `web_app.py` | course_name, display_name, library, file_content, read_json (+2) |
| `drive_scan.py` | folder_id_from, file_kind, transcript_key, scan_folder, report_markdown (+2) |
| `tests/test_drive_scan.py` | test_folder_link_and_id, test_recursive_scan_pagination_and_caption_pair, test_scan_limit_fails_instead_of_silent_truncation, test_file_classification, test_locale_suffix_and_video_watermark_pair (+2) |
| `codex_notes.py` | find_codex, read_cues, check_note, render_note, generate (+1) |
| `output_layout.py` | is_promotional_document, safe_segment, video_title, output_paths, safe_output_file |
| `drive_documents.py` | extract_text, save_manifest, download_media, process_documents, main |
| `tests/test_getsub_demo.py` | test_source_backed_answer_keeps_timestamp, test_out_of_source_question_abstains, test_vtt_and_srt_timing, test_malformed_caption_fails |
| `tests/test_web_app.py` | test_library_reads_reports_without_exposing_credentials, test_file_reader_blocks_unlisted_paths, test_jobs_are_whitelisted |

## Entry Points

Start here when exploring this area:

- **`process_captions`** (Function) — `drive_process.py:19`
- **`is_promotional_document`** (Function) — `output_layout.py:17`
- **`safe_segment`** (Function) — `output_layout.py:25`
- **`video_title`** (Function) — `output_layout.py:43`
- **`output_paths`** (Function) — `output_layout.py:47`

## Key Symbols

| Symbol | Type | File | Line |
|--------|------|------|------|
| `process_captions` | Function | `drive_process.py` | 19 |
| `is_promotional_document` | Function | `output_layout.py` | 17 |
| `safe_segment` | Function | `output_layout.py` | 25 |
| `video_title` | Function | `output_layout.py` | 43 |
| `output_paths` | Function | `output_layout.py` | 47 |
| `safe_output_file` | Function | `output_layout.py` | 91 |
| `manual_note_paths` | Function | `study_pack.py` | 14 |
| `relative_link` | Function | `study_pack.py` | 27 |
| `migrate_manual_notes` | Function | `study_pack.py` | 31 |
| `natural_key` | Function | `study_pack.py` | 57 |
| `build_index` | Function | `study_pack.py` | 62 |
| `update_study_pack` | Function | `study_pack.py` | 121 |
| `main` | Function | `study_pack.py` | 131 |
| `course_name` | Function | `web_app.py` | 45 |
| `display_name` | Function | `web_app.py` | 50 |
| `library` | Function | `web_app.py` | 55 |
| `file_content` | Function | `web_app.py` | 125 |
| `parse_time` | Function | `getsub_demo.py` | 31 |
| `parse_captions` | Function | `getsub_demo.py` | 43 |
| `format_time` | Function | `getsub_demo.py` | 73 |

## Execution Flows

| Flow | Type | Steps |
|------|------|-------|
| `Main → Format_time` | intra_community | 5 |
| `Build_index → Safe_segment` | intra_community | 4 |
| `Build_index → Video_title` | intra_community | 4 |
| `Library → Safe_segment` | intra_community | 4 |
| `Library → Video_title` | intra_community | 4 |
| `Main → Tokens` | intra_community | 4 |
| `Migrate_manual_notes → Safe_segment` | intra_community | 4 |
| `Migrate_manual_notes → Video_title` | intra_community | 4 |
| `Main → Safe_segment` | cross_community | 3 |
| `Main → Video_title` | cross_community | 3 |

## How to Explore

1. `context({name: "process_captions"})` — see callers and callees
2. `query({search_query: "tests"})` — find related execution flows
3. Read key files listed above for implementation details
4. `explain({target: "<file or symbol>"})` — persisted taint findings (source→sink data flows), when indexed with `--pdg`
