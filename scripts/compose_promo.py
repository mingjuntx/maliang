"""马良 · 宣传片合成：深色舞台 + 手机机位 + 顶部字幕 + 合成配乐和交互音效 + 结尾图标卡。
用法: python3 compose_promo.py promo.json
promo.json 示例见 promo.example.json。录屏素材来自 harness.js record（rec.json + frames/）。
依赖: numpy, pillow, ffmpeg；中文字体默认 Noto Sans CJK，可在配置里改。
"""
import json, math, os, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

CFG = json.load(open(sys.argv[1]))
BASEDIR = os.path.dirname(os.path.abspath(sys.argv[1]))
P = lambda p: p if os.path.isabs(p) else os.path.join(BASEDIR, p)
D = P(CFG.get('rec_dir', '.')).rstrip('/') + '/'
OUT = P(CFG['out'])
ICON = P(CFG['icon'])
FPS = 30
CW, CH = 1080, 1920
FB = CFG.get('font_black', '/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc')
FBOLD = CFG.get('font_bold', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc')
FI = CFG.get('font_index', 2)  # Noto CJK 的 SC 子字体
F_CAP = ImageFont.truetype(FB, 76, index=FI)
F_TAG = ImageFont.truetype(FBOLD, 34, index=FI)
F_FOOT = ImageFont.truetype(FBOLD, 30, index=FI)
NAME = CFG['name']

rec = json.load(open(D + 'rec.json'))
t0 = rec['t0']
frames = [(n, ts - t0) for n, ts in rec['frames']]
ftimes = np.array([t for _, t in frames])
M = {m['key']: m['t'] for m in rec['marks']}
# 可选：微调某个镜头的起点（跳过空白帧、多停一会儿等）
for k, dv in CFG.get('mark_offsets', {}).items():
    M[k] += dv

# 段落：录屏起止 mark、目标时长、字幕、小标签
SEG = [(s['from'], s['to'], s['dur'], s['caption'], s.get('tag', '')) for s in CFG['segments']]
END_DUR = CFG.get('end_dur', 3.2)
pieces = []
o = 0.0
for a, b, dur, cap, tag in SEG:
    pieces.append((o, o + dur, M[a], M[b], cap, tag))
    o += dur
REC_END = o
TOTAL = REC_END + END_DUR
for p in pieces:
    print('%-26s %.2fx' % (p[4], (p[3] - p[2]) / (p[1] - p[0])))


def rec_time(t):
    for oa, ob, ra, rb, _, _ in pieces:
        if t < ob:
            return ra + (t - oa) / (ob - oa) * (rb - ra)
    return pieces[-1][3]


def out_time(r):
    for oa, ob, ra, rb, _, _ in pieces:
        if ra <= r < rb:
            return oa + (r - ra) / (rb - ra) * (ob - oa), (rb - ra) / (ob - oa)
    return None, None


# ---------- 背景 ----------
def background():
    y, x = np.mgrid[0:CH, 0:CW].astype(np.float32)
    img = np.zeros((CH, CW, 3), np.float32) + np.array([12, 10, 20], np.float32)
    for cx, cy, r, col in [(200, 520, 700, (120, 70, 220)), (900, 1250, 760, (230, 80, 160)), (520, 1700, 600, (60, 140, 230))]:
        d = np.sqrt((x - cx) ** 2 + (y - cy) ** 2) / r
        k = np.clip(1 - d, 0, 1) ** 2 * 0.45
        img += k[..., None] * np.array(col, np.float32)
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(im)
    for yy in range(14, CH, 30):
        for xx in range(14, CW, 30):
            dr.point((xx, yy), fill=(70, 60, 110))
    return im


BG = background()
SCR_H = 1330
SCR_W = int(SCR_H * 360 / 640)
SCR_X = (CW - SCR_W) // 2
SCR_Y = 420
BZ = 16


def rmask(w, h, r):
    m = Image.new('L', (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), r, fill=255)
    return m


MASK = rmask(SCR_W, SCR_H, 56)
BASE = BG.copy()
sh = Image.new('L', (CW, CH), 0)
ImageDraw.Draw(sh).rounded_rectangle((SCR_X - BZ, SCR_Y - BZ + 30, SCR_X + SCR_W + BZ, SCR_Y + SCR_H + BZ + 30), 72, fill=170)
BASE.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(36)))
ImageDraw.Draw(BASE).rounded_rectangle((SCR_X - BZ, SCR_Y - BZ, SCR_X + SCR_W + BZ, SCR_Y + SCR_H + BZ), 72, fill=(16, 15, 22), outline=(80, 76, 100), width=3)
fd = ImageDraw.Draw(BASE)
foot = CFG.get('footer', '小红书搜「%s」' % NAME)
w = fd.textlength(foot, font=F_FOOT)
fd.text(((CW - w) / 2, CH - 92), foot, font=F_FOOT, fill=(170, 160, 210))


