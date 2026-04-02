# -*- coding: utf-8 -*-
"""Analyze Gachabase character page for image URL patterns."""
import re
import json
import requests

URL = "https://hsr.gachabase.net/characters/1502/yao-guang/beta?lang=en"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0",
    "Accept-Language": "en-US,en;q=0.9",
}

def main():
    r = requests.get(URL, headers=HEADERS, timeout=45)
    r.raise_for_status()
    t = r.text
    print("Page length:", len(t))

    # 1) application/json script blocks (SvelteKit)
    json_blocks = re.findall(
        r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>',
        t,
        re.DOTALL,
    )
    print("application/json script count:", len(json_blocks))
    for i, block in enumerate(json_blocks):
        if len(block) < 200:
            continue
        # try parse
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        s = json.dumps(data)[:5000]
        if "cdn.gachabase" in s or "img.gachabase" in s or "assets/" in s or "1502" in s:
            print(f"\n--- Block {i} (len {len(block)}) preview ---")
            print(s[:3000])

    # 2) Inline data: [...] pattern seen before
    m = re.search(r'data:\s*\[\{type:"data"', t)
    if m:
        print("\nFound data: [{type:data ...")

    # 3) All unique asset hashes with short context
    pat = r'(https://(?:cdn|img)\.gachabase\.net/[^"\s<>]+)'
    urls = sorted(set(re.findall(pat, t)))
    print("\nUnique gachabase image URLs:", len(urls))

    # 4) For each URL, show 120 chars before in HTML (once)
    for u in urls[:15]:
        idx = t.find(u)
        ctx = t[max(0, idx - 150) : idx + len(u) + 80].replace("\n", " ")
        print("\nCTX:", ctx[:280])

    # 5) Parse all data-preview-group + data-preview-src pairs
    groups = {}
    for m in re.finditer(
        r'data-preview-group="([^"]+)"[^>]*data-preview-src="(https://cdn\.gachabase\.net/hsr/assets/[a-f0-9]{32}\.png)"',
        t,
    ):
        g, u = m.group(1), m.group(2)
        groups.setdefault(g, []).append(u)
    print("\n=== By data-preview-group (unique URLs per group) ===")
    for g, lst in sorted(groups.items()):
        uniq = []
        for x in lst:
            if x not in uniq:
                uniq.append(x)
        print(f"  {g}: {len(uniq)} images")
        for u in uniq[:8]:
            print(f"    {u.split('/')[-1]}")

    # 6) Check if hash is MD5 of known path (sample)
    import hashlib
    test_paths = [
        "SpriteOutput/SkillIcon/SkillIcon_1502_Normal.png",
        "SpriteOutput/SkillIcon/SkillIcon_1502_BP.png",
        "SpriteOutput/SkillIcon/SkillIcon_1502_Ultra.png",
        "SpriteOutput/SkillIcon/SkillIcon_1502_Passive.png",
        "SpriteOutput/SkillIcon/SkillIcon_1502_Maze.png",
    ]
    sample_hash = "10d8bd17c7c86398deda1a95f83c7c90"
    print("\n=== MD5 guess (first skill icon hash vs common paths) ===")
    for p in test_paths:
        h = hashlib.md5(p.encode()).hexdigest()
        print(f"  md5({p}) = {h} {'MATCH' if h == sample_hash else ''}")

    # 7) Snippet around "Whistlebolt" or skill id
    for needle in ["Whistlebolt", "1502", "skill_icon", "SkillIcon"]:
        i = t.find(needle)
        if i != -1:
            snip = t[max(0, i - 80) : i + 120].replace("\n", " ")
            print(f"\nNear {needle!r}: {snip[:240]}")

if __name__ == "__main__":
    main()
