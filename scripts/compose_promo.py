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

SR = 44100


def load_audio(path, trim=True):
    """任意格式音频 → 44.1k 单声道 float32；trim=True 时去掉首尾静音（-40dB 以下）"""
    raw = subprocess.run(['ffmpeg', '-loglevel', 'error', '-i', path, '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True, check=True).stdout
    v = np.frombuffer(raw, np.int16).astype(np.float32) / 32767
    if trim and len(v):
        hop = int(0.01 * SR)
        n = len(v) // hop
        rms = np.sqrt(np.mean(v[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12) if n else np.array([0.0])
        on = np.where(rms > 10 ** (-40 / 20))[0]
        if len(on):
            a = max(0, on[0] * hop - int(0.03 * SR))
            b = min(len(v), (on[-1] + 1) * hop + int(0.06 * SR))
            v = v[a:b]
    return v


# ---------- 口播（可选，逐段）----------
# 每段可以带一条口播音频：segment 里写 "vo_file"，或在顶层写 "vo_dir"，按 01.wav、02.wav… 对应第 1、2… 段，
# 结尾卡的口播是 end.wav（或顶层 "end_vo_file"）。"vo" 字段放这句口播的文字，用来出字幕文件。
# 适配规则：画面迁就声音。某段口播比画面长，就把这段画面放慢拉长（录屏本来就是按段变速的），不去加速人声。
VO_LEAD = CFG.get('vo_lead', 0.12)   # 每段开头留多久再开口
VO_TAIL = CFG.get('vo_tail', 0.3)    # 说完留多久再切下一段
VO_DIR = P(CFG['vo_dir']) if CFG.get('vo_dir') else None
# vo_fit：tight（默认）= 段长跟着口播走，说完就切，句间停顿统一；stretch = 只在口播比目标时长长时才拉长
VO_FIT = CFG.get('vo_fit', 'tight')
BPM = CFG.get('bpm', 100)
BEAT = 60.0 / BPM
GRID = BEAT / 2


def vo_path(seg, i):
    f = seg.get('vo_file')
    if f:
        return P(f)
    if VO_DIR:
        for ext in ('wav', 'mp3', 'm4a', 'flac'):
            q = os.path.join(VO_DIR, '%s.%s' % (i, ext))
            if os.path.exists(q):
                return q
    return None


VOS = []
for i, s in enumerate(CFG['segments']):
    f = vo_path(s, '%02d' % (i + 1))
    if f and not os.path.exists(f):
        sys.exit('找不到口播文件：%s' % f)
    VOS.append(load_audio(f) if f else None)
END_VO = None
_ef = P(CFG['end_vo_file']) if CFG.get('end_vo_file') else vo_path({}, 'end')
if _ef:
    END_VO = load_audio(_ef)

# 段落：录屏起止 mark、目标时长、字幕、小标签
SEG = [(s['from'], s['to'], s['dur'], s['caption'], s.get('tag', '')) for s in CFG['segments']]
END_DUR = CFG.get('end_dur', 3.2)
if END_VO is not None:
    END_DUR = max(END_DUR, 0.45 + len(END_VO) / SR + 0.6)
pieces = []
vo_place = []   # (输出时间, 音频, 段号, 文字)
report = []
o = 0.0
for i, (a, b, dur, cap, tag) in enumerate(SEG):
    v = VOS[i]
    if v is not None and VO_FIT == 'tight':
        # 紧凑：段长 = 开口前 + 口播 + 说完后，再向上取整到半拍，切镜头落在拍子上；句间停顿因此统一在 0.3~0.6 秒
        d = VO_LEAD + len(v) / SR + VO_TAIL
        d = max(CFG['segments'][i].get('min_dur', 0.9), d)
        d = math.ceil(d / GRID - 1e-6) * GRID
    elif v is not None:
        d = max(dur, VO_LEAD + len(v) / SR + VO_TAIL)
    else:
        d = dur
    pieces.append((o, o + d, M[a], M[b], cap, tag))
    speed = (M[b] - M[a]) / d
    text = CFG['segments'][i].get('vo', '')
    if v is not None:
        vo_place.append((o + VO_LEAD, v, i + 1, text))
    report.append({'seg': i + 1, 'caption': cap, 'vo': text, 'start': round(o, 2), 'end': round(o + d, 2), 'dur_cfg': dur, 'dur': round(d, 2),
                   'vo_start': round(o + VO_LEAD, 2) if v is not None else None, 'vo_len': round(len(v) / SR, 2) if v is not None else None, 'speed': round(speed, 2)})
    o += d
REC_END = o
TOTAL = REC_END + END_DUR
if END_VO is not None:
    vo_place.append((REC_END + 0.45, END_VO, 'end', CFG.get('end_vo', '')))
print('%-4s %-22s %6s %6s %6s %6s' % ('段', '字幕', '原时长', '实际', '口播', '画面'))
for r in report:
    warn = ''
    if r['vo_len'] is not None and abs(r['dur'] - r['dur_cfg']) > 0.01:
        warn = '  ← 跟着口播%s' % ('拉长' if r['dur'] > r['dur_cfg'] else '缩短')
    if r['speed'] > 12:
        warn += '  ⚠ 画面加速到 %.1fx，会跳得厉害，这句口播可以加长一点，或者给这段设 min_dur' % r['speed']
    if r['speed'] < 0.45:
        warn += '  ⚠ 画面放慢到 %.2fx，会显得卡，建议缩短这句口播或录长一点' % r['speed']
    print('%-4s %-22s %6.2f %6.2f %6s %5.2fx%s' % (r['seg'], r['caption'][:11], r['dur_cfg'], r['dur'], '%.2f' % r['vo_len'] if r['vo_len'] else '-', r['speed'], warn))


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

# ---------- 音频：配乐 + 交互音效 + 口播 ----------
L = int(TOTAL * SR) + SR
mix = np.zeros(L, np.float32)
tt = np.arange(L) / SR


def note(f):
    return 440.0 * 2 ** ((f - 69) / 12)


rng_m = np.random.default_rng(7)


def onepole_lp(x, fc):
    """一阶低通，让合成器声音暖一点"""
    k = math.exp(-2 * math.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    # 分块向量化：用 scipy 不方便时的简单写法
    for i0 in range(0, len(x), 4096):
        blk = x[i0:i0 + 4096]
        out = np.empty_like(blk)
        for j in range(len(blk)):
            acc = (1 - k) * blk[j] + k * acc
            out[j] = acc
        y[i0:i0 + 4096] = out
    return y


def synth_music(total):
    """lo-fi 轻律动：电钢琴和弦 + 圆润低音 + 很轻的鼓。速度 = bpm，和镜头切点同一个拍子网格"""
    n = int(total * SR) + SR
    keys = np.zeros(n, np.float32)
    bass = np.zeros(n, np.float32)
    drums = np.zeros(n, np.float32)
    bar = BEAT * 4
    prog = [[53, 57, 60, 64], [52, 55, 59, 62], [50, 53, 57, 60], [48, 52, 55, 59]]   # Fmaj7 Em7 Dm7 Cmaj7

    def put(buf, at, sig):
        p0 = int(at * SR)
        if p0 >= n:
            return
        e = min(n, p0 + len(sig))
        buf[p0:e] += sig[: e - p0]

    def ep(f, dur):
        # 电钢琴：正弦 + 一点 FM 的"叮"，慢衰减
        m = int(dur * SR)
        t = np.arange(m) / SR
        mod = np.sin(2 * np.pi * f * 1.0 * t) * 1.2 * np.exp(-t * 6)
        w = np.sin(2 * np.pi * f * t + mod) * np.exp(-t * 1.6)
        return (w * np.minimum(1, t / 0.01)).astype(np.float32)

    for bi in range(int(total / bar) + 1):
        ch = prog[bi % 4]
        t0 = bi * bar
        # 和弦：第 1 拍 + 第 3 拍后半拍轻轻再弹一次（切分）
        for at, vel in [(0, 1.0), (BEAT * 2.5, 0.55)]:
            for k, m in enumerate(ch):
                put(keys, t0 + at + k * 0.012, ep(440 * 2 ** ((m - 57) / 12), bar) * 0.16 * vel)
        # 低音：1、3 拍
        f = 440 * 2 ** ((ch[0] - 24 - 57) / 12)
        for at in (0, BEAT * 2):
            m = int(BEAT * 1.6 * SR)
            t = np.arange(m) / SR
            put(bass, t0 + at, (np.sin(2 * np.pi * f * t) * np.exp(-t * 2.2) * np.minimum(1, t / 0.008) * 0.32).astype(np.float32))
        # 鼓：底鼓 1、3 拍（3 拍后的半拍偶尔加一下），軽拍手 2、4 拍，踩镲八分音符带一点摇摆
        for at in [0, BEAT * 2] + ([BEAT * 2.5] if bi % 2 else []):
            m = int(0.28 * SR)
            t = np.arange(m) / SR
            fr = 50 + 70 * np.exp(-t * 30)
            put(drums, t0 + at, (np.sin(2 * np.pi * np.cumsum(fr) / SR) * np.exp(-t * 11) * 0.5).astype(np.float32))
        for at in (BEAT, BEAT * 3):
            m = int(0.16 * SR)
            t = np.arange(m) / SR
            nz = rng_m.standard_normal(m).astype(np.float32)
            nz = np.diff(np.concatenate([[0], nz]))
            put(drums, t0 + at, nz * np.exp(-t * 28) * 0.09)
        for k in range(8):
            at = k * BEAT / 2 + (BEAT * 0.08 if k % 2 else 0)
            m = int(0.05 * SR)
            t = np.arange(m) / SR
            nz = rng_m.standard_normal(m).astype(np.float32)
            nz = np.diff(np.diff(np.concatenate([[0, 0], nz])))
            put(drums, t0 + at, nz * np.exp(-t * 90) * (0.028 if k % 2 else 0.04))
    keys = onepole_lp(keys, 2600)
    out = keys + bass + drums
    # 第一小节只放和弦，第二小节起鼓进来
    out[: int(bar * SR)] = (keys + bass)[: int(bar * SR)]
    return out[:n]


def load_bgm(path, total):
    """外部 BGM：不够长就交叉淡化循环"""
    b = load_audio(path, trim=False)
    n = int(total * SR) + SR
    if len(b) >= n:
        return b[:n]
    xf = int(1.0 * SR)
    out = np.zeros(n, np.float32)
    pos = 0
    while pos < n:
        seg = b.copy()
        if pos > 0:
            seg[:xf] *= np.linspace(0, 1, xf)
            out[pos - xf: pos] *= np.linspace(1, 0, xf)
            pos -= xf
        e = min(n, pos + len(seg))
        out[pos:e] += seg[: e - pos]
        pos = e
    return out


if CFG.get('bgm'):
    pad = load_bgm(P(CFG['bgm']), TOTAL)
    pad *= 0.6 / max(1e-6, float(np.percentile(np.abs(pad), 99.5)))
else:
    pad = synth_music(TOTAL)
    pad *= 0.9 / max(1e-6, float(np.percentile(np.abs(pad), 99.5)))
pad = np.pad(pad, (0, max(0, L - len(pad))))[:L]
fade = np.ones(L, np.float32)
fade[: int(0.6 * SR)] = np.linspace(0, 1, int(0.6 * SR))
fe = int(TOTAL * SR)
fade[fe - int(1.5 * SR): fe] = np.linspace(1, 0, int(1.5 * SR))
fade[fe:] = 0
# 人声轨：逐段口播 + 旧的整段口播（voice + voice_offset）
voice = np.zeros(L, np.float32)


def put(track, at, sig, gain=1.0):
    p = int(at * SR)
    if p < 0 or p >= L:
        return
    e = min(L, p + len(sig))
    track[p:e] += sig[: e - p] * gain


for at, v, _, _ in vo_place:
    put(voice, at, v)
if CFG.get('voice'):
    put(voice, CFG.get('voice_offset', 0.0), load_audio(P(CFG['voice']), trim=False))

# 配乐闪避：有人声时压低，没人声时恢复（起 80ms、落 450ms）
MUSIC = CFG.get('music_gain', 0.55)
DUCK = CFG.get('music_duck', 0.16)
hop = int(0.01 * SR)
nf = L // hop
env = np.sqrt(np.mean(voice[: nf * hop].reshape(nf, hop) ** 2, axis=1))
act = (env > 10 ** (-38 / 20)).astype(np.float32)
# 句内短停顿不要让配乐忽高忽低：把 0.35 秒内的空隙填上
gapf = int(0.35 / 0.01)
idx = np.where(act > 0)[0]
for k in range(len(idx) - 1):
    if 1 < idx[k + 1] - idx[k] <= gapf:
        act[idx[k]: idx[k + 1]] = 1
g = np.empty(nf, np.float32)
cur = MUSIC
for k in range(nf):
    tgt = DUCK if act[k] else MUSIC
    rate = 0.12 if tgt < cur else 0.022
    cur += (tgt - cur) * rate
    g[k] = cur
gain = np.interp(np.arange(L), np.arange(nf) * hop + hop / 2, g).astype(np.float32)
mix += pad * fade * gain

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
# 人声电平统一到峰值 0.8 左右，再混进去
if np.any(voice):
    voice *= 0.8 / max(1e-6, float(np.percentile(np.abs(voice[voice != 0]), 99.5)))
mix += voice
mix = np.tanh(mix * 1.1) * 0.85
pcm = (np.clip(mix, -1, 1) * 32767).astype(np.int16)
with wave.open(D + '_audio.wav', 'wb') as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(SR)
    wf.writeframes(pcm.tobytes())
# 响度：两遍 loudnorm，成片 -16 LUFS、真峰值 -1.5 dBTP
LN = 'loudnorm=I=-16:TP=-1.5:LRA=11'
m = subprocess.run(['ffmpeg', '-hide_banner', '-i', D + '_audio.wav', '-af', LN + ':print_format=json', '-f', 'null', '-'], capture_output=True, text=True).stderr
af = LN
try:
    j = json.loads(m[m.rindex('{'): m.rindex('}') + 1])
    af = LN + ':measured_I=%s:measured_TP=%s:measured_LRA=%s:measured_thresh=%s:offset=%s:linear=true' % (j['input_i'], j['input_tp'], j['input_lra'], j['input_thresh'], j['target_offset'])
except Exception:
    pass
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', D + '_video.mp4', '-i', D + '_audio.wav', '-af', af + ',aresample=44100', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '160k', '-shortest', '-movflags', '+faststart', OUT], check=True)


# 口播时间表 + 字幕文件（有口播文字时）
def ts(x):
    h, r = divmod(x, 3600)
    mm, ss = divmod(r, 60)
    return '%02d:%02d:%06.3f' % (h, mm, ss)


if vo_place:
    base = os.path.splitext(OUT)[0]
    json.dump({'total': round(TOTAL, 2), 'segments': report, 'end_vo': round(len(END_VO) / SR, 2) if END_VO is not None else None}, open(base + '_vo.json', 'w'), ensure_ascii=False, indent=1)
    lines = [(at, at + len(v) / SR, txt) for at, v, _, txt in vo_place if txt]
    if lines:
        with open(base + '.srt', 'w') as f:
            for k, (a, b, txt) in enumerate(lines):
                f.write('%d\n%s --> %s\n%s\n\n' % (k + 1, ts(a).replace('.', ','), ts(b).replace('.', ','), txt))
    print('口播 %d 句已对齐；时间表 %s_vo.json' % (len(vo_place), os.path.basename(base)))
    print('提醒：AI 合成的口播，发布时请勾选「含 AI 合成内容」')
print('done', round(TOTAL, 2))