def caption(img, text, tag, alpha):
    if alpha <= 0:
        return img
    layer = Image.new('RGBA', (CW, 420), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    tw = d.textlength(tag, font=F_TAG)
    px = (CW - tw) / 2 - 26
    d.rounded_rectangle((px, 118, px + tw + 52, 176), 29, fill=(255, 255, 255, 34))
    d.text(((CW - tw) / 2, 124), tag, font=F_TAG, fill=(220, 205, 255, 255))
    cw_ = d.textlength(text, font=F_CAP)
    font = F_CAP
    if cw_ > CW - 80:
        font = ImageFont.truetype(FB, int(76 * (CW - 80) / cw_), index=FI)
        cw_ = d.textlength(text, font=font)
    sh = Image.new('RGBA', (CW, 420), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text(((CW - cw_) / 2, 214), text, font=font, fill=(0, 0, 0, 170))
    layer = Image.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), layer)
    ImageDraw.Draw(layer).text(((CW - cw_) / 2, 206), text, font=font, fill=(255, 255, 255, 255))
    if alpha < 1:
        a = layer.split()[3].point(lambda v: int(v * alpha))
        layer.putalpha(a)
    img.paste(layer, (0, 0), layer)
    return img


cache = {}


def screen_at(r):
    i = int(np.searchsorted(ftimes, r, side='right')) - 1
    i = max(0, min(len(frames) - 1, i))
    n = frames[i][0]
    if n not in cache:
        if len(cache) > 40:
            cache.clear()
        cache[n] = Image.open(D + 'frames/' + n).convert('RGB').resize((SCR_W, SCR_H), Image.LANCZOS)
    return cache[n]


ICON_IM = Image.open(ICON).convert('RGB').resize((420, 420), Image.LANCZOS)
ICON_MASK = rmask(420, 420, 96)
F_END1 = ImageFont.truetype(FB, 92, index=FI)
F_END2 = ImageFont.truetype(FBOLD, 44, index=FI)


