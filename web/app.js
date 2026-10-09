const initialView = ["overview", "videos", "sources", "documents", "notes", "activity"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "overview";
const state = { pack: null, library: null, jobs: [], token: "", view: initialView, query: "", course: "", videoCourse: "", selected: null, lastJobs: "", lastLibraryRefresh: 0, librarySignature: "", sourceList: [], sourceCatalog: null, sourceQuery: "", sourceKind: "" };
const main = document.querySelector("#main");
const drawer = document.querySelector("#drawer");
const backdrop = document.querySelector("#drawer-backdrop");
const drawerContent = document.querySelector("#drawer-content");
const labels = { overview: "Tổng quan", videos: "Video bài học", sources: "Nguồn Drive mới", documents: "Tài liệu", notes: "Ghi chú", activity: "Hoạt động" };
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
function documentTypeLabel(type) {
  return ({ pdf: "PDF", docx: "Word", pptx: "PowerPoint", markdown: "Markdown", code: "Mã / cấu hình", text: "Văn bản" })[type] || "Văn bản";
}

function overview() {
  const data = state.library;
  const count = data.counts;
  const featured = [...data.courses].sort((a, b) => b.videos - a.videos).slice(0, 6);
  return `${pageHead("THƯ VIỆN HỌC TẬP", "Tổng quan nội dung", `Đã đồng bộ báo cáo từ thư mục “${data.folder.name || "Google Drive"}”.`)}
    <section class="hero"><div class="hero-content"><span class="hero-label">BỘ SƯU TẬP CỦA BẠN</span><h2>Học tập có hệ thống, từ video đến ghi chú.</h2><p>Xem tiến độ đọc phụ đề, tài liệu và mở lại đúng nguồn cho từng bài học. Mọi tác vụ chỉ chạy khi bạn yêu cầu.</p></div><div class="hero-art" aria-hidden="true"><div class="sheet"></div><div class="sheet two"></div></div></section>
    <div class="metric-grid">${metric("Video", count.video, "Trong thư mục và các thư mục con", "▷")}${metric("Tài liệu", count.document, `${data.processed.documents} đã trích văn bản`, "▤")}${metric("Bản chép lời Drive", data.processed.ui_transcripts, "Có thể đọc trong từng bài và chương", "≋")}${metric("Bài học AI", data.processed.progressive_notes, `${number(data.processed.ui_batch?.ai_waiting)} bài chờ hạn mức AI`, "✦")}</div>
    <div class="two-columns"><section class="panel"><div class="panel-header"><div><h3>Khóa học trong thư mục</h3><span>${data.courses.length} khóa có video hoặc tài liệu</span></div><button class="panel-link" data-view="videos">Xem video →</button></div>${featured.map((course, i) => `<div class="course-row"><span class="course-icon">${String(i + 1).padStart(2, "0")}</span><div class="course-info"><strong title="${esc(course.name)}">${esc(course.name)}</strong><small>${number(course.captions)} phụ đề · ${number(course.documents)} tài liệu</small></div><span class="count">${number(course.videos)} video</span></div>`).join("") || `<div class="empty-state">Chưa có báo cáo quét Drive.</div>`}</section>
    <section class="panel"><div class="panel-header"><div><h3>Tiến độ xử lý</h3><span>Từ dữ liệu đã quét</span></div></div><div class="progress-block"><div class="progress-row"><div class="progress-label"><span>Video có phụ đề riêng đã đọc</span><strong>${number(data.processed.captions)} / ${number(count.video)}</strong></div><progress class="progress-meter" value="${data.processed.captions}" max="${count.video || 1}"></progress></div><div class="progress-row"><div class="progress-label"><span>Video có nguồn lời nói đã đọc</span><strong>${number(data.processed.captions + data.processed.ui_transcripts)} / ${number(count.video)}</strong></div><progress class="progress-meter" value="${data.processed.captions + data.processed.ui_transcripts}" max="${count.video || 1}"></progress></div><div class="progress-row"><div class="progress-label"><span>Bài học AI từ bản chép lời Drive</span><strong>${number(data.processed.progressive_notes)}</strong></div></div><div class="progress-row"><div class="progress-label"><span>Tài liệu đã trích văn bản</span><strong>${number(data.processed.documents)} / ${number(count.document)}</strong></div><progress class="progress-meter blue" value="${data.processed.documents}" max="${count.document || 1}"></progress></div><div class="progress-row"><div class="progress-label"><span>Gói bài học đã tạo</span><strong>${number(data.processed.lesson_packs)} / ${number(data.processed.captions)}</strong></div><progress class="progress-meter" value="${data.processed.lesson_packs || 0}" max="${data.processed.captions || 1}"></progress></div><div class="progress-row"><div class="progress-label"><span>Video tải được, chờ ASR</span><strong>${number(data.processed.sources?.asr_ready)}</strong></div></div><div class="progress-row"><div class="progress-label"><span>Video chưa có nguồn văn bản trong ứng dụng</span><strong>${number(data.processed.sources?.no_source)}</strong></div></div><div class="progress-row"><div class="progress-label"><span>Tài liệu cần OCR</span><strong>${number(data.processed.needs_ocr)}</strong></div></div></div><div class="quick-actions"><button class="button button-soft" data-run="captions">≋ &nbsp; Đọc lại file phụ đề</button><button class="button button-soft" data-run="documents">▤ &nbsp; Đọc lại tài liệu</button></div></section></div>`;
}

function toolbar() {
  const choices = state.library.courses.map(row => `<option value="${esc(row.name)}" ${state.course === row.name ? "selected" : ""}>${esc(row.name)}</option>`).join("");
  return `<div class="toolbar"><label class="search"><span aria-hidden="true">⌕</span><input id="search-input" type="search" placeholder="Tìm theo tên hoặc đường dẫn..." value="${esc(state.query)}" aria-label="Tìm kiếm"></label><select id="course-select" class="select" aria-label="Lọc khóa học"><option value="">Tất cả khóa học</option>${choices}</select></div>`;
}
function filtered(rows) {
  const query = state.query.trim().toLocaleLowerCase("vi");
  return rows.filter(row => (!state.course || row.course === state.course) && (!query || `${row.name} ${row.path || ""} ${row.course} ${row.chapter || ""}`.toLocaleLowerCase("vi").includes(query)));
}

function videoLessonStatus(row) {
  const source = row.caption_id ? `${number(row.cue_count)} đoạn phụ đề`
    : row.ui_transcript ? `${number(row.ui_transcript.row_count)} dòng bản chép lời Drive`
      : "Chưa có phụ đề riêng";
  const pending = row.processing_status === "running" ? " · Đang xử lý"
    : row.processing_status === "ai_waiting" ? " · Chờ hạn mức AI"
    : row.processing_status === "no_transcript" ? " · Drive chưa hiển thị bản chép lời"
      : row.processing_status === "failed" ? " · Cần thử lại" : "";
  return `${source}${row.lesson_pack ? " · Có gói bài học" : ""}${row.progressive_note ? " · Có bài học AI" : ""}${pending}`;
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
  return `${intro}<div class="video-breadcrumb"><button type="button" data-video-back>Khóa học</button><span>›</span><strong>${esc(state.videoCourse)}</strong></div><div class="video-search"><label class="search"><span aria-hidden="true">⌕</span><input id="video-search" type="search" placeholder="Tìm bài trong khóa học..." value="${esc(state.query)}" aria-label="Tìm bài học"></label><small>${number(rows.length)} / ${number(courseRows.length)} video · ${number(chapters.length)} chương</small></div><div class="chapter-list">${chapters.map((chapter, index) => { const lessons = rows.filter(row => row.chapter === chapter); return `<details class="chapter-card" ${query || chapters.length === 1 ? "open" : ""}><summary><span class="chapter-number">${String(index + 1).padStart(2, "0")}</span><strong>${esc(chapter)}</strong><span class="chapter-count">${number(lessons.length)} bài</span><span class="chapter-chevron">⌄</span></summary><div class="chapter-lessons">${lessons.map(row => `<button type="button" class="lesson-row" data-open-kind="video" data-id="${esc(row.id)}"><span class="file-icon">▷</span><span class="lesson-name"><strong>${esc(row.name)}</strong><small>${esc(videoLessonStatus(row))}</small></span><span class="lesson-duration">${duration(row.duration_ms)}</span><span class="row-arrow">›</span></button>`).join("")}</div></details>`; }).join("") || `<div class="empty-state">Không tìm thấy bài học phù hợp.</div>`}</div>`;
}

function sources() {
  const catalog = state.sourceCatalog;
  const intro = pageHead("NGUỒN HỌC LIỆU", "Hai thư mục Drive mới", "Duyệt theo cây thư mục. Các nhóm và file đã loại trừ không xuất hiện trong danh sách.", catalog ? `<button type="button" class="button button-outline" data-source-refresh>↻ Cập nhật</button>` : "");
  if (!catalog) {
    return `${intro}<div class="video-course-grid">${state.sourceList.map(row => `<button type="button" class="video-course-card" data-source-id="${esc(row.id)}"><span class="course-icon">⌑</span><strong>${esc(row.name)}</strong><span>${row.complete ? "Đã quét xong" : "Đang quét"} · ${number(row.total)} mục đã giữ</span><span>${number(row.counts?.video)} video · ${number(row.counts?.document)} tài liệu</span><span>${number(row.excluded?.folders)} nhánh và ${number(row.excluded?.files)} file đã bỏ qua</span><span class="course-enter">Mở thư mục →</span></button>`).join("")}</div>`;
  }
  const source = catalog.source;
  const breadcrumb = `<div class="video-breadcrumb"><button type="button" data-source-home>Hai nguồn Drive</button>${catalog.ancestors.map((node, index) => `<span>›</span>${index === catalog.ancestors.length - 1 ? `<strong>${esc(node.name)}</strong>` : `<button type="button" data-source-parent="${esc(node.id)}">${esc(node.name)}</button>`}`).join("")}</div>`;
  const rows = catalog.items.map(row => {
    const label = row.kind === "folder" ? "Thư mục" : row.kind === "video" ? "Video" : row.kind === "document" ? "Tài liệu" : row.kind === "transcript" ? "Phụ đề" : "Tệp";
    const marker = row.kind === "folder" ? "▣" : row.kind === "video" ? "▷" : "▤";
    const location = state.sourceKind && row.kind !== "folder" ? row.path.split("/").slice(1, -1).join(" / ") : "";
    const status = row.caption_id ? " · Có phụ đề" : row.document_status === "ok" || row.transcript_status === "ok" ? " · Đã đọc" : row.document_status || row.transcript_status ? " · Chưa đọc được" : "";
    const text = `<span class="file-icon">${marker}</span><span class="lesson-name"><strong>${esc(row.name)}</strong><small class="source-path" title="${esc(row.path)}">${label}${location ? ` · ${esc(location)}` : ""}${status}${row.already_indexed ? " · Đã có trong thư viện cũ" : ""}</small></span><span class="row-arrow">›</span>`;
    return row.kind === "folder" ? `<button type="button" class="lesson-row" data-source-parent="${esc(row.id)}">${text}</button>`
      : row.kind === "video" ? `<button type="button" class="lesson-row" data-source-video="${esc(row.id)}">${text}</button>`
        : row.kind === "document" ? `<button type="button" class="lesson-row" data-source-document="${esc(row.id)}">${text}</button>`
          : row.kind === "transcript" ? `<button type="button" class="lesson-row" data-source-transcript="${esc(row.id)}">${text}</button>`
        : `<a class="lesson-row" href="${esc(safeUrl(row.url))}" target="_blank" rel="noopener noreferrer">${text}</a>`;
  }).join("");
  const shown = Math.min(catalog.total_children, catalog.offset + catalog.items.length);
  const pages = `<div class="source-pagination"><span>${number(catalog.offset + (catalog.items.length ? 1 : 0))}–${number(shown)} / ${number(catalog.total_children)} mục</span>${catalog.offset ? `<button type="button" class="button button-soft" data-source-offset="${Math.max(0, catalog.offset - 200)}">← Trước</button>` : ""}${shown < catalog.total_children ? `<button type="button" class="button button-soft" data-source-offset="${catalog.offset + 200}">Tiếp →</button>` : ""}</div>`;
  return `${intro}${breadcrumb}<section class="source-status"><strong>${esc(source.name)}</strong><span>${source.complete ? "Đã quét xong" : "Đang quét"} · ${number(source.total)} mục · ${number(source.counts?.video)} video · ${number(source.counts?.document)} tài liệu</span><small>Đã bỏ qua ${number(source.excluded?.folders)} nhánh thư mục và ${number(source.excluded?.files)} file</small></section><div class="source-search"><input id="source-search-input" type="search" placeholder="Tìm tên bài hoặc khóa học trong nguồn này..." value="${esc(state.sourceQuery)}" aria-label="Tìm trong nguồn Drive"><select id="source-kind" class="select" aria-label="Lọc loại nội dung"><option value="">Tất cả</option><option value="folder" ${state.sourceKind === "folder" ? "selected" : ""}>Thư mục</option><option value="video" ${state.sourceKind === "video" ? "selected" : ""}>Video</option><option value="document" ${state.sourceKind === "document" ? "selected" : ""}>Tài liệu</option></select><button type="button" class="button button-outline" data-source-search>Tìm</button></div><section class="chapter-card"><div class="chapter-lessons">${rows || `<div class="empty-state">${catalog.parent_scanned || catalog.query ? "Không có mục phù hợp." : "Thư mục này đang chờ lượt quét."}</div>`}</div></section>${pages}`;
}

async function loadSource(sourceId, parentId = "", offset = 0, query = "") {
  try {
    const params = new URLSearchParams({ source: sourceId, offset: String(offset) });
    if (parentId) params.set("parent", parentId);
    if (query) params.set("q", query);
    if (state.sourceKind) params.set("kind", state.sourceKind);
    state.sourceCatalog = await api(`/api/source-catalog?${params}`);
    state.sourceQuery = query;
    render();
    main.focus();
  } catch (error) { toast(error.message); }
}

function openSourceVideo(id) {
  const item = state.sourceCatalog?.items.find(row => row.id === id && row.kind === "video");
  if (!item || !/^[A-Za-z0-9_-]+$/.test(id)) return;
  const inLibrary = state.library.videos.some(row => row.id === id);
  state.selected = { kind: "source_video", id };
  drawerContent.innerHTML = `<div class="drawer-top"><strong>VIDEO TỪ NGUỒN DRIVE</strong><button type="button" class="icon-button" data-close aria-label="Đóng">×</button></div><div class="drawer-body"><h2>${esc(item.name)}</h2><div class="detail-meta"><span>${esc(item.path)}</span><span>${item.caption_id ? "Có file phụ đề riêng đã đọc" : inLibrary ? "Video này đã có trong thư viện học tập" : "Đã quét metadata; chưa tạo bản chép lời"}</span></div><div class="video-preview"><iframe title="Xem ${esc(item.name)} trên Google Drive" src="https://drive.google.com/file/d/${esc(id)}/preview" loading="lazy" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen referrerpolicy="no-referrer"></iframe></div><div class="detail-actions"><a class="button button-outline" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">↗ Mở video Drive</a>${inLibrary ? `<button class="button button-accent" data-open-kind="video" data-id="${esc(id)}">Đọc bài học đã lưu</button>` : ""}</div><section class="reader"><div class="reader-head"><span id="reader-title">Phụ đề</span><span>Timeline</span></div><pre id="reader-content">${item.caption_id ? "Đang tải phụ đề…" : "Video này chưa có file phụ đề riêng đã xử lý."}</pre><div id="markdown-content" class="markdown-preview" hidden></div></section></div>`;
  backdrop.hidden = false; drawer.classList.add("open"); drawer.setAttribute("aria-hidden", "false");
  if (item.caption_id) readSourceFile("transcript", item.caption_id);
}

function openSourceDocument(id) {
  const item = state.sourceCatalog?.items.find(row => row.id === id && row.kind === "document");
  if (!item || !/^[A-Za-z0-9_-]+$/.test(id)) return;
  state.selected = { kind: "source_document", id };
  drawerContent.innerHTML = `<div class="drawer-top"><strong>TÀI LIỆU TỪ NGUỒN DRIVE</strong><button type="button" class="icon-button" data-close aria-label="Đóng">×</button></div><div class="drawer-body"><h2>${esc(item.name)}</h2><div class="detail-meta"><span>${esc(item.path)}</span><span>${item.document_status === "ok" ? "Đã trích văn bản" : "Chưa có văn bản để xem trên web"}</span></div><div class="detail-actions"><a class="button button-outline" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">↗ Mở tài liệu Drive</a></div><section class="reader"><div class="reader-head"><span id="reader-title">Nội dung tài liệu</span><span>Văn bản</span></div><pre id="reader-content">${item.document_status === "ok" ? "Đang tải nội dung…" : "Tài liệu chưa được trích văn bản hoặc cần xử lý thêm."}</pre><div id="markdown-content" class="markdown-preview" hidden></div></section></div>`;
  backdrop.hidden = false; drawer.classList.add("open"); drawer.setAttribute("aria-hidden", "false");
  if (item.document_status === "ok") readSourceFile("document", id);
}

function openSourceTranscript(id) {
  const item = state.sourceCatalog?.items.find(row => row.id === id && row.kind === "transcript");
  if (!item || !/^[A-Za-z0-9_-]+$/.test(id)) return;
  state.selected = { kind: "source_transcript", id };
  drawerContent.innerHTML = `<div class="drawer-top"><strong>PHỤ ĐỀ TỪ NGUỒN DRIVE</strong><button type="button" class="icon-button" data-close aria-label="Đóng">×</button></div><div class="drawer-body"><h2>${esc(item.name)}</h2><div class="detail-meta"><span>${esc(item.path)}</span><span>${item.transcript_status === "ok" ? "Đã đọc mốc thời gian" : "Phụ đề chưa đọc được"}</span></div><div class="detail-actions"><a class="button button-outline" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">↗ Mở file Drive</a></div><section class="reader"><div class="reader-head"><span id="reader-title">Timeline phụ đề</span><span>Markdown</span></div><pre id="reader-content">${item.transcript_status === "ok" ? "Đang tải phụ đề…" : "File phụ đề thiếu mốc thời gian hợp lệ hoặc chưa được xử lý."}</pre><div id="markdown-content" class="markdown-preview" hidden></div></section></div>`;
  backdrop.hidden = false; drawer.classList.add("open"); drawer.setAttribute("aria-hidden", "false");
  if (item.transcript_status === "ok") readSourceFile("transcript", id);
}

async function readSourceFile(kind, id) {
  const selected = state.selected;
  try {
    const params = new URLSearchParams({ source: state.sourceCatalog.source.id, kind, id });
    const result = await api(`/api/source-file?${params}`);
    if (state.selected !== selected) return;
    const title = drawerContent.querySelector("#reader-title");
    const reader = drawerContent.querySelector("#reader-content");
    const preview = drawerContent.querySelector("#markdown-content");
    if (!title || !reader || !preview) return;
    title.textContent = kind === "document" ? "Nội dung tài liệu" : "Timeline phụ đề";
    reader.hidden = true; preview.hidden = false;
    preview.innerHTML = (kind === "document" ? renderDocument(result) : renderMarkdown(result.content))
      + (result.truncated ? '<p>Chỉ hiển thị 1 triệu ký tự đầu; mở file Drive để xem tiếp.</p>' : "");
  } catch (error) {
    if (state.selected === selected) drawerContent.querySelector("#reader-content").textContent = error.message;
  }
}

function documents() {
  const rows = filtered(state.library.documents);
  return `${pageHead("KHO TÀI LIỆU", "Tài liệu học", `${number(state.library.processed.excluded)} file quảng cáo Khóa học giá hời đã được bỏ qua.`, `<button class="button button-outline" data-run="documents">↻ Đọc tài liệu</button>`)}${toolbar()}<section class="table-card"><div class="table-header"><strong>Danh sách tài liệu</strong><small>${number(rows.length)} / ${number(state.library.documents.length)} tài liệu</small></div><div class="table-wrap"><table class="data-table"><thead><tr><th>Tên tài liệu</th><th>Khóa học</th><th>Loại</th><th>Trạng thái</th><th>Dung lượng</th><th></th></tr></thead><tbody>${rows.map(row => `<tr tabindex="0" role="button" data-open-kind="document" data-id="${esc(row.id)}"><td><div class="item-cell"><span class="file-icon doc">▤</span><div><strong title="${esc(row.name)}">${esc(row.name)}</strong><small title="${esc(row.path)}">${esc(row.path)}</small></div></div></td><td>${esc(row.course)}</td><td><span class="document-type-badge">${esc(documentTypeLabel(row.document_type))}</span></td><td>${statusTag(row.status)}</td><td>${bytes(row.size)}</td><td class="row-arrow">›</td></tr>`).join("")}</tbody></table>${rows.length ? "" : `<div class="no-results">Không tìm thấy tài liệu phù hợp.</div>`}</div></section>`;
}

function notes() {
  const rows = filtered(state.library.notes);
  const courses = [...new Set(rows.map(row => row.course))].sort((a, b) => a.localeCompare(b, "vi", { numeric: true }));
  const label = row => row.type === "progressive_note" ? `Bài học AI · ${number(row.covered_chunks)} đoạn đã dẫn nguồn`
    : row.type === "ui_transcript" ? `Bản chép lời Drive · ${number(row.row_count)} dòng`
    : row.type === "lesson_pack" ? (row.status === "ok" ? "Gói bài học" : "Gói bài học · cần xem lại")
      : row.type === "video_summaries" ? "Nội dung chi tiết video" : row.type === "cross_source_review" ? "Đối chiếu nguồn"
        : row.type === "course_summary" ? "Tổng hợp khóa học" : row.type === "ai_note" ? "Ghi chú AI"
          : row.type === "study_index" ? "Chỉ mục khóa học" : "Ghi chú học tập";
  const cards = entries => `<div class="note-grid">${entries.map(row => `<button type="button" class="note-card${row.type === "ui_transcript" ? " note-card-transcript" : ""}" data-open-kind="${esc(row.type)}" data-id="${esc(row.id)}"><span class="file-icon note">${row.type === "ui_transcript" ? "≋" : "✦"}</span><h3>${esc(row.name)}</h3><p>${esc(label(row))}</p><span class="bottom"><span>${row.type === "ui_transcript" ? "Đọc bản chép lời" : "Đọc bài"}</span><span>↗</span></span></button>`).join("")}</div>`;
  const groups = courses.map(course => {
    const courseRows = rows.filter(row => row.course === course);
    const chapters = [...new Set(courseRows.map(row => row.chapter || "Tổng quan và tài liệu"))]
      .sort((a, b) => a.localeCompare(b, "vi", { numeric: true }));
    return `<section class="note-course"><header class="note-course-head"><span class="course-icon">✦</span><div><h2>${esc(course)}</h2><small>${number(courseRows.length)} bài học và ghi chú</small></div></header>${chapters.map((chapter, index) => {
      const lessons = courseRows.filter(row => (row.chapter || "Tổng quan và tài liệu") === chapter);
      return `<details class="note-chapter" ${state.query || chapters.length === 1 ? "open" : ""}><summary><span class="chapter-number">${String(index + 1).padStart(2, "0")}</span><strong>${esc(chapter)}</strong><span class="chapter-count">${number(lessons.length)} bài</span><span class="chapter-chevron">⌄</span></summary>${cards(lessons)}</details>`;
    }).join("")}</section>`;
  }).join("");
  return `${pageHead("KIẾN THỨC ĐÃ LƯU", "Học theo khóa và chương", "Mở từng chương để đọc bài học, bản tóm tắt và nguồn tham chiếu.")}${toolbar()}${groups || `<div class="empty-state">Chưa có ghi chú phù hợp.</div>`}`;
}

function activity() {
  return `${pageHead("QUY TRÌNH XỬ LÝ", "Hoạt động", "Theo dõi các lần quét Drive, đọc phụ đề, tài liệu và tạo ghi chú trong phiên web này.")}<div class="job-list">${state.jobs.map(job => `<article class="job-card"><div class="job-head"><strong>${esc(jobLabels[job.action] || job.action)}</strong>${job.status === "running" ? `<span class="tag blue">Đang chạy</span>` : job.status === "done" ? `<span class="tag">Hoàn thành</span>` : `<span class="tag warn">Thất bại</span>`}<time>${esc(new Date(job.started).toLocaleString("vi-VN"))}</time></div>${job.output ? `<pre>${esc(job.output)}</pre>` : `<p class="detail-meta">${job.status === "running" ? "Đang xử lý; trạng thái sẽ tự cập nhật." : "Không có thông báo."}</p>`}</article>`).join("") || `<div class="empty-state">Chưa có tác vụ nào được chạy trong phiên web này.</div>`}</div>`;
}

function render() {
  if (!state.library) return;
  document.querySelector("#crumb-title").textContent = labels[state.view];
  document.querySelectorAll("#nav button").forEach(node => node.classList.toggle("active", node.dataset.view === state.view));
  main.innerHTML = ({ overview, videos, sources, documents, notes, activity })[state.view]();
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

function renderDocument(result) {
  const type = result.document_type || "text";
  const label = documentTypeLabel(type);
  const intro = `<div class="document-preview-head"><span class="document-type-badge">${esc(label)}</span><span>${type === "markdown" || type === "code" || type === "text" ? "Nội dung văn bản" : "Bản trích văn bản từ file gốc"}</span></div>`;
  if (type === "markdown") return `<article class="document-preview document-markdown">${intro}${renderMarkdown(result.content)}</article>`;
  if (type === "code") return `<article class="document-preview document-code">${intro}<pre><code>${esc(result.content)}</code></pre></article>`;

  const output = [];
  const lines = String(result.content).replace(/\r\n?/g, "\n").split("\n");
  let paragraph = [], list = "", table = false;
  const closeParagraph = () => {
    if (paragraph.length) { output.push(`<p>${esc(paragraph.join(type === "pdf" ? " " : "\n"))}</p>`); paragraph = []; }
  };
  const closeList = () => { if (list) { output.push(`</${list}>`); list = ""; } };
  const closeTable = () => { if (table) { output.push("</tbody></table></div>"); table = false; } };
  const closeAll = () => { closeParagraph(); closeList(); closeTable(); };
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { closeAll(); continue; }
    const marker = line.match(/^\[(Trang|Slide)\s+(\d+)\]$/i);
    if (marker) {
      closeAll(); output.push(`<h3 class="document-page-marker">${marker[1].toLowerCase() === "slide" ? "Trang chiếu" : "Trang"} ${esc(marker[2])}</h3>`);
      continue;
    }
    if (raw.includes("\t") && type === "docx") {
      closeParagraph(); closeList();
      if (!table) { output.push('<div class="document-table-wrap"><table><tbody>'); table = true; }
      output.push(`<tr>${raw.split("\t").map(cell => `<td>${esc(cell.trim())}</td>`).join("")}</tr>`);
      continue;
    }
    closeTable();
    const bullet = line.match(/^[•●*-]\s+(.+)$/);
    const numbered = line.match(/^\d+[.)]\s+(.+)$/);
    if (bullet || numbered) {
      closeParagraph();
      const next = bullet ? "ul" : "ol";
      if (list !== next) { closeList(); output.push(`<${next}>`); list = next; }
      output.push(`<li>${esc((bullet || numbered)[1])}</li>`);
      continue;
    }
    closeList();
    const letters = line.replace(/[^\p{L}]/gu, "");
    if (line.length <= 90 && letters.length >= 3 && letters === letters.toLocaleUpperCase("vi-VN") && letters !== letters.toLocaleLowerCase("vi-VN")) {
      closeParagraph(); output.push(`<h3 class="document-section-title">${esc(line)}</h3>`);
      continue;
    }
    if (type === "pdf") {
      paragraph.push(line);
      if (paragraph.length >= 8) closeParagraph();
    } else {
      closeParagraph(); output.push(`<p>${esc(line)}</p>`);
    }
  }
  closeAll();
  return `<article class="document-preview document-${esc(type)}">${intro}${output.join("")}</article>`;
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
    title.textContent = kind === "document" ? `${documentTypeLabel(result.document_type)} · Xem nội dung` : kind === "transcript" ? "Timeline phụ đề" : "Ghi chú";
    if (markdown) { reader.hidden = true; markdown.hidden = false; markdown.innerHTML = kind === "document" ? renderDocument(result) : renderMarkdown(result.content); }
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
  const actions = kind === "video" ? `<a class="button button-outline" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">↗ Mở video Drive</a>${item.progressive_note ? `<button class="button button-accent" data-reader-kind="progressive_note" data-reader-id="${esc(item.id)}">✦ Đọc bài học AI</button>` : ""}${item.ui_transcript ? `<button class="button button-soft" data-reader-kind="ui_transcript" data-reader-id="${esc(item.id)}">≋ Xem bản chép lời Drive</button>` : ""}${item.caption_id ? `<button class="button button-soft" data-reader-kind="transcript" data-reader-id="${esc(item.caption_id)}">≋ Xem phụ đề</button>${item.lesson_pack ? `<button class="button button-outline" data-reader-kind="lesson_pack" data-reader-id="${esc(item.caption_id)}">▣ Xem gói bài học</button>` : ""}<button class="button button-accent" data-run="lesson_pack" data-caption-id="${esc(item.caption_id)}">▣ ${item.lesson_pack ? "Tạo lại gói bài học" : "Tạo gói bài học"}</button><button class="button button-soft" data-run="note" data-caption-id="${esc(item.caption_id)}">✦ Tạo ghi chú AI</button>${item.has_ai_note ? `<button class="button button-outline" data-reader-kind="ai_note" data-reader-id="${esc(item.caption_id)}">Đọc ghi chú AI</button>` : ""}${item.has_manual_note ? `<button class="button button-outline" data-reader-kind="study_note" data-reader-id="14-admin">Ghi chú mẫu</button>` : ""}` : ""}`
    : kind === "document" ? `<a class="button button-outline" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">↗ Mở tài liệu Drive</a>${item.status === "ok" ? `<button class="button button-soft" data-reader-kind="document" data-reader-id="${esc(item.id)}">▤ Xem văn bản</button>` : ""}` : "";
  const transcriptActions = kind === "ui_transcript" ? `<a class="button button-outline" href="${esc(safeUrl(item.url))}" target="_blank" rel="noopener noreferrer">↗ Mở video Drive</a>` : "";
  const meta = kind === "video" ? `<span>${esc(item.course)} / ${esc(item.chapter)}</span><span>${item.ui_transcript ? `${number(item.ui_transcript.row_count)} dòng bản chép lời Drive · đến ${esc(item.ui_transcript.last_at)}` : item.caption_id ? `${number(item.cue_count)} đoạn phụ đề · ${duration(item.duration_ms)}` : item.source_status === "asr_ready" ? "Chưa có phụ đề · tải được, chờ ASR" : "Chưa có file phụ đề riêng trong ứng dụng · video không tải được"}</span>`
    : kind === "document" ? `<span>${esc(item.course)} · ${esc(documentTypeLabel(item.document_type))}</span><span>${bytes(item.size)} · ${item.status === "ok" ? `${number(item.characters)} ký tự` : item.status === "needs_ocr" ? "Cần OCR để lấy chữ" : "Chưa đọc được nội dung"}</span>`
      : `<span>${esc(item.course)}${item.chapter ? ` / ${esc(item.chapter)}` : ""} · ${kind === "progressive_note" ? "Bài học AI có dẫn nguồn" : kind === "ui_transcript" ? "Bản chép lời Drive" : kind === "lesson_pack" ? "Gói bài học" : kind === "ai_note" ? "Ghi chú AI" : kind === "video_summaries" ? "Nội dung chi tiết video" : kind === "study_index" ? "Chỉ mục khóa học" : "Ghi chú mẫu"}</span>`;
  drawerContent.innerHTML = `<div class="drawer-top"><strong>${kind === "video" ? "CHI TIẾT VIDEO" : kind === "document" ? "CHI TIẾT TÀI LIỆU" : kind === "lesson_pack" ? "GÓI BÀI HỌC" : "GHI CHÚ HỌC TẬP"}</strong><button type="button" class="icon-button" data-close aria-label="Đóng">×</button></div><div class="drawer-body"><h2>${esc(item.name)}</h2><div class="detail-meta">${meta}<span>${esc(item.path || "")}</span></div>${(kind === "video" || kind === "ui_transcript") && /^[A-Za-z0-9_-]+$/.test(item.id) ? `<div class="video-preview"><iframe title="Xem ${esc(item.name)} trên Google Drive" src="https://drive.google.com/file/d/${esc(item.id)}/preview" loading="lazy" allow="autoplay; fullscreen; picture-in-picture" allowfullscreen referrerpolicy="no-referrer"></iframe></div>` : ""}<div class="detail-actions">${actions}${transcriptActions}</div><section class="reader"><div class="reader-head"><span id="reader-title">Nội dung</span><span>${kind === "video" ? "Phụ đề / ghi chú" : kind === "document" ? esc(documentTypeLabel(item.document_type)) : "Markdown"}</span></div><pre id="reader-content">${kind === "video" && !item.caption_id && !item.ui_transcript ? (item.source_status === "asr_ready" ? "Video chưa có phụ đề; có thể tạo bằng ASR khi bước này được bật." : "Drive có thể hiển thị bản chép lời, nhưng ứng dụng chưa lấy được caption track. Video không có file phụ đề riêng và tài khoản không có quyền tải; cần chủ sở hữu cấp quyền hoặc cung cấp phụ đề.") : kind === "document" && item.status !== "ok" ? "Tài liệu này chưa có văn bản để hiển thị." : "Đang tải nội dung…"}</pre><div id="markdown-content" class="markdown-preview" hidden></div><div id="pack-content" class="pack" hidden></div></section></div>`;
  backdrop.hidden = false; drawer.classList.add("open"); drawer.setAttribute("aria-hidden", "false");
  if (kind === "video" && item.progressive_note) readFile("progressive_note", item.id);
  else if (kind === "video" && item.caption_id) readFile(item.lesson_pack ? "lesson_pack" : item.has_ai_note ? "ai_note" : "transcript", item.caption_id);
  else if (kind === "video" && item.ui_transcript) readFile("ui_transcript", item.id);
  else if (kind === "document" && item.status === "ok") readFile("document", item.id);
  else if (kind === "ai_note" || kind === "progressive_note" || kind === "ui_transcript" || kind === "study_note" || kind === "study_index" || kind === "video_summaries" || kind === "lesson_pack" || kind === "course_summary" || kind === "cross_source_review") readFile(kind, id);
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
  const sourceHome = event.target.closest("[data-source-home]"); if (sourceHome) { state.sourceCatalog = null; state.sourceQuery = ""; state.sourceKind = ""; render(); return; }
  const sourceRefresh = event.target.closest("[data-source-refresh]"); if (sourceRefresh) { loadSource(state.sourceCatalog.source.id, state.sourceCatalog.parent_id, state.sourceCatalog.offset, state.sourceQuery); return; }
  const source = event.target.closest("[data-source-id]"); if (source) { state.sourceKind = ""; loadSource(source.dataset.sourceId); return; }
  const sourceParent = event.target.closest("[data-source-parent]"); if (sourceParent) { loadSource(state.sourceCatalog.source.id, sourceParent.dataset.sourceParent); return; }
  const sourceOffset = event.target.closest("[data-source-offset]"); if (sourceOffset) { loadSource(state.sourceCatalog.source.id, state.sourceCatalog.parent_id, Number(sourceOffset.dataset.sourceOffset), state.sourceQuery); return; }
  const sourceSearch = event.target.closest("[data-source-search]"); if (sourceSearch) { loadSource(state.sourceCatalog.source.id, state.sourceCatalog.parent_id, 0, document.querySelector("#source-search-input")?.value.trim() || ""); return; }
  const sourceVideo = event.target.closest("[data-source-video]"); if (sourceVideo) { openSourceVideo(sourceVideo.dataset.sourceVideo); return; }
  const sourceDocument = event.target.closest("[data-source-document]"); if (sourceDocument) { openSourceDocument(sourceDocument.dataset.sourceDocument); return; }
  const sourceTranscript = event.target.closest("[data-source-transcript]"); if (sourceTranscript) { openSourceTranscript(sourceTranscript.dataset.sourceTranscript); return; }
  const back = event.target.closest("[data-video-back]"); if (back) { state.videoCourse = ""; state.query = ""; render(); return; }
  const course = event.target.closest("[data-video-course]"); if (course) { state.videoCourse = course.dataset.videoCourse; state.query = ""; render(); main.focus(); return; }
  const nav = event.target.closest("[data-view]"); if (nav) { state.view = nav.dataset.view; location.hash = state.view; state.query = ""; state.course = ""; render(); main.focus(); return; }
  const quiz = event.target.closest("[data-quiz-opt]"); if (quiz) { answerQuiz(quiz); return; }
  const run = event.target.closest("[data-run]"); if (run) { runJob(run.dataset.run, run.dataset.captionId); return; }
  const reader = event.target.closest("[data-reader-kind]"); if (reader) { readFile(reader.dataset.readerKind, reader.dataset.readerId); return; }
  const open = event.target.closest("[data-open-kind]"); if (open) openDrawer(open.dataset.openKind, open.dataset.id);
});
backdrop.addEventListener("click", closeDrawer);
document.addEventListener("keydown", event => { if (event.key === "Escape") closeDrawer(); else if (event.key === "Enter" && event.target.id === "source-search-input") { event.preventDefault(); loadSource(state.sourceCatalog.source.id, state.sourceCatalog.parent_id, 0, event.target.value.trim()); } else if ((event.key === "Enter" || event.key === " ") && event.target.matches("tr[data-open-kind]")) { event.preventDefault(); openDrawer(event.target.dataset.openKind, event.target.dataset.id); } });
document.addEventListener("change", event => { if (event.target.id === "source-kind" && state.sourceCatalog) { state.sourceKind = event.target.value; loadSource(state.sourceCatalog.source.id, state.sourceCatalog.parent_id, 0, state.sourceQuery); } });
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
    if (Date.now() - state.lastLibraryRefresh > 15000) {
      state.lastLibraryRefresh = Date.now();
      const [next, sourceData] = await Promise.all([api("/api/library"), api("/api/source-catalog")]);
      const nextSignature = JSON.stringify([next.processed, next.videos.map(row => [row.id, row.ui_transcript?.row_count, row.progressive_note?.status, row.processing_status])]);
      if (nextSignature !== state.librarySignature) {
        state.library = next; state.librarySignature = nextSignature;
        if (!document.activeElement?.matches("input,select")) render();
      }
      const oldSources = JSON.stringify(state.sourceList);
      state.sourceList = sourceData.sources;
      if (state.view === "sources" && !state.sourceCatalog && JSON.stringify(state.sourceList) !== oldSources) render();
    }
  } catch { /* Retain the last visible state if the local server is restarting. */ }
}

async function initialize() {
  try {
    const [session, data, jobs, sourceData] = await Promise.all([api("/api/bootstrap"), api("/api/library"), api("/api/jobs"), api("/api/source-catalog")]);
    state.token = session.token; state.library = data; state.jobs = jobs.jobs; state.lastJobs = JSON.stringify(jobs.jobs.map(row => [row.id, row.status, row.output]));
    state.sourceList = sourceData.sources;
    state.librarySignature = JSON.stringify([data.processed, data.videos.map(row => [row.id, row.ui_transcript?.row_count, row.progressive_note?.status, row.processing_status])]);
    state.lastLibraryRefresh = Date.now(); render();
    setInterval(pollJobs, 4000);
  } catch (error) { main.innerHTML = `<div class="empty-state">Không tải được dữ liệu: ${esc(error.message)}</div>`; }
}
initialize();
