const initialView = ["overview", "videos", "documents", "notes", "activity"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "overview";
const state = { pack: null, library: null, jobs: [], token: "", view: initialView, query: "", course: "", videoCourse: "", selected: null, lastJobs: "" };
const main = document.querySelector("#main");
const drawer = document.querySelector("#drawer");
const backdrop = document.querySelector("#drawer-backdrop");
const drawerContent = document.querySelector("#drawer-content");
const labels = { overview: "Tổng quan", videos: "Video bài học", documents: "Tài liệu", notes: "Ghi chú", activity: "Hoạt động" };
const jobLabels = { scan: "Quét lại Drive", captions: "Đọc phụ đề", documents: "Đọc tài liệu", note: "Tạo ghi chú AI", lesson_pack: "Tạo gói bài học" };

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}
function number(value) { return new Intl.NumberFormat("vi-VN").format(value || 0); }
function duration(ms) { if (!ms) return "—"; const minutes = Math.floor(ms / 60000); return `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`; }
function bytes(value) { if (!value) return "—"; return value >= 1e6 ? `${(value / 1e6).toFixed(1)} MB` : `${Math.ceil(value / 1000)} KB`; }
function safeUrl(url) { try { const parsed = new URL(url); return parsed.hostname === "drive.google.com" && parsed.protocol === "https:" ? parsed.href : "#"; } catch { return "#"; } }
function toast(message) { const node = document.querySelector("#toast"); node.textContent = message; node.classList.add("show"); clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.remove("show"), 4000); }

