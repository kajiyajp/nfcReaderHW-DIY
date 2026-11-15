# 作成日: 2026-11-15
# 目的: KiCadのシンボルライブラリ(.kicad_sym)を読む最小限のS式パーサとヘルパー

import os
import re

KICAD_DIR = os.environ.get("KICAD_DIR", r"C:\Users\kajiy\AppData\Local\Programs\KiCad\10.0")
SYM_DIR = os.path.join(KICAD_DIR, "share", "kicad", "symbols")
FP_DIR = os.path.join(KICAD_DIR, "share", "kicad", "footprints")

_TOKEN = re.compile(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()"]+')


# S式テキストをネストしたリストに変換する（文字列は引用符付きのまま保持）
def parse(text):
    stack = [[]]
    for m in _TOKEN.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append([])
        elif t == ")":
            node = stack.pop()
            stack[-1].append(node)
        else:
            stack[-1].append(t)
    return stack[0][0]


# ネストしたリストをS式テキストに戻す
def dump(node, indent=0):
    if not isinstance(node, list):
        return node
    if all(not isinstance(x, list) for x in node):
        return "(" + " ".join(node) + ")"
    pad = "\t" * (indent + 1)
    parts = [dump(x, indent + 1) for x in node]
    head = []
    while parts and not isinstance(node[len(head)], list):
        head.append(parts.pop(0))
    return "(" + " ".join(head) + "".join("\n" + pad + p for p in parts) + ")"


# 引用符を外す
def unq(s):
    return s[1:-1] if s.startswith('"') else s


_cache = {}


# ライブラリから指定シンボルのS式ノードを返す（extendsも解決）
def load_symbol(lib, name):
    if lib not in _cache:
        with open(os.path.join(SYM_DIR, lib + ".kicad_sym"), encoding="utf8") as f:
            _cache[lib] = {unq(n[1]): n for n in parse(f.read()) if isinstance(n, list) and n[0] == "symbol"}
    node = _cache[lib][name]
    ext = [x for x in node if isinstance(x, list) and x[0] == "extends"]
    if ext:
        base = load_symbol(lib, unq(ext[0][1]))
        merged = [base[0], node[1]]
        props = [x for x in node if isinstance(x, list) and x[0] == "property"]
        pnames = {unq(p[1]) for p in props}
        for x in base[2:]:
            if isinstance(x, list) and x[0] == "property" and unq(x[1]) in pnames:
                continue
            if isinstance(x, list) and x[0] == "symbol":
                x = [x[0], '"' + unq(x[1]).replace(unq(base[1]), name) + '"'] + x[2:]
            merged.append(x)
        merged[2:2] = props
        return merged
    return node


# シンボルのピン一覧 [(番号, 名前, 種別, x, y, 角度)] を返す（unit 0 と 1 のみ）
def pins(sym):
    out = []
    for sub in sym:
        if isinstance(sub, list) and sub[0] == "symbol":
            for p in sub:
                if isinstance(p, list) and p[0] == "pin":
                    at = next(x for x in p if isinstance(x, list) and x[0] == "at")
                    nm = next(x for x in p if isinstance(x, list) and x[0] == "name")
                    nu = next(x for x in p if isinstance(x, list) and x[0] == "number")
                    out.append((unq(nu[1]), unq(nm[1]), p[1], float(at[1]), float(at[2]), float(at[3]) if len(at) > 3 else 0.0))
    return out


# シンボルのプロパティ値を返す
def prop(sym, key):
    for x in sym:
        if isinstance(x, list) and x[0] == "property" and unq(x[1]) == key:
            return unq(x[2])
    return None
