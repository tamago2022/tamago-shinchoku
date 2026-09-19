#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""959ページから system instructions と道具の定義をそのまま抜いて 967_brain_prompt.md を作り直す。
手で写すと必ずズレるので、ここで機械的に抜く。"""
import re, json, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
src = (R/"share/check/959-gemini-live-tamago.html").read_text(encoding="utf-8")
inst = "\n".join(json.loads("[" + re.search(r"const INSTRUCTIONS=\[(.*?)\]\.join", src, re.S).group(1).strip().rstrip(",") + "]"))
schema = re.search(r"new FunctionCallDefinition\((.*?)\n  \);", src, re.S).group(1)
(R/"tools/967_brain_prompt.md").write_text(
    "# 967 覆面調査員：案内人の頭（たまこ）の代役に渡す指示\n\n"
    "これは 959 ページから**そのまま抜き出した**もの。手で書き写さない。\n"
    "再生成： python3 tools/967_build_brain_prompt.py\n\n"
    "## 案内人に渡されている指示文（system instructions・原文まま）\n\n```\n" + inst + "\n```\n\n"
    "## 案内人が呼べる道具（原文まま）\n\n```js\nnew FunctionCallDefinition(" + schema + "\n  );\n```\n",
    encoding="utf-8")
print("ok")