async function api(url, options = {}) {
  const response = await fetch(url, { cache: "no-store", ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `Lỗi HTTP ${response.status}`);
  return data;
}

function metric(title, value, caption, icon) {
  return `<article class="metric"><div class="metric-top"><span>${esc(title)}</span><span class="metric-icon">${icon}</span></div><strong>${number(value)}</strong><small>${esc(caption)}</small></article>`;
}
function pageHead(eyebrow, title, description, actions = "") {
  return `<div class="page-heading"><div><div class="eyebrow">${esc(eyebrow)}</div><h1>${esc(title)}</h1><p>${esc(description)}</p></div>${actions ? `<div class="heading-actions">${actions}</div>` : ""}</div>`;
}
function packTag(pack) {
  if (!pack) return "";
  const pct = pack.coverage == null ? "" : ` · ${Math.round(pack.coverage * 100)}%`;
  return pack.status === "ok" ? `<span class="tag blue">▣ Gói bài học${pct}</span>` : `<span class="tag warn">▣ Cần xem lại${pct}</span>`;
}
function sourceTag(row) {
  if (row.caption_id) return `<span class="tag">● ${number(row.cue_count)} đoạn</span> ${packTag(row.lesson_pack)}`;
  if (row.source_status === "asr_ready") return `<span class="tag blue">◌ Chờ ASR</span>`;
  return `<span class="tag muted">Không có nguồn văn bản</span>`;
}
function statusTag(status) {
  if (status === "ok") return `<span class="tag">● Đã đọc</span>`;
  if (status === "needs_ocr") return `<span class="tag warn">◌ Cần OCR</span>`;
  if (status === "too_large") return `<span class="tag warn">◌ Tệp lớn</span>`;
  if (status === "error") return `<span class="tag warn">! Lỗi</span>`;
  return `<span class="tag muted">Chưa xử lý</span>`;
}

function overview() {
  const data = state.library;
  const count = data.counts;
  const featured = [...data.courses].sort((a, b) => b.videos - a.videos).slice(0, 6);
  return `${pageHead("THƯ VIỆN HỌC TẬP", "Tổng quan nội dung", `Đã đồng bộ báo cáo từ thư mục “${data.folder.name || "Google Drive"}”.`)}
    <section class="hero"><div class="hero-content"><span class="hero-label">BỘ SƯU TẬP CỦA BẠN</span><h2>Học tập có hệ thống, từ video đến ghi chú.</h2><p>Xem tiến độ đọc phụ đề, tài liệu và mở lại đúng nguồn cho từng bài học. Mọi tác vụ chỉ chạy khi bạn yêu cầu.</p></div><div class="hero-art" aria-hidden="true"><div class="sheet"></div><div class="sheet two"></div></div></section>
    <div class="metric-grid">${metric("Video", count.video, "Trong thư mục và các thư mục con", "▷")}${metric("Tài liệu", count.document, `${data.processed.documents} đã trích văn bản`, "▤")}${metric("Phụ đề riêng", count.transcript, `${data.processed.captions} đã đọc`, "≋")}${metric("Ghi chú", data.notes.length, "Ghi chú AI và mẫu hiện có", "✦")}</div>
    <div class="two-columns"><section class="panel"><div class="panel-header"><div><h3>Khóa học trong thư mục</h3><span>${data.courses.length} khóa có video hoặc tài liệu</span></div><button class="panel-link" data-view="videos">Xem video →</button></div>${featured.map((course, i) => `<div class="course-row"><span class="course-icon">${String(i + 1).padStart(2, "0")}</span><div class="course-info"><strong title="${esc(course.name)}">${esc(course.name)}</strong><small>${number(course.captions)} phụ đề · ${number(course.documents)} tài liệu</small></div><span class="count">${number(course.videos)} video</span></div>`).join("") || `<div class="empty-state">Chưa có báo cáo quét Drive.</div>`}</section>
    <section class="panel"><div class="panel-header"><div><h3>Tiến độ xử lý</h3><span>Từ dữ liệu đã quét</span></div></div><div class="progress-block"><div class="progress-row"><div class="progress-label"><span>Video có phụ đề riêng đã đọc</span><strong>${number(data.processed.captions)} / ${number(count.video)}</strong></div><progress class="progress-meter" value="${data.processed.captions}" max="${count.video || 1}"></progress></div><div class="progress-row"><div class="progress-label"><span>Tài liệu đã trích văn bản</span><strong>${number(data.processed.documents)} / ${number(count.document)}</strong></div><progress class="progress-meter blue" value="${data.processed.documents}" max="${count.document || 1}"></progress></div><div class="progress-row"><div class="progress-label"><span>Gói bài học đã tạo</span><strong>${number(data.processed.lesson_packs)} / ${number(data.processed.captions)}</strong></div><progress class="progress-meter" value="${data.processed.lesson_packs || 0}" max="${data.processed.captions || 1}"></progress></div><div class="progress-row"><div class="progress-label"><span>Video tải được, chờ ASR</span><strong>${number(data.processed.sources?.asr_ready)}</strong></div></div><div class="progress-row"><div class="progress-label"><span>Video không có nguồn văn bản</span><strong>${number(data.processed.sources?.no_source)}</strong></div></div><div class="progress-row"><div class="progress-label"><span>Tài liệu cần OCR</span><strong>${number(data.processed.needs_ocr)}</strong></div></div></div><div class="quick-actions"><button class="button button-soft" data-run="captions">≋ &nbsp; Đọc lại file phụ đề</button><button class="button button-soft" data-run="documents">▤ &nbsp; Đọc lại tài liệu</button></div></section></div>`;
}

function toolbar() {
  const choices = state.library.courses.map(row => `<option value="${esc(row.name)}" ${state.course === row.name ? "selected" : ""}>${esc(row.name)}</option>`).join("");
  return `<div class="toolbar"><label class="search"><span aria-hidden="true">⌕</span><input id="search-input" type="search" placeholder="Tìm theo tên hoặc đường dẫn..." value="${esc(state.query)}" aria-label="Tìm kiếm"></label><select id="course-select" class="select" aria-label="Lọc khóa học"><option value="">Tất cả khóa học</option>${choices}</select></div>`;
}
function filtered(rows) {
  const query = state.query.trim().toLocaleLowerCase("vi");
  return rows.filter(row => (!state.course || row.course === state.course) && (!query || `${row.name} ${row.path} ${row.course}`.toLocaleLowerCase("vi").includes(query)));
}

function videos() {
  const all = state.library.videos;
  const courses = [...new Set(all.map(row => row.course))].sort((a, b) => a.localeCompare(b, "vi", { numeric: true }));
  const query = state.query.trim().toLocaleLowerCase("vi");
  const intro = pageHead("THƯ VIỆN VIDEO", "Video theo khóa học", "Chọn khóa học, mở từng chương và chọn bài để xem phụ đề hoặc ghi chú.", `<button class="button button-outline" data-run="captions">↻ Đọc phụ đề</button>`);
  if (!state.videoCourse || !courses.includes(state.videoCourse)) {
    return `${intro}<div class="video-search"><label class="search"><span aria-hidden="true">⌕</span><input id="video-search" type="search" placeholder="Tìm khóa học hoặc bài học..." value="${esc(state.query)}" aria-label="Tìm video"></label><small>${number(courses.length)} khóa học · ${number(all.length)} video</small></div><div class="video-course-grid">${courses.filter(course => !query || course.toLocaleLowerCase("vi").includes(query) || all.some(row => row.course === course && `${row.name} ${row.chapter}`.toLocaleLowerCase("vi").includes(query))).map((course, index) => { const rows = all.filter(row => row.course === course); const chapters = new Set(rows.map(row => row.chapter)); return `<button type="button" class="video-course-card" data-video-course="${esc(course)}"><span class="course-icon">${String(index + 1).padStart(2, "0")}</span><strong>${esc(course)}</strong><span>${number(chapters.size)} chương · ${number(rows.length)} video</span><span class="course-enter">Mở khóa học →</span></button>`; }).join("") || `<div class="empty-state">Không tìm thấy khóa học phù hợp.</div>`}</div>`;
  }
  const courseRows = all.filter(row => row.course === state.videoCourse);
  const rows = courseRows.filter(row => !query || `${row.name} ${row.chapter}`.toLocaleLowerCase("vi").includes(query));
  const chapters = [...new Set(rows.map(row => row.chapter))].sort((a, b) => a.localeCompare(b, "vi", { numeric: true }));
  return `${intro}<div class="video-breadcrumb"><button type="button" data-video-back>Khóa học</button><span>›</span><strong>${esc(state.videoCourse)}</strong></div><div class="video-search"><label class="search"><span aria-hidden="true">⌕</span><input id="video-search" type="search" placeholder="Tìm bài trong khóa học..." value="${esc(state.query)}" aria-label="Tìm bài học"></label><small>${number(rows.length)} / ${number(courseRows.length)} video · ${number(chapters.length)} chương</small></div><div class="chapter-list">${chapters.map((chapter, index) => { const lessons = rows.filter(row => row.chapter === chapter); return `<details class="chapter-card" ${query || chapters.length === 1 ? "open" : ""}><summary><span class="chapter-number">${String(index + 1).padStart(2, "0")}</span><strong>${esc(chapter)}</strong><span class="chapter-count">${number(lessons.length)} bài</span><span class="chapter-chevron">⌄</span></summary><div class="chapter-lessons">${lessons.map(row => `<button type="button" class="lesson-row" data-open-kind="video" data-id="${esc(row.id)}"><span class="file-icon">▷</span><span class="lesson-name"><strong>${esc(row.name)}</strong><small>${row.caption_id ? `${number(row.cue_count)} đoạn phụ đề` : "Chưa có phụ đề"}${row.lesson_pack ? " · Có gói bài học" : ""}</small></span><span class="lesson-duration">${duration(row.duration_ms)}</span><span class="row-arrow">›</span></button>`).join("")}</div></details>`; }).join("") || `<div class="empty-state">Không tìm thấy bài học phù hợp.</div>`}</div>`;
}

function documents() {
  const rows = filtered(state.library.documents);
  return `${pageHead("KHO TÀI LIỆU", "Tài liệu học", `${number(state.library.processed.excluded)} file quảng cáo Khóa học giá hời đã được bỏ qua.`, `<button class="button button-outline" data-run="documents">↻ Đọc tài liệu</button>`)}${toolbar()}<section class="table-card"><div class="table-header"><strong>Danh sách tài liệu</strong><small>${number(rows.length)} / ${number(state.library.documents.length)} tài liệu</small></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Tên tài liệu</th><th>Khóa học</th><th>Trạng thái</th><th>Dung lượng</th><th></th></tr></thead><tbody>${rows.map(row => `<tr tabindex="0" role="button" data-open-kind="document" data-id="${esc(row.id)}"><td><div class="item-cell"><span class="file-icon doc">▤</span><div><strong title="${esc(row.name)}">${esc(row.name)}</strong><small title="${esc(row.path)}">${esc(row.path)}</small></div></div></td><td>${esc(row.course)}</td><td>${statusTag(row.status)}</td><td>${bytes(row.size)}</td><td class="row-arrow">›</td></tr>`).join("")}</tbody></table>${rows.length ? "" : `<div class="no-results">Không tìm thấy tài liệu phù hợp.</div>`}</div></section>`;
}

function notes() {
  const rows = filtered(state.library.notes);
  return `${pageHead("KIẾN THỨC ĐÃ LƯU", "Ghi chú học tập", "Bản tóm tắt có dẫn về phụ đề hoặc tài liệu nguồn.")}${toolbar()}<div class="note-grid">${rows.map(row => `<button type="button" class="note-card" data-open-kind="${esc(row.type)}" data-id="${esc(row.id)}"><span class="file-icon note">✦</span><h3>${esc(row.name)}</h3><p>${esc(row.course)} · ${row.type === "lesson_pack" ? (row.status === "ok" ? "Gói bài học" : "Gói bài học · cần xem lại") : row.type === "course_summary" ? "Tổng hợp khóa học" : row.type === "ai_note" ? "Ghi chú AI" : row.type === "study_index" ? "Chỉ mục khóa học" : "Ghi chú mẫu"}</p><span class="bottom"><span>Đọc ghi chú</span><span>↗</span></span></button>`).join("")}</div>${rows.length ? "" : `<div class="empty-state">Chưa có ghi chú phù hợp. Mở một video có phụ đề để tạo ghi chú AI.</div>`}`;
}

function activity() {
  return `${pageHead("QUY TRÌNH XỬ LÝ", "Hoạt động", "Theo dõi các lần quét Drive, đọc phụ đề, tài liệu và tạo ghi chú trong phiên web này.")}<div class="job-list">${state.jobs.map(job => `<article class="job-card"><div class="job-head"><strong>${esc(jobLabels[job.action] || job.action)}</strong>${job.status === "running" ? `<span class="tag blue">Đang chạy</span>` : job.status === "done" ? `<span class="tag">Hoàn thành</span>` : `<span class="tag warn">Thất bại</span>`}<time>${esc(new Date(job.started).toLocaleString("vi-VN"))}</time></div>${job.output ? `<pre>${esc(job.output)}</pre>` : `<p class="detail-meta">${job.status === "running" ? "Đang xử lý; trạng thái sẽ tự cập nhật." : "Không có thông báo."}</p>`}</article>`).join("") || `<div class="empty-state">Chưa có tác vụ nào được chạy trong phiên web này.</div>`}</div>`;
}

function render() {
  if (!state.library) return;
  document.querySelector("#crumb-title").textContent = labels[state.view];
  document.querySelectorAll("#nav button").forEach(node => node.classList.toggle("active", node.dataset.view === state.view));
  main.innerHTML = ({ overview, videos, documents, notes, activity })[state.view]();
  const search = document.querySelector("#search-input");
  if (search) search.addEventListener("input", event => { const pos = event.target.selectionStart; state.query = event.target.value; render(); const input = document.querySelector("#search-input"); input.focus(); input.setSelectionRange(pos, pos); });
  document.querySelector("#course-select")?.addEventListener("change", event => { state.course = event.target.value; render(); });
  document.querySelector("#video-search")?.addEventListener("input", event => { const position = event.target.selectionStart; state.query = event.target.value; render(); const input = document.querySelector("#video-search"); input.focus(); input.setSelectionRange(position, position); });
}

function markdownInline(value) {
  const token = /(`[^`]+`|\[[^\]]+\]\([^)]+\)|\*\*[^*]+\*\*|\*[^*]+\*)/g;
  return String(value).split(token).map(part => {
    if (part.startsWith("`") && part.endsWith("`")) return `<code>${esc(part.slice(1, -1))}</code>`;
    const link = part.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) {
      const url = link[2].replace(/^<|>$/g, "");
      try {
        const parsed = new URL(url);
        if (["https:", "http:"].includes(parsed.protocol)) return `<a href="${esc(parsed.href)}" target="_blank" rel="noopener noreferrer">${esc(link[1])}</a>`;
      } catch { /* Local report paths stay as text in the web preview. */ }
      return `<span title="Liên kết đến file cục bộ">${esc(link[1])}</span>`;
    }
    if (part.startsWith("**") && part.endsWith("**")) return `<strong>${esc(part.slice(2, -2))}</strong>`;
    if (part.startsWith("*") && part.endsWith("*")) return `<em>${esc(part.slice(1, -1))}</em>`;
    return esc(part);
  }).join("");
}

function renderMarkdown(source) {
  const lines = String(source).replace(/\r\n?/g, "\n").split("\n");
  const out = [];
  let list = "", inCode = false, code = [];
  const closeList = () => { if (list) { out.push(`</${list}>`); list = ""; } };
  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index], trimmed = line.trim();
    if (trimmed.startsWith("```")) {
      closeList();
      if (inCode) { out.push(`<pre><code>${esc(code.join("\n"))}</code></pre>`); code = []; }
      inCode = !inCode; continue;
    }
    if (inCode) { code.push(line); continue; }
    if (!trimmed) { closeList(); continue; }
    if (/^\|?\s*:?-{3,}/.test(trimmed)) continue;
    if (trimmed.includes("|") && index + 1 < lines.length && /^\s*\|?\s*:?-{3,}/.test(lines[index + 1])) {
      closeList();
      const cells = row => row.trim().replace(/^\||\|$/g, "").split(/(?<!\\)\|/).map(cell => cell.trim().replace(/\\\|/g, "|"));
      const headers = cells(line);
      out.push(`<div class="markdown-table-wrap"><table><thead><tr>${headers.map(cell => `<th>${markdownInline(cell)}</th>`).join("")}</tr></thead><tbody>`);
      index += 1;
      while (index + 1 < lines.length && lines[index + 1].trim().startsWith("|")) {
        index += 1; out.push(`<tr>${cells(lines[index]).map(cell => `<td>${markdownInline(cell)}</td>`).join("")}</tr>`);
      }
      out.push("</tbody></table></div>"); continue;
    }
    const heading = trimmed.match(/^(#{1,6})\s+(.+)$/);
    if (heading) { closeList(); const level = Math.min(heading[1].length + 1, 6); out.push(`<h${level}>${markdownInline(heading[2])}</h${level}>`); continue; }
    if (/^---+$/.test(trimmed)) { closeList(); out.push("<hr>"); continue; }
    const bullet = trimmed.match(/^[-*+]\s+(.+)$/), numbered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (bullet || numbered) { const next = bullet ? "ul" : "ol"; if (list !== next) { closeList(); out.push(`<${next}>`); list = next; } out.push(`<li>${markdownInline((bullet || numbered)[1])}</li>`); continue; }
    closeList();
    if (trimmed.startsWith(">")) out.push(`<blockquote>${markdownInline(trimmed.replace(/^>\s?/, ""))}</blockquote>`);
    else out.push(`<p>${markdownInline(trimmed)}</p>`);
  }
  closeList();
  if (inCode) out.push(`<pre><code>${esc(code.join("\n"))}</code></pre>`);
  return out.join("");
}

async function readFile(kind, id) {
  const reader = drawerContent.querySelector("#reader-content");
  const title = drawerContent.querySelector("#reader-title");
  const markdown = drawerContent.querySelector("#markdown-content");
  if (!reader || !title) return;
  title.textContent = "Đang tải nội dung…";
  reader.textContent = "";
  if (markdown) { markdown.hidden = true; markdown.innerHTML = ""; }
  try {
    const result = await api(`/api/file?kind=${encodeURIComponent(kind)}&id=${encodeURIComponent(id)}`);
    const packView = drawerContent.querySelector("#pack-content");
    if (kind === "lesson_pack") {
      title.textContent = "Gói bài học";
      state.pack = result;
      reader.hidden = true; packView.hidden = false; packView.innerHTML = renderPack(result);
      return;
    }
    if (packView) { packView.hidden = true; reader.hidden = false; }
    title.textContent = kind === "document" ? "Văn bản đã trích" : kind === "transcript" ? "Timeline phụ đề" : "Ghi chú";
    if (kind !== "document" && markdown) { reader.hidden = true; markdown.hidden = false; markdown.innerHTML = renderMarkdown(result.content); }
    else reader.textContent = result.content;
  } catch (error) { title.textContent = "Không mở được nội dung"; reader.hidden = false; reader.textContent = error.message; }
}

function refChips(refs) {
  const spans = [...new Set((refs || []).map(ref => ref.at).filter(Boolean))];
  return spans.map(at => `<span class="ref-chip">${esc(at)}</span>`).join("");
}
function quotes(refs) {
  if (!refs || !refs.length) return "";
  return `<details class="quotes"><summary>Trích nguồn (${refs.length})</summary>${refs.map(ref => `<blockquote><span class="ref-chip">${esc(ref.at || ref.chunk_id)}</span> “${esc(ref.quote)}”</blockquote>`).join("")}</details>`;
}
function renderPack(result) {
  const pack = result.pack || {}, qa = result.qa || {}, meta = result.meta || {};
  const spans = Object.fromEntries((result.chunks || []).map(c => [c.chunk_id, `${c.start}–${c.end}`]));
  const coverage = qa.coverage == null ? "—" : `${Math.round(qa.coverage * 100)}%`;
  const list = (items, fn) => (items || []).map(fn).join("");
  return `<div class="pack-qa ${qa.status === "ok" ? "" : "warn"}"><strong>${qa.status === "ok" ? "✓ Đã qua kiểm tra tự động" : "⚠ Cần xem lại"}</strong><span>Coverage ${coverage} · sửa ${number(qa.revisions)} lần · ${esc(meta.prompt_id)} · ${esc(meta.model)}</span>${(qa.errors || []).length ? `<ul>${list(qa.errors, e => `<li>${esc(e)}</li>`)}</ul>` : ""}</div>
<section class="pack-section"><h3>Tóm tắt</h3><p>${esc(pack.summary)}</p></section>
<section class="pack-section"><h3>Mục tiêu bài học</h3><ul>${list(pack.objectives, x => `<li>${esc(x)}</li>`)}</ul></section>
${(meta.documents || []).length ? `<section class="pack-section"><h3>Tài liệu đi kèm</h3><ul>${list(meta.documents, d => `<li><a href="${esc(safeUrl(d.url))}" target="_blank" rel="noopener noreferrer">${esc(d.name)}</a></li>`)}</ul></section>` : ""}
<section class="pack-section"><h3>Khái niệm chính</h3><div class="concept-grid">${list(pack.concepts, c => `<article class="concept"><div class="concept-head"><strong>${esc(c.name)}</strong>${refChips(c.source_refs)}</div><p class="definition">${esc(c.definition)}</p><p>${esc(c.explanation)}</p>${quotes(c.source_refs)}</article>`)}</div></section>
${(pack.steps || []).length ? `<section class="pack-section"><h3>Các bước thực hành</h3><ol class="steps">${list(pack.steps, x => `<li>${esc(x.text)} ${refChips(x.source_refs)}</li>`)}</ol></section>` : ""}
<section class="pack-section"><h3>Timeline</h3><ol class="timeline">${list(pack.timeline, t => `<li><span class="ref-chip">${esc(spans[t.chunk_id] || "?")}</span><div><strong>${esc(t.topic)}</strong><p>${esc(t.summary)}</p></div></li>`)}</ol></section>
<section class="pack-section"><h3>Ghi chú chi tiết</h3>${list(pack.sections, x => `<article class="pack-note"><div class="concept-head"><strong>${esc(x.heading)}</strong>${refChips(x.source_refs)}</div><p>${esc(x.body)}</p>${quotes(x.source_refs)}</article>`)}</section>
<section class="pack-section"><h3>Cần nhớ</h3><ul class="remember">${list(pack.must_remember, x => `<li>${esc(x.text)} ${refChips(x.source_refs)}</li>`)}</ul></section>
<section class="pack-section"><h3>Quiz</h3>${list(pack.quiz, (q, i) => `<article class="quiz" data-quiz="${i}"><strong>${i + 1}. ${esc(q.question)}</strong><div class="quiz-options">${list(q.options, (o, j) => `<button type="button" class="quiz-option" data-quiz-q="${i}" data-quiz-opt="${j}">${String.fromCharCode(65 + j)}. ${esc(o)}</button>`)}</div><div class="quiz-result" hidden></div></article>`)}</section>
${(pack.caveats || []).length ? `<section class="pack-section"><h3>Cần kiểm tra lại</h3><ul>${list(pack.caveats, x => `<li>${esc(x)}</li>`)}</ul></section>` : ""}`;
}
function answerQuiz(button) {
  const q = state.pack?.pack?.quiz?.[Number(button.dataset.quizQ)];
  if (!q) return;
  const card = button.closest(".quiz");
  const chosen = Number(button.dataset.quizOpt);
  card.querySelectorAll(".quiz-option").forEach((el, j) => { el.disabled = true; el.classList.toggle("correct", j === q.answer_index); el.classList.toggle("wrong", j === chosen && j !== q.answer_index); });
  const result = card.querySelector(".quiz-result");
  result.hidden = false;
  result.innerHTML = `<strong>${chosen === q.answer_index ? "✓ Đúng" : `✗ Chưa đúng — đáp án ${String.fromCharCode(65 + q.answer_index)}`}</strong> ${esc(q.explanation)} ${refChips(q.source_refs)}`;
}

function openDrawer(kind, id) {
  let item;
  if (kind === "video") item = state.library.videos.find(row => row.id === id);
  else if (kind === "document") item = state.library.documents.find(row => row.id === id);
  else item = state.library.notes.find(row => row.id === id && row.type === kind);
  if (!item) return;
  state.selected = { kind, id };
  const actions = kind === "video" ? `<a class="button button-outline" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">↗ Mở video Drive</a>${item.caption_id ? `<button class="button button-soft" data-reader-kind="transcript" data-reader-id="${esc(item.caption_id)}">≋ Xem phụ đề</button>${item.lesson_pack ? `<button class="button button-outline" data-reader-kind="lesson_pack" data-reader-id="${esc(item.caption_id)}">▣ Xem gói bài học</button>` : ""}<button class="button button-accent" data-run="lesson_pack" data-caption-id="${esc(item.caption_id)}">▣ ${item.lesson_pack ? "Tạo lại gói bài học" : "Tạo gói bài học"}</button><button class="button button-soft" data-run="note" data-caption-id="${esc(item.caption_id)}">✦ Tạo ghi chú AI</button>${item.has_ai_note ? `<button class="button button-outline" data-reader-kind="ai_note" data-reader-id="${esc(item.caption_id)}">Đọc ghi chú AI</button>` : ""}${item.has_manual_note ? `<button class="button button-outline" data-reader-kind="study_note" data-reader-id="14-admin">Ghi chú mẫu</button>` : ""}` : ""}`
    : kind === "document" ? `<a class="button button-outline" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">↗ Mở tài liệu Drive</a>${item.status === "ok" ? `<button class="button button-soft" data-reader-kind="document" data-reader-id="${esc(item.id)}">▤ Xem văn bản</button>` : ""}` : "";
  const meta = kind === "video" ? `<span>${esc(item.course)} / ${esc(item.chapter)}</span><span>${item.caption_id ? `${number(item.cue_count)} đoạn phụ đề · ${duration(item.duration_ms)}` : item.source_status === "asr_ready" ? "Chưa có phụ đề · tải được, chờ ASR" : "Không có phụ đề và không tải được video"}</span>`
    : kind === "document" ? `<span>${esc(item.course)}</span><span>${bytes(item.size)} · ${item.status === "ok" ? `${number(item.characters)} ký tự` : item.status === "needs_ocr" ? "Cần OCR để lấy chữ" : "Chưa đọc được nội dung"}</span>`
      : `<span>${esc(item.course)} · ${kind === "lesson_pack" ? "Gói bài học" : kind === "ai_note" ? "Ghi chú AI" : kind === "study_index" ? "Chỉ mục khóa học" : "Ghi chú mẫu"}</span>`;
  drawerContent.innerHTML = `<div class="drawer-top"><strong>${kind === "video" ? "CHI TIẾT VIDEO" : kind === "document" ? "CHI TIẾT TÀI LIỆU" : kind === "lesson_pack" ? "GÓI BÀI HỌC" : "GHI CHÚ HỌC TẬP"}</strong><button type="button" class="icon-button" data-close aria-label="Đóng">×</button></div><div class="drawer-body"><h2>${esc(item.name)}</h2><div class="detail-meta">${meta}<span>${esc(item.path || "")}</span></div><div class="detail-actions">${actions}</div><section class="reader"><div class="reader-head"><span id="reader-title">Nội dung</span><span>${kind === "video" ? "Phụ đề / ghi chú" : kind === "document" ? "Tệp văn bản" : "Markdown"}</span></div><pre id="reader-content">${kind === "video" && !item.caption_id ? (item.source_status === "asr_ready" ? "Video chưa có phụ đề; có thể tạo bằng ASR khi bước này được bật." : "Video không có file phụ đề và chủ sở hữu không cho tải, nên không có nguồn văn bản để tạo ghi chú.") : kind === "document" && item.status !== "ok" ? "Tài liệu này chưa có văn bản để hiển thị." : "Đang tải nội dung…"}</pre><div id="markdown-content" class="markdown-preview" hidden></div><div id="pack-content" class="pack" hidden></div></section></div>`;
  backdrop.hidden = false; drawer.classList.add("open"); drawer.setAttribute("aria-hidden", "false");
  if (kind === "video" && item.caption_id) readFile(item.lesson_pack ? "lesson_pack" : item.has_ai_note ? "ai_note" : "transcript", item.caption_id);
  else if (kind === "document" && item.status === "ok") readFile("document", item.id);
  else if (kind === "ai_note" || kind === "study_note" || kind === "study_index" || kind === "lesson_pack" || kind === "course_summary") readFile(kind, id);
}
function closeDrawer() { drawer.classList.remove("open"); drawer.setAttribute("aria-hidden", "true"); backdrop.hidden = true; state.selected = null; }

async function runJob(action, captionId) {
  try {
    const job = await api("/api/jobs", { method: "POST", headers: { "Content-Type": "application/json", "X-Drive-Studio-Token": state.token }, body: JSON.stringify({ action, caption_id: captionId || null }) });
    closeDrawer(); state.view = "activity"; location.hash = "activity"; state.query = ""; state.course = "";
    state.jobs.unshift(job); render(); toast(`${jobLabels[action]} đã bắt đầu.`);
  } catch (error) { toast(error.message); }
}

document.addEventListener("click", event => {
  const close = event.target.closest("[data-close]"); if (close) { closeDrawer(); return; }
  const back = event.target.closest("[data-video-back]"); if (back) { state.videoCourse = ""; state.query = ""; render(); return; }
  const course = event.target.closest("[data-video-course]"); if (course) { state.videoCourse = course.dataset.videoCourse; state.query = ""; render(); main.focus(); return; }
  const nav = event.target.closest("[data-view]"); if (nav) { state.view = nav.dataset.view; location.hash = state.view; state.query = ""; state.course = ""; render(); main.focus(); return; }
  const quiz = event.target.closest("[data-quiz-opt]"); if (quiz) { answerQuiz(quiz); return; }
  const run = event.target.closest("[data-run]"); if (run) { runJob(run.dataset.run, run.dataset.captionId); return; }
  const reader = event.target.closest("[data-reader-kind]"); if (reader) { readFile(reader.dataset.readerKind, reader.dataset.readerId); return; }
  const open = event.target.closest("[data-open-kind]"); if (open) openDrawer(open.dataset.openKind, open.dataset.id);
});
backdrop.addEventListener("click", closeDrawer);
document.addEventListener("keydown", event => { if (event.key === "Escape") closeDrawer(); else if ((event.key === "Enter" || event.key === " ") && event.target.matches("tr[data-open-kind]")) { event.preventDefault(); openDrawer(event.target.dataset.openKind, event.target.dataset.id); } });
window.addEventListener("hashchange", () => { const next = location.hash.slice(1); if (labels[next] && next !== state.view) { state.view = next; state.query = ""; state.course = ""; render(); } });

async function pollJobs() {
  try {
    const data = await api("/api/jobs");
    const signature = JSON.stringify(data.jobs.map(row => [row.id, row.status, row.output]));
    if (signature !== state.lastJobs) {
      const previous = state.jobs;
      state.jobs = data.jobs; state.lastJobs = signature;
      if (previous.some(row => row.status === "running") && data.jobs.some(row => row.status === "done" && previous.find(old => old.id === row.id)?.status === "running")) {
        state.library = await api("/api/library"); toast("Tác vụ đã hoàn thành. Dữ liệu đã được cập nhật.");
      }
      if (state.view === "activity" || state.view === "overview") render();
    }
  } catch { /* Retain the last visible state if the local server is restarting. */ }
}

async function initialize() {
  try {
    const [session, data, jobs] = await Promise.all([api("/api/bootstrap"), api("/api/library"), api("/api/jobs")]);
    state.token = session.token; state.library = data; state.jobs = jobs.jobs; state.lastJobs = JSON.stringify(jobs.jobs.map(row => [row.id, row.status, row.output])); render();
    setInterval(pollJobs, 4000);
  } catch (error) { main.innerHTML = `<div class="empty-state">Không tải được dữ liệu: ${esc(error.message)}</div>`; }
}
initialize();
