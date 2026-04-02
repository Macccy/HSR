# -*- coding: utf-8 -*-
"""測試 Hakush.in 技能圖標的實際 URL（依 Network 看到的檔名）"""
import requests
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 從角色頁 Network 看到的檔名（你截圖中的）
icons = [
    "SkillIcon_1501_Normal.webp",
    "SkillIcon_1501_BP.webp",
    "SkillIcon_1501_Ultra.webp",
    "SkillIcon_1501_Passive.webp",
    "SkillIcon_1501_Maze.webp",
    "SkillIcon_1501_SkillTree1.webp",
    "SkillIcon_1501_SkillTree2.webp",
    "SkillIcon_1501_SkillTree3.webp",
    "SkillIcon_1501_Elation.webp",
]

# 可能的前綴（api.hakush.in 與 hsr20.hakush.in 各種路徑）
bases = [
    "https://api.hakush.in/hsr/UI/avatarskillicon/_dependencies/textures/1501/",
    "https://api.hakush.in/hsr/UI/skillicon/_dependencies/textures/1501/",
    "https://api.hakush.in/hsr/UI/skill/_dependencies/textures/1501/",
    "https://api.hakush.in/hsr/UI/avatarskillicon/",
    "https://api.hakush.in/hsr/UI/skillicon/",
    "https://api.hakush.in/hsr/UI/skill/",
    "https://hsr20.hakush.in/assets/",
    "https://hsr20.hakush.in/char/assets/",
    "https://hsr20.hakush.in/_app/immutable/",
    "https://hsr20.hakush.in/",
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'image/webp,image/*,*/*;q=0.8',
    'Referer': 'https://hsr20.hakush.in/',
}

# 只測第一個圖標，找到可用的 base 再報
test_icon = icons[0]
print("測試 SkillIcon URL（第一個圖標）:", test_icon)
print("=" * 70)

# 加上與角色頁一致的 Referer
headers['Referer'] = 'https://hsr20.hakush.in/char/1501'

for base in bases:
    url = base + test_icon
    try:
        r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
        if r.status_code == 200:
            ct = r.headers.get('content-type', '')
            size = len(r.content)
            # 檢查是否為真實圖片
            ok = size >= 500 and (b'RIFF' == r.content[:4] or r.content[:8] == b'\x89PNG\r\n\x1a\n')
            print("OK [200]" if ok else "200 but not image", url)
            print("  -> content-type:", ct, " size:", size, " valid_image:", ok)
        else:
            print("[%d]" % r.status_code, url[:75] + "...")
    except Exception as e:
        print("ERR", url[:60] + "...", str(e)[:30])

print("\n若無 OK，請在 Network 裡對任一 SkillIcon 請求右鍵 -> Copy -> Copy link address 貼給我。")
