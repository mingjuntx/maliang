#!/usr/bin/env python3
"""马良 · 小红书小工具 zip 自检（不依赖官方 skill）。

用法:  python3 scripts/check_xhs_zip.py tool.zip
退出码: 0 = 通过（可能有提醒），1 = 有必须修的问题。

检查的是马良实战中踩过的上传 / 审核规则，以官方最新文档为准。
拿到官方打包校验 skill 时，上传前再用官方脚本跑一遍。
"""
import re
import sys
import zipfile

MiB = 1024 * 1024
ALLOWED = {'html', 'css', 'js', 'json', 'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'woff', 'woff2'}
TEXT = {'html', 'css', 'js', 'json', 'svg'}

# (正则, 说明)：出现就算错误
BANNED_JS = [
    (r'\bfetch\s*\(', '不能联网：fetch('),
    (r'\bXMLHttpRequest\b', '不能联网：XMLHttpRequest'),
    (r'\bWebAssembly\s*\.', '不能用 WebAssembly'),
    (r'\bnew\s+Worker\s*\(', '不能用 Web Worker'),
    (r'(?<![\w.])eval\s*\(', '不能用 eval'),
    (r'\bnew\s+Function\s*\(', '不能用 new Function'),
    (r'\bwindow\.open\s*\(', '不能外跳：window.open'),
    (r'\bDeviceOrientation', '不能用 DeviceOrientation，改用平台陀螺仪'),
    (r'(?<![\w.$])(?<!async )import\s*\(', '不能动态 import('),
]
BANNED_HTML = [
    (r'<script(?![^>]*\bsrc=)[^>]*>\s*\S', '不能有内联脚本，脚本放进 .js 文件'),
    (r'<script[^>]*type\s*=\s*["\']module', '不能用 type="module"'),
    (r'\son[a-z]+\s*=\s*["\']', '不能在 HTML 上写 onclick 这类事件属性，改用 addEventListener'),
    (r'<a[^>]*\sdownload\b', '不能用 a[download]'),
    (r'target\s*=\s*["\']_blank', '不能用 target=_blank'),
    (r'(?:src|href)\s*=\s*["\']https?://', '不能引用外链资源'),
]
# (正则, 说明)：出现就提醒（兼容基线：ES2017 / Chrome 61）
WARN_JS = [
    (r'\?\.(?!\d)[A-Za-z_$\[(]', '可选链 ?. 超出 ES2017，老机型会报错'),
    (r'\?\?(?!=)', '空值合并 ?? 超出 ES2017'),
    (r'\.onclick\s*=', 'el.onclick = 容易被扫描误判，改用 addEventListener'),
]
WARN_CSS = [
    (r'(?<![\w-])gap\s*:', 'flex gap 在 Chrome 61 不生效'),
    (r'(?<![\w-])inset\s*:', 'inset 在 Chrome 61 不生效'),
    (r'aspect-ratio\s*:', 'aspect-ratio 在 Chrome 61 不生效'),
    (r'url\(\s*["\']?https?://', 'CSS 里不能引用外链资源'),
]


def strip_comments(src, ext):
    if ext in ('js', 'css'):
        src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)
    if ext == 'js':
        # 粗略去掉 // 注释（不处理字符串里的 //，误判时人工看一眼）
        src = re.sub(r'(?<![:\'"\\])//[^\n]*', '', src)
    if ext == 'html':
        src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    return src


def main(path):
    errors, warns = [], []
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:
        print('打不开 zip：', e)
        return 1
    import os
    size = os.path.getsize(path)
    if size > 10 * MiB:
        errors.append('zip 超过 10MiB 上限（%.1fMiB）' % (size / MiB))
    elif size > 2 * MiB:
        warns.append('zip 超过推荐的 2MiB（%.1fMiB），打开会慢' % (size / MiB))
    names = z.namelist()
    if 'index.html' not in names:
        errors.append('zip 根目录没有 index.html（打包时要在工具目录里面执行 zip）')
    for n in names:
        if n.endswith('/'):
            warns.append('zip 里有目录条目 %s（打包加 -D 参数）' % n)
            continue
        base = n.rsplit('/', 1)[-1]
        if base.startswith('.') or '__MACOSX' in n:
            errors.append('多余的隐藏文件：%s' % n)
            continue
        ext = base.rsplit('.', 1)[-1].lower() if '.' in base else ''
        if ext not in ALLOWED:
            errors.append('不允许的文件类型：%s（README、txt、md 都不能放）' % n)
            continue
        info = z.getinfo(n)
        if ext in TEXT and info.file_size > 2 * MiB:
            warns.append('文本文件超过 2MiB：%s（%.1fMiB）' % (n, info.file_size / MiB))
        if ext not in TEXT:
            continue
        src = strip_comments(z.read(n).decode('utf-8', 'replace'), ext)
        rules = []
        if ext == 'js':
            rules = [(r, m, errors) for r, m in BANNED_JS] + [(r, m, warns) for r, m in WARN_JS]
        elif ext == 'html':
            rules = [(r, m, errors) for r, m in BANNED_HTML]
        elif ext == 'css':
            rules = [(r, m, warns) for r, m in WARN_CSS]
        for rx, msg, bucket in rules:
            hits = [m.start() for m in re.finditer(rx, src, flags=re.I if ext == 'html' else 0)]
            if hits:
                line = src.count('\n', 0, hits[0]) + 1
                bucket.append('%s　→ %s 第 %d 行附近（共 %d 处）' % (msg, n, line, len(hits)))
    print('马良 · 小红书小工具自检：%s（%d 个文件，%.0fKB）' % (path, len(names), size / 1024))
    for e in errors:
        print('  ✗', e)
    for w in warns:
        print('  !', w)
    if not errors:
        print('  ✓ 没有必须修的问题' + ('（有 %d 条提醒，看一眼）' % len(warns) if warns else ''))
    return 1 if errors else 0


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1]))
