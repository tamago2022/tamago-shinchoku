#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""既定のオーディオ入出力を名前で切り替える（CoreAudio直叩き・許可ダイアログ不要）。

使い方:
  python3 audio_switch.py --list
  python3 audio_switch.py --out "複数出力装置" --in "BlackHole 2ch"
  python3 audio_switch.py --show
"""
import argparse
import ctypes
import ctypes.util
import sys

ca = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreAudio"))
cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))

cf.CFStringCreateWithCString.restype = ctypes.c_void_p
cf.CFStringCreateWithCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_uint32]
cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
cf.CFRelease.argtypes = [ctypes.c_void_p]

kCFStringEncodingUTF8 = 0x08000100
kAudioObjectSystemObject = 1


def fourcc(s):
    return (ord(s[0]) << 24) | (ord(s[1]) << 16) | (ord(s[2]) << 8) | ord(s[3])


GLOBAL = fourcc("glob")
DEVICES = fourcc("dev#")
DEF_IN = fourcc("dIn ")
DEF_OUT = fourcc("dOut")
NAME = fourcc("lnam")
STREAMS = fourcc("stm#")
SCOPE_IN = fourcc("inpt")
SCOPE_OUT = fourcc("outp")


class Addr(ctypes.Structure):
    _fields_ = [("mSelector", ctypes.c_uint32),
                ("mScope", ctypes.c_uint32),
                ("mElement", ctypes.c_uint32)]


def get_size(obj, sel, scope=GLOBAL):
    size = ctypes.c_uint32(0)
    a = Addr(sel, scope, 0)
    r = ca.AudioObjectGetPropertyDataSize(ctypes.c_uint32(obj), ctypes.byref(a),
                                          0, None, ctypes.byref(size))
    return size.value if r == 0 else 0


def device_ids():
    n = get_size(kAudioObjectSystemObject, DEVICES) // 4
    buf = (ctypes.c_uint32 * n)()
    size = ctypes.c_uint32(n * 4)
    a = Addr(DEVICES, GLOBAL, 0)
    ca.AudioObjectGetPropertyData(ctypes.c_uint32(kAudioObjectSystemObject),
                                  ctypes.byref(a), 0, None,
                                  ctypes.byref(size), ctypes.byref(buf))
    return list(buf)


def dev_name(dev):
    ref = ctypes.c_void_p()
    size = ctypes.c_uint32(ctypes.sizeof(ctypes.c_void_p))
    a = Addr(NAME, GLOBAL, 0)
    r = ca.AudioObjectGetPropertyData(ctypes.c_uint32(dev), ctypes.byref(a), 0, None,
                                      ctypes.byref(size), ctypes.byref(ref))
    if r != 0 or not ref.value:
        return ""
    out = ctypes.create_string_buffer(512)
    ok = cf.CFStringGetCString(ref.value, out, 512, kCFStringEncodingUTF8)
    cf.CFRelease(ref.value)
    return out.value.decode("utf-8", "replace") if ok else ""


def has_streams(dev, scope):
    return get_size(dev, STREAMS, scope) > 0


def get_default(sel):
    d = ctypes.c_uint32(0)
    size = ctypes.c_uint32(4)
    a = Addr(sel, GLOBAL, 0)
    ca.AudioObjectGetPropertyData(ctypes.c_uint32(kAudioObjectSystemObject),
                                  ctypes.byref(a), 0, None,
                                  ctypes.byref(size), ctypes.byref(d))
    return d.value


def set_default(sel, dev):
    d = ctypes.c_uint32(dev)
    a = Addr(sel, GLOBAL, 0)
    return ca.AudioObjectSetPropertyData(ctypes.c_uint32(kAudioObjectSystemObject),
                                         ctypes.byref(a), 0, None,
                                         ctypes.c_uint32(4), ctypes.byref(d))


def find(name, want_input):
    for d in device_ids():
        if dev_name(d) == name:
            if want_input and not has_streams(d, SCOPE_IN):
                continue
            if (not want_input) and not has_streams(d, SCOPE_OUT):
                continue
            return d
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--list", action="store_true")
    p.add_argument("--show", action="store_true")
    p.add_argument("--out")
    p.add_argument("--in", dest="inp")
    args = p.parse_args()

    if args.list:
        for d in device_ids():
            print("%-32s in=%s out=%s" % (dev_name(d), has_streams(d, SCOPE_IN),
                                          has_streams(d, SCOPE_OUT)))
        return 0
    if args.show:
        print("OUT=%s" % dev_name(get_default(DEF_OUT)))
        print("IN=%s" % dev_name(get_default(DEF_IN)))
        return 0

    rc = 0
    if args.out:
        d = find(args.out, False)
        if d is None:
            print("出力が見つからない: %s" % args.out); rc = 2
        else:
            print("OUT -> %s (%s)" % (args.out, set_default(DEF_OUT, d)))
    if args.inp:
        d = find(args.inp, True)
        if d is None:
            print("入力が見つからない: %s" % args.inp); rc = 2
        else:
            print("IN  -> %s (%s)" % (args.inp, set_default(DEF_IN, d)))
    return rc


if __name__ == "__main__":
    sys.exit(main())
