#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lovable への書き込み全面禁止（憲法・2026-10-22・たまごさん厳命「Lovableに勝手に書き込むな。厳格に禁止」）。

きっかけ：2026-10-10 21:30:33 JST、Lovable プロジェクト 8ebdb648-… のチャットに
「新しい特集記事ページを1本作ってください（オーナー承認済み）…/feature/ekkyo…」という
依頼文が送られ、Lovable 側が TalkingAvatar.tsx を1行書き換えた（edt-39674bff-…）。

決まり：AI（Claude・Codex・ChatGPT・Genspark・Grokボット・工場の道具すべて）は
  Lovable のチャット（send_message）・エディタ入力・API による書き込みを一切しない。
  許されるのは「読む」（get_*／list_*／read_file／get_diff／SELECT だけの query_database）と
  「公開を押す」deploy_project だけ。コードの変更は GitHub へ push する。

使い方（工場のコードから）：
  import lovable_kinshi; lovable_kinshi.mamoru("tools/call", {"name": ..., "arguments": ...})
  → 禁止の道具なら LovableKinshi を投げる（呼ぶ前に止まる）。
逆テスト：python3 tools/lovable_kinshi.py --self-test
関所（セッション側）：tools/stop_kanmon/lovable_kakikomi_kinshi.mjs（同じ白名簿）
"""
import json
import os
import re
import sys
import time

# 読むだけの道具と、公開ボタン。これ以外は全部呼ばない。
YURUSU = {
    "deploy_project",
    "get_project", "get_me", "get_workspace", "get_message", "get_diff",
    "get_database_status", "get_project_analytics", "get_project_analytics_trend",
    "get_project_knowledge", "get_workspace_knowledge", "get_workspace_skill",
    "list_projects", "list_workspaces", "list_messages", "list_edits", "list_files",
    "list_connectors", "list_custom_connectors", "list_design_systems",
    "list_template_projects", "list_workspace_skills",
    "read_file", "query_database", "render_project_widget",
}
SQL_YOMU = re.compile(r"^\s*(select|with|explain|show)\b", re.I)
SQL_KAKU = re.compile(r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke|merge|upsert)\b", re.I)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAICHO = os.path.join(REPO, "status", "lovable_kinshi.jsonl")


class LovableKinshi(RuntimeError):
    pass


def handan(name, args=None):
    """(ok, 理由)。name は道具名（接頭辞つきでも可）。"""
    n = (name or "").split("__")[-1]
    if n not in YURUSU:
        return False, "Lovableへの書き込みは全面禁止（%s）。許されるのは読む道具と deploy_project だけ" % n
    if n == "query_database":
        sql = str((args or {}).get("sql") or (args or {}).get("query") or "")
        if not SQL_YOMU.search(sql) or SQL_KAKU.search(sql):
            return False, "query_database は読むSQL（SELECT）だけ。書き込みSQLは禁止"
    return True, ""


def mamoru(method, params=None):
    if method != "tools/call":
        return
    p = params or {}
    ok, why = handan(p.get("name"), p.get("arguments"))
    if not ok:
        try:
            with open(DAICHO, "a") as f:
                f.write(json.dumps({"at": time.strftime("%F %T"), "name": p.get("name"),
                                    "why": why, "argv": sys.argv[:3]}, ensure_ascii=False) + "\n")
        except Exception:
            pass
        raise LovableKinshi(why)


def _self_test():
    ng = [("send_message", {"project_id": "x", "message": "作って"}),
          ("mcp__lovable__send_message", {}), ("create_project", {}), ("remix_project", {}),
          ("set_project_knowledge", {}), ("respond_to_approval", {}),
          ("query_database", {"sql": "update songs set x=1"}),
          ("query_database", {"sql": "with a as (select 1) delete from t"})]
    ok = [("deploy_project", {"project_id": "x"}), ("get_project", {}), ("list_edits", {}),
          ("query_database", {"sql": "select * from songs limit 1"})]
    bad = 0
    for n, a in ng:
        if handan(n, a)[0]:
            print("NG のはずが通った:", n); bad += 1
    for n, a in ok:
        if not handan(n, a)[0]:
            print("OK のはずが止まった:", n); bad += 1
    try:
        mamoru("tools/call", {"name": "send_message", "arguments": {}})
        print("mamoru が send_message を止めない"); bad += 1
    except LovableKinshi:
        pass
    print("lovable_kinshi self-test:", "PASS" if not bad else "FAIL %d" % bad)
    return 0 if not bad else 1


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(_self_test())
    print(__doc__)
