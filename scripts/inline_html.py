"""马良 · 把工具目录打成一个自包含的 HTML，发成网页给用户在手机上试玩。
用法: python3 inline_html.py 工具目录 out.html
- <link rel=stylesheet href=...> 和 <script src=...> 都内联进来；
- 图片等其他文件不处理（马良的工具素材都是代码画的，一般没有）。
平台接口（存相册、发笔记、关注）在网页里会自动降级，玩法和手感都能试。
"""
import os
import re
import sys

src, out = sys.argv[1], sys.argv[2]
html = open(os.path.join(src, 'index.html'), encoding='utf-8').read()


def read(rel):
    return open(os.path.join(src, rel.lstrip('./')), encoding='utf-8').read()


html = re.sub(r'<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"[^>]*/?>', lambda m: '<style>\n' + read(m.group(1)) + '\n</style>', html)
html = re.sub(r'<script src="([^"]+)"></script>', lambda m: '<script>\n' + read(m.group(1)) + '\n</script>', html)
open(out, 'w', encoding='utf-8').write(html)
print('ok', out, '%.0f KB' % (len(html.encode('utf-8')) / 1024))
