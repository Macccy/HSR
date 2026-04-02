# -*- coding: utf-8 -*-
"""檢查各來源實際回傳的 Content-Type 與前幾 bytes"""
import requests
import sys
sys.stdout.reconfigure(encoding='utf-8')

urls = [
    ("HHW skill", "https://starrail.honeyhunterworld.com/img/character/cat-got-your-flametongue-skill_icon.webp"),
    ("HHW eidolon", "https://starrail.honeyhunterworld.com/img/character/goingviral-whoisshe-eidolon_icon.webp"),
    ("Hakush rank", "https://api.hakush.in/hsr/UI/rank/_dependencies/textures/1501/1501_Rank_1.webp"),
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'image/webp,image/*,*/*;q=0.8',
    'Referer': 'https://starrail.honeyhunterworld.com/',
}

for name, url in urls:
    try:
        r = requests.get(url, headers=headers, timeout=15)
        ct = r.headers.get('content-type', '')
        size = len(r.content)
        # WebP 檔案開頭是 RIFF....WEBP
        start = r.content[:20] if size >= 20 else r.content
        is_webp = start[:4] == b'RIFF' and b'WEBP' in start[:12]
        is_html = b'<!' in start or b'<html' in start.lower()
        print(f"{name}:")
        print(f"  status={r.status_code} content-type={ct} size={size}")
        print(f"  is_webp={is_webp} is_html={is_html} start={start[:12]}")
    except Exception as e:
        print(f"{name}: error {e}")
    print()
