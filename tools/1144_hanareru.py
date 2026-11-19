#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""1144番【切り離して走らせる】心臓が再起動しても死なない形で1本走らせる。

なぜ要るか（2026-09-25 実測）:
  心臓(tools/heartbeat.sh)は再起動のたびに自分のプロセスグループを kill -9 する。
  oneshot_runner.py は心臓の子なので、そこから起こした長い仕事も一緒に死ぬ。
  ( nohup ... & ) でも同じグループのままなので死ぬ。macOS に setsid は無い。
  → os.setsid() で**新しいセッション**に移してから exec する。これで心臓と縁が切れる。

使い方:
  python3 tools/1144_hanareru.py <出力ファイル> <コマンド...>
"""
import os, sys

def main():
    outpath, cmd = sys.argv[1], sys.argv[2:]
    if os.fork() != 0:
        return 0                      # 親はすぐ帰る（心臓を待たせない）
    os.setsid()                       # ★ここで心臓のプロセスグループから抜ける
    if os.fork() != 0:
        os._exit(0)
    fd = os.open(os.devnull, os.O_RDONLY); os.dup2(fd, 0)
    fd = os.open(outpath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
    os.dup2(fd, 1); os.dup2(fd, 2)
    os.execvp(cmd[0], cmd)

if __name__ == "__main__":
    sys.exit(main())
