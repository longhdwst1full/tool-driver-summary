#!/usr/bin/env python3
"""Capture a Drive video's visible transcript in a private headless Chrome session."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

import websocket


ROOT = Path(__file__).resolve().parent.parent
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{10,}$")
PROFILE_ITEMS = ("Cookies", "Cookies-journal", "Preferences", "Secure Preferences",
                 "Web Data", "Local Storage", "IndexedDB")


class CDP:
    def __init__(self, socket_url: str):
        self.socket = websocket.create_connection(socket_url, timeout=240, suppress_origin=True)
        self.next_id = 0

    def close(self) -> None:
        self.socket.close()

    def call(self, method: str, params: dict | None = None) -> dict:
        self.next_id += 1
        request_id = self.next_id
        self.socket.send(json.dumps({"id": request_id, "method": method,
                                     "params": params or {}}))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"Chrome DevTools: {message['error'].get('message')}")
                return message.get("result", {})

    def evaluate(self, expression: str, *, await_promise: bool = False) -> object:
        result = self.call("Runtime.evaluate", {"expression": expression,
                           "awaitPromise": await_promise, "returnByValue": True,
                           "userGesture": True})
        if "exceptionDetails" in result:
            exception = result["exceptionDetails"]
            raise RuntimeError(exception.get("exception", {}).get("description")
                               or exception.get("text", "Lỗi JavaScript trong Drive"))
        return result.get("result", {}).get("value")


def clone_profile(source: Path, target: Path, profile_name: str) -> None:
    source_profile = source / profile_name
    if not (source / "Local State").is_file() or not source_profile.is_dir():
        raise FileNotFoundError(f"Không tìm thấy Chrome profile {profile_name}")
    shutil.copy2(source / "Local State", target / "Local State")
    destination = target / profile_name
    destination.mkdir(mode=0o700)
    for name in PROFILE_ITEMS:
        item = source_profile / name
        if not item.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, destination / name)
        else:
            shutil.copy2(item, destination / name)


def capture(video_id: str, profile_source: Path, profile_name: str) -> dict:
    with tempfile.TemporaryDirectory(prefix="getsub-private-") as directory:
        temporary = Path(directory)
        os.chmod(temporary, 0o700)
        clone_profile(profile_source, temporary, profile_name)
        log = (temporary / "chrome.log").open("wb")
        process = subprocess.Popen([
            "google-chrome", "--headless=new", "--mute-audio", "--disable-extensions",
            "--disable-sync", "--no-first-run", "--no-default-browser-check",
            "--remote-debugging-port=0", f"--user-data-dir={temporary}",
            f"--profile-directory={profile_name}", "about:blank",
        ], stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            port_file = temporary / "DevToolsActivePort"
            for _ in range(100):
                if port_file.is_file():
                    break
                if process.poll() is not None:
                    raise RuntimeError("Chrome chạy ngầm đã thoát trước khi mở DevTools")
                time.sleep(0.1)
            else:
                raise TimeoutError("Chrome chạy ngầm không mở DevTools")
            port = port_file.read_text().splitlines()[0]
            base = f"http://127.0.0.1:{port}"
            video_url = f"https://drive.google.com/file/d/{video_id}/view"
            request = Request(base + "/json/new?" + quote(video_url, safe=""), method="PUT")
            with urlopen(request, timeout=10) as response:
                target = json.load(response)
            client = CDP(target["webSocketDebuggerUrl"])
            try:
                for _ in range(60):
                    state = client.evaluate('''(() => ({
                      title: document.title,
                      play: [...document.querySelectorAll('button')]
                        .some(e => !e.disabled && /phát|play/i.test(e.getAttribute('aria-label') || ''))
                    }))()''')
                    if isinstance(state, dict) and state.get("play"):
                        break
                    time.sleep(0.5)
                else:
                    raise TimeoutError("Video không mở được trong Chrome chạy ngầm")
                client.evaluate('''(() => {
                  const button = [...document.querySelectorAll('button')]
                    .find(e => !e.disabled && /phát|play/i.test(e.getAttribute('aria-label') || ''));
                  button?.click();
                  return !!button;
                })()''')
                for attempt in range(60):
                    ready = client.evaluate('''(() => {
                      const button = [...document.querySelectorAll('button')]
                        .find(e => /bản chép lời|transcript/i.test(e.innerText || ''));
                      return !!button && !button.disabled;
                    })()''')
                    if ready:
                        break
                    if attempt and attempt % 10 == 0:
                        client.evaluate('''(() => {
                          const button = [...document.querySelectorAll('button')]
                            .find(e => !e.disabled && /phát|play/i.test(e.getAttribute('aria-label') || ''));
                          button?.click();
                        })()''')
                    time.sleep(0.5)
                else:
                    raise TimeoutError("Bản chép lời không khả dụng trong phiên Chrome này")
                client.evaluate('''(() => {
                  const button = [...document.querySelectorAll('button')]
                    .find(e => /bản chép lời|transcript/i.test(e.innerText || ''));
                  button?.click();
                  return !!button;
                })()''')
                for _ in range(60):
                    count = client.evaluate('''(() => [...document.querySelectorAll('*')]
                      .filter(e => e.scrollHeight - e.clientHeight > 100
                        && e.getBoundingClientRect().left > innerWidth * .4
                        && (e.innerText || '').match(/(?:^|\\n)\\s*\\d{1,2}:\\d{2}/g)?.length > 2)
                      .length)()''')
                    if count:
                        break
                    time.sleep(0.5)
                else:
                    raise TimeoutError("Panel bản chép lời không hiện dòng có thời gian")
                source = (ROOT / "browser-demo" / "console-transcript.js").read_text()
                for attempt in range(3):
                    result = client.evaluate("window.__getsubReturnResult = true;\n" + source,
                                             await_promise=True)
                    if not isinstance(result, dict) or result.get("videoId") != video_id:
                        raise ValueError("Bản thu không khớp video yêu cầu")
                    if (result.get("atBottom") and result.get("startsNearZero")
                            and result.get("rowCount", 0) >= 2):
                        return result
                    if attempt < 2:
                        time.sleep(1)
                raise ValueError("Panel bản chép lời chưa đủ mốc đầu/cuối sau 3 lần đọc")
            finally:
                client.close()
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait()
            log.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Thu bản chép lời Drive không chiếm cửa sổ đang dùng")
    parser.add_argument("--video-id", required=True)
    parser.add_argument("--profile-source", type=Path,
                        default=Path.home() / ".config/google-chrome")
    parser.add_argument("--profile-name", default="Default")
    parser.add_argument("--ai", action="store_true", help="Tạo ghi chú bằng Codex sau khi nhập")
    args = parser.parse_args()
    if not VIDEO_ID.fullmatch(args.video_id) or "/" in args.profile_name or args.profile_name.startswith("."):
        parser.error("ID video hoặc tên profile không hợp lệ")
    try:
        result = capture(args.video_id, args.profile_source, args.profile_name)
        with tempfile.TemporaryDirectory(prefix="getsub-import-") as directory:
            path = Path(directory) / f"getsub-transcript-{args.video_id}.json"
            path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            subprocess.run([sys.executable, str(ROOT / "import_ui_transcript.py"), str(path)],
                           cwd=ROOT, check=True)
        print(f"Đã thu {result['rowCount']} dòng; cuối panel: {result['atBottom']}", flush=True)
        if args.ai:
            subprocess.run([sys.executable, str(ROOT / "progressive_demo.py"),
                            "--ui-video-id", args.video_id], cwd=ROOT, check=True)
        return 0
    except (OSError, ValueError, RuntimeError, TimeoutError, subprocess.CalledProcessError) as exc:
        print(f"Lỗi thu ngầm: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