def end_card(t):
    k = min(1, t / 0.5)
    e = 1 - (1 - k) ** 3
    img = BG.copy()
    d = ImageDraw.Draw(img)
    s = int(420 * (0.85 + 0.15 * e))
    ic = ICON_IM.resize((s, s), Image.LANCZOS)
    mk = rmask(s, s, int(96 * s / 420)).point(lambda v: int(v * e))
    img.paste(ic, ((CW - s) // 2, 560 + (420 - s) // 2), mk)
    lay = Image.new('RGBA', (CW, CH), (0, 0, 0, 0))
    dl = ImageDraw.Draw(lay)
    for txt, font, y, col in [(NAME, F_END1, 1080, (255, 255, 255)), (CFG.get('end_line1', '小红书搜一搜，就能玩'), F_END2, 1210, (200, 190, 240)), (CFG.get('end_line2', ''), F_TAG, 1290, (160, 150, 200))]:
        w = dl.textlength(txt, font=font)
        dl.text(((CW - w) / 2, y), txt, font=font, fill=col + (int(255 * e),))
    img.paste(lay, (0, 0), lay)
    return img


# ---------- 视频 ----------
ff = subprocess.Popen(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (CW, CH), '-r', str(FPS), '-i', '-',
                       '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-pix_fmt', 'yuv420p', D + '_video.mp4'], stdin=subprocess.PIPE)
N = int(round(TOTAL * FPS))
for fi in range(N):
    t = fi / FPS
    if t < REC_END:
        img = BASE.copy()
        img.paste(screen_at(rec_time(t)), (SCR_X, SCR_Y), MASK)
        for oa, ob, ra, rb, cap, tag in pieces:
            if oa <= t < ob:
                a = min(1, (t - oa) / 0.18)
                caption(img, cap, tag, a)
        # 结尾前淡出
        if t > REC_END - 0.3:
            k = (t - (REC_END - 0.3)) / 0.3
            img = Image.blend(img, BG, k)
    else:
        img = end_card(t - REC_END)
    ff.stdin.write(img.tobytes())
ff.stdin.close()
ff.wait()

# ---------- 音频：配乐 + 交互音效 ----------
SR = 44100
L = int(TOTAL * SR) + SR
mix = np.zeros(L, np.float32)
tt = np.arange(L) / SR


def note(f):
    return 440.0 * 2 ** ((f - 69) / 12)


chords = [[60, 64, 67, 71], [57, 60, 64, 67], [53, 57, 60, 64], [55, 59, 62, 67]]
BAR = 2.0
pad = np.zeros(L, np.float32)
for ci in range(int(TOTAL / BAR) + 1):
    ch = chords[ci % 4]
    s0 = int(ci * BAR * SR)
    n = int(BAR * 1.15 * SR)
    seg = np.arange(n) / SR
    env = np.minimum(1, seg / 0.35) * np.exp(-seg * 0.6)
    w = np.zeros(n, np.float32)
    for m in ch:
        f = note(m)
        w += np.sin(2 * np.pi * f * seg) * 0.5 + np.sin(2 * np.pi * f * 2.003 * seg) * 0.12
    w = w * env / len(ch)
    e = min(L, s0 + n)
    pad[s0:e] += w[: e - s0]
    # 琶音
    for k in range(8):
        f = note(ch[k % 4] + 12 + (12 if k in (3, 7) else 0))
        p0 = s0 + int(k * BAR / 8 * SR)
        n2 = int(0.5 * SR)
        sg = np.arange(n2) / SR
        pl = np.sin(2 * np.pi * f * sg) * np.exp(-sg * 7) * 0.16
        e2 = min(L, p0 + n2)
        if p0 < L:
            pad[p0:e2] += pl[: e2 - p0]
# 低音
for ci in range(int(TOTAL / BAR) + 1):
    f = note(chords[ci % 4][0] - 24)
    for k in range(4):
        p0 = int((ci * BAR + k * BAR / 4) * SR)
        n2 = int(0.45 * SR)
        sg = np.arange(n2) / SR
        bs = np.sin(2 * np.pi * f * sg) * np.exp(-sg * 5) * 0.22
        e2 = min(L, p0 + n2)
        if p0 < L:
            pad[p0:e2] += bs[: e2 - p0]
fade = np.ones(L, np.float32)
fade[: int(0.6 * SR)] = np.linspace(0, 1, int(0.6 * SR))
fe = int(TOTAL * SR)
fade[fe - int(1.2 * SR): fe] = np.linspace(1, 0, int(1.2 * SR))
fade[fe:] = 0
MUSIC = 0.22 if CFG.get('voice') else 0.55
mix += pad * fade * MUSIC

rng = np.random.default_rng(3)


def add(at, sig, gain):
    p = int(at * SR)
    if p < 0 or p >= L:
        return
    e = min(L, p + len(sig))
    mix[p:e] += sig[: e - p] * gain


def click():
    n = int(0.03 * SR)
    s = np.arange(n) / SR
    noise = rng.standard_normal(n).astype(np.float32)
    noise = np.diff(np.concatenate([[0], noise]))
    return noise * np.exp(-s * 160) * 0.5 + np.sin(2 * np.pi * 2400 * s) * np.exp(-s * 120) * 0.3


def pop():
    n = int(0.09 * SR)
    s = np.arange(n) / SR
    f = 900 - 3500 * s
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-s * 40)


def chime():
    n = int(0.9 * SR)
    s = np.arange(n) / SR
    return (np.sin(2 * np.pi * 1318.5 * s) + 0.7 * np.sin(2 * np.pi * 1760 * s) * (s > 0.09)) * np.exp(-s * 4.5) * 0.5


last = -1
for name, r in rec['sfx']:
    ot, speed = out_time(r)
    if ot is None:
        continue
    if name == 'flip':
        if ot - last < 0.05:
            continue
        last = ot
        add(ot, click(), 0.55)
    elif name in ('pick', 'drop'):
        add(ot, pop(), 0.35)
    elif name in ('done', 'magic'):
        add(ot, chime(), 0.45)
add(REC_END + 0.05, chime(), 0.5)
if CFG.get('voice'):
    # 口播：任意格式（wav/m4a/mp3）先用 ffmpeg 转成 44.1k 单声道，再从 voice_offset 秒开始混入
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', P(CFG['voice']), '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    v = np.frombuffer(raw, np.int16).astype(np.float32) / 32767
    add(CFG.get('voice_offset', 0.0), v, 1.0)
mix = np.tanh(mix * 1.1) * 0.85
pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
with wave.open(D + '_audio.wav', 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(pcm.tobytes())
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', D + '_video.mp4', '-i', D + '_audio.wav', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', OUT], check=True)
print('done', TOTAL)
