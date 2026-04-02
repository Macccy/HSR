# -*- coding: utf-8 -*-
"""無頭環境依 all_json.csv 重寫 all_skill_silder.txt（需 PyQt6）。"""
from __future__ import annotations

import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, SCRIPT_DIR)


def main() -> None:
    from PyQt6.QtWidgets import QApplication

    from skill_viewer import SkillViewer

    app = QApplication([])
    w = SkillViewer()
    csv_path = os.path.join(SCRIPT_DIR, "all_json.csv")
    w.skill_data = w.read_skills_from_csv(csv_path)
    out = os.path.join(SCRIPT_DIR, "all_skill_silder.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(w.get_all_skill_silder_html())
    print("寫入", out)
    app.quit()


if __name__ == "__main__":
    main()
