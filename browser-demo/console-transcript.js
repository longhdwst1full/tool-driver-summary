/*
 * Run in Chrome DevTools Console on an open Google Drive video tab.
 * Reads timestamped text rendered in the visible transcript panel, scrolls it,
 * and downloads one JSON file. It does not call Drive APIs or hidden endpoints.
 */
(async () => {
  const match = location.href.match(/^https:\/\/drive\.google\.com\/file\/d\/([A-Za-z0-9_-]+)/);
  if (!match) throw new Error('Mở tab video drive.google.com/file/d/... trước khi chạy.');
  const videoId = match[1];
  const transcriptLabel = /bản chép lời|transcript/i;
  const timeLine = /^\d{1,2}:\d{2}(?::\d{2})?$/;
  const seconds = value => value.split(':').reduce((total, part) => total * 60 + Number(part), 0);
  const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

  const findPanel = () => {
    const candidates = [...document.querySelectorAll('*')].map(el => {
      const rect = el.getBoundingClientRect();
      const text = el.innerText || '';
      const stamps = (text.match(/(?:^|\n)\s*\d{1,2}:\d{2}(?::\d{2})?\s*(?=\n|$)/g) || []).length;
      return { el, rect, stamps, distance: el.scrollHeight - el.clientHeight };
    }).filter(item => item.stamps >= 2 && item.distance > 40
      && item.rect.width > 150 && item.rect.width < innerWidth * 0.55
      && item.rect.left > innerWidth * 0.4 && item.rect.height > 120);
    candidates.sort((a, b) => b.stamps - a.stamps || b.distance - a.distance);
    return candidates[0]?.el || null;
  };

  let panel = findPanel();
  if (!panel) {
    const tab = [...document.querySelectorAll('button,[role="button"],[role="tab"]')]
      .find(el => transcriptLabel.test((el.getAttribute('aria-label') || '') + ' ' + (el.innerText || '')));
    if (tab) {
      tab.click();
      await pause(800);
      panel = findPanel();
    }
  }
  if (!panel) throw new Error('Không thấy panel bản chép lời có timestamp; mở panel thủ công rồi chạy lại.');

  const parse = text => {
    const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
    const rows = [];
    let current = null;
    for (const line of lines) {
      if (/^(Sao chép đường liên kết đến bản chép lời này|Copy link to this transcript)$/i.test(line)) continue;
      if (timeLine.test(line)) {
        if (current?.text) rows.push(current);
        current = { at: line, text: '' };
      } else if (current) {
        current.text += (current.text ? ' ' : '') + line;
      }
    }
    if (current?.text) rows.push(current);
    return rows;
  };

  panel.scrollTop = 0;
  await pause(500);
  const seen = new Map();
  let atBottom = false;
  let stable = 0;
  const initialRows = parse(panel.innerText || '');
  if (initialRows.length >= 100) {
    panel.scrollTop = panel.scrollHeight;
    await pause(350);
    const bottomRows = parse(panel.innerText || '');
    if (bottomRows.length >= initialRows.length &&
        bottomRows[0]?.at === initialRows[0]?.at &&
        bottomRows.at(-1)?.at === initialRows.at(-1)?.at &&
        panel.scrollTop + panel.clientHeight >= panel.scrollHeight - 3) {
      for (const row of bottomRows) {
        const key = `${seconds(row.at)}:${row.text}`;
        if (!seen.has(key)) seen.set(key, { ...row, order: seen.size });
      }
      atBottom = true;
    }
    if (!atBottom) panel.scrollTop = 0;
  }
  for (let step = 0; !atBottom && step < 500; step++) {
    const visible = parse(panel.innerText || '');
    for (const row of visible) {
      const key = `${seconds(row.at)}:${row.text}`;
      if (!seen.has(key)) seen.set(key, { ...row, order: seen.size });
    }
    const before = panel.scrollTop;
    panel.scrollTop = Math.min(panel.scrollHeight, before + Math.max(250, panel.clientHeight * 0.7));
    await pause(350);
    const bottom = panel.scrollTop + panel.clientHeight >= panel.scrollHeight - 3;
    stable = panel.scrollTop === before ? stable + 1 : 0;
    if (step % 25 === 0) console.log(`Bản chép lời: ${seen.size} dòng, bước ${step}`);
    if (bottom && stable >= 2) {
      atBottom = true;
      break;
    }
  }
  const finalPanel = document.contains(panel) ? panel : findPanel();
  if (finalPanel) {
    finalPanel.scrollTop = finalPanel.scrollHeight;
    await pause(300);
    atBottom = finalPanel.scrollTop + finalPanel.clientHeight >= finalPanel.scrollHeight - 3;
  }
  for (const row of parse(finalPanel?.innerText || panel.innerText || '')) {
    const key = `${seconds(row.at)}:${row.text}`;
    if (!seen.has(key)) seen.set(key, { ...row, order: seen.size });
  }
  const rows = [...seen.values()]
    .sort((a, b) => seconds(a.at) - seconds(b.at) || a.order - b.order)
    .map(({ at, text }) => ({ at, text }));
  const result = {
    source: 'drive_ui', videoId, url: location.href,
    rowCount: rows.length, atBottom,
    startsNearZero: rows.length > 0 && seconds(rows[0].at) <= 5,
    rows,
  };
  if (!rows.length) throw new Error('Không đọc được dòng bản chép lời nào từ panel.');
  if (window.__getsubReturnResult === true) return result;
  const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `getsub-transcript-${videoId}.json`;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(link.href), 10000);
  console.log(`Đã tải JSON: ${rows.length} dòng; đến cuối panel: ${atBottom}; thấy mốc đầu: ${result.startsNearZero}`);
  return { rowCount: rows.length, atBottom, startsNearZero: result.startsNearZero };
})();
