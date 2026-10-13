const params = new URLSearchParams(location.search);
const fileId = params.get("id") || "";
const sourceId = params.get("source") || "";
const title = document.querySelector("#document-title");
const content = document.querySelector("#document-content");
const typeLabel = document.querySelector("#document-type");

function line(parent, tag, text, className = "") {
  const node = document.createElement(tag);
  node.textContent = text;
  if (className) node.className = className;
  parent.append(node);
  return node;
}

function renderText(result) {
  content.replaceChildren();
  const type = result.document_type || "text";
  typeLabel.textContent = ({ pdf: "PDF", docx: "Word", pptx: "PowerPoint", html: "HTML", spreadsheet: "Excel / Sheet", markdown: "Markdown", code: "Mã", text: "Văn bản" })[type] || "Văn bản";
  const rows = String(result.content || "").replace(/\r\n?/g, "\n").split("\n");
  content.className = `document-content document-${["pdf", "docx", "pptx", "html", "spreadsheet", "markdown", "code"].includes(type) ? type : "text"}`;
  const intro = line(content, "div", `BẢN ĐỌC · ${typeLabel.textContent}`, "reading-label");
  intro.setAttribute("aria-label", "Loại tài liệu");
  if (type === "spreadsheet") {
    let table, body;
    for (const row of rows) {
      const sheet = row.match(/^\[Trang tính (.+)\]$/);
      if (sheet) { line(content, "h2", sheet[1], "sheet-title"); table = null; continue; }
      if (!row.trim()) continue;
      if (!table) { const wrap = line(content, "div", "", "sheet-scroll"); table = line(wrap, "table", ""); body = line(table, "tbody", ""); }
      const tr = document.createElement("tr");
      row.split("\t").forEach(cell => line(tr, "td", cell));
      body.append(tr);
    }
  } else if (type === "code") {
    line(line(content, "pre", ""), "code", rows.join("\n"));
  } else {
    let paragraph = [];
    const flush = () => { if (paragraph.length) line(content, "p", paragraph.join(" ")); paragraph = []; };
    let list = null, code = null;
    for (const raw of rows) {
      const text = raw.trim();
      if (type === "markdown" && /^```/.test(text)) { flush(); list = null; code = code ? null : line(content, "pre", "", "code-block"); continue; }
      if (code) { line(code, "span", `${raw}\n`); continue; }
      if (!text) { flush(); list = null; continue; }
      const marker = text.match(/^\[(Trang|Slide)\s+(\d+)\]$/i);
      if (marker) { flush(); list = null; line(content, "h2", `${marker[1]} ${marker[2]}`, "page-heading"); continue; }
      const heading = type === "markdown" ? text.match(/^(#{1,4})\s+(.+)$/) : null;
      if (heading) { flush(); list = null; line(content, heading[1].length < 3 ? "h2" : "h3", heading[2]); continue; }
      const bullet = text.match(/^(?:[-*•]|\d+[.)])\s+(.+)$/);
      if (bullet) { flush(); const tag = /^\d/.test(text) ? "ol" : "ul"; if (!list || list.tagName.toLowerCase() !== tag) list = line(content, tag, ""); line(list, "li", bullet[1]); continue; }
      list = null;
      if (type === "docx" && raw.includes("\t")) { flush(); line(content, "p", raw.split("\t").join("  ·  "), "table-line"); continue; }
      if (type === "html" && /^<[^>]+>$/.test(text)) continue;
      paragraph.push(text);
      if (paragraph.length >= (type === "pdf" ? 6 : 4)) flush();
    }
    flush();
  }
  if (content.childNodes.length === 1) line(content, "p", "Chưa có văn bản trích xuất từ tài liệu này.");
  if (result.truncated) line(content, "p", "Bản trích đã được rút ngắn ở 1 triệu ký tự.", "notice");
}

async function initialize() {
  if (!/^[A-Za-z0-9_-]{10,}$/.test(fileId) || (sourceId && !/^[A-Za-z0-9_-]{10,}$/.test(sourceId))) {
    title.textContent = "Liên kết tài liệu không hợp lệ";
    content.textContent = "Không thể mở tài liệu này.";
    return;
  }
  const driveUrl = `https://drive.google.com/file/d/${fileId}/preview`;
  document.querySelector("#drive-frame").src = driveUrl;
  const driveLink = document.querySelector("#drive-link");
  driveLink.href = `https://drive.google.com/file/d/${fileId}/view`;
  driveLink.hidden = false;
  const query = new URLSearchParams({ kind: "document", id: fileId });
  if (sourceId) query.set("source", sourceId);
  try {
    const response = await fetch(`${sourceId ? "/api/source-file" : "/api/file"}?${query}`, { cache: "no-store" });
    if (!response.ok) throw new Error("Tài liệu chưa có văn bản đã trích; có thể xem bản gốc ở bên trái.");
    const result = await response.json();
    title.textContent = result.title || "Tài liệu học tập";
    document.title = `${title.textContent} · Drive Studio`;
    document.querySelector("#document-meta").textContent = "Xem bản gốc và nội dung đã trích trong cùng một trang";
    renderText(result);
  } catch (error) {
    title.textContent = "Xem tài liệu trên Drive";
    content.textContent = error.message;
  }
}

document.querySelector("#text-toggle").addEventListener("click", event => {
  const pane = document.querySelector("#text-pane");
  pane.hidden = !pane.hidden;
  event.currentTarget.textContent = pane.hidden ? "Hiện văn bản" : "Ẩn văn bản";
});
initialize();
