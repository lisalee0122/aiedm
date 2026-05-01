#!/usr/bin/env python3
"""寄送 EDM 測試信。

用法：
  SMTP_USER=your@gmail.com SMTP_PASS=app_password \\
  TO=test@example.com python3 send_test.py

行為：
  - 讀取 index.html，把 <img src="img/xxx"> 改寫為 cid: 內嵌
  - 圖片以 multipart/related 方式附加在信件中（Outlook / Gmail / Mail.app 皆支援）
  - 預設走 Gmail SMTP（smtp.gmail.com:587），可用環境變數覆寫
"""

import os
import re
import smtplib
import ssl
import sys
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

ROOT = Path(__file__).parent
HTML_PATH = ROOT / "index.html"
IMG_DIR = ROOT / "img"

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER")
SMTP_PASS = os.environ.get("SMTP_PASS")
MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USER)
MAIL_TO = os.environ.get("TO")
SUBJECT = os.environ.get("SUBJECT", "Savitech 週刊｜2026 年 5 月號：如何有效使用 GitHub Copilot")


def build_message() -> EmailMessage:
    if not (SMTP_USER and SMTP_PASS and MAIL_TO):
        sys.exit("缺少必要環境變數：SMTP_USER / SMTP_PASS / TO")

    html = HTML_PATH.read_text(encoding="utf-8")

    # 為每個 img/xxx 產生 cid，並把 HTML 中的相對路徑替換成 cid:xxx
    used = {}
    def replace(match: re.Match) -> str:
        rel_path = match.group(2)
        filename = Path(rel_path).name
        if filename not in used:
            cid = make_msgid(domain="edm.local")[1:-1]  # 去除 < >
            used[filename] = cid
        return f'{match.group(1)}cid:{used[filename]}{match.group(3)}'

    pattern = re.compile(r'(src=["\'])img/([^"\']+)(["\'])')
    html_cid = pattern.sub(replace, html)

    msg = EmailMessage()
    msg["Subject"] = SUBJECT
    msg["From"] = MAIL_FROM
    msg["To"] = MAIL_TO
    # Outlook 純文字 fallback（給沒法看 HTML 的客戶端 / 反垃圾分數）
    msg.set_content(
        "本信件為 HTML 格式。如果無法正常顯示，請使用支援 HTML 的郵件用戶端開啟。\n"
        "2026 年 5 月號 · Issue 01 — 如何有效使用 GitHub Copilot"
    )
    msg.add_alternative(html_cid, subtype="html")

    # 把圖片附加到 HTML alternative（multipart/related）
    html_part = msg.get_payload()[1]
    for filename, cid in used.items():
        img_path = IMG_DIR / filename
        if not img_path.exists():
            sys.exit(f"找不到圖片：{img_path}")
        ext = img_path.suffix.lower().lstrip(".")
        subtype = "jpeg" if ext in ("jpg", "jpeg") else ext
        with img_path.open("rb") as f:
            html_part.add_related(
                f.read(),
                maintype="image",
                subtype=subtype,
                cid=f"<{cid}>",
                filename=filename,
            )
    return msg


def send(msg: EmailMessage) -> None:
    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.ehlo()
        s.starttls(context=context)
        s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)
    print(f"已寄出 → {MAIL_TO}（from {MAIL_FROM} via {SMTP_HOST}:{SMTP_PORT}）")


if __name__ == "__main__":
    send(build_message())
