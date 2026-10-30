// 宣传片 short-ppt 版的前半段：把录屏按「约 3 秒一个节点」重剪，配律动 BGM + 交互音效，
// 并按新时间轴写出 short-ppt 要的 captions.srt 和 chapters.json。后半段交给 short-ppt 的 render.py。
//
//   node scripts/shortppt_cut.mjs shortppt.json
//
// shortppt.json（路径相对配置文件所在目录）：
// {
//   "rec": "rec",                  // harness.js record 的输出目录（rec.json + frames/）
//   "out": "shortppt",             // 输出：frames.txt、audio.wav、source.mp4、captions.srt、chapters.json
//   "bpm": 116,                    // 配乐速度；默认 116
//   "width": 1080,                  // 输出宽度，高度按比例；默认 1080（录屏帧常常只有 390 宽，直接用会很糊）
//   "drop_at": "fall",             // 可选：在这个时刻（原始时间轴）鼓和贝斯停一拍，用于「塌了 / 翻车」等瞬间
//   "segments": [                  // 一段 = 一个节点，建议每段输出 2.4～3.5 秒
//     { "from": "start", "to": "start+3", "speed": 1, "title": "按住出奶", "sub": "冰激凌机开工", "cap": "按住屏幕就出奶" },
//     { "from": 3.6, "to": 8.4, "speed": 1.6, "title": "一圈圈叠高", "sub": "越叠越上头", "cap": null }
//   ]
// }
// from / to 可以写秒数、mark 名，或「mark±秒数」。cap 为 null 的段不出底部字幕（抽屉、弹窗打开时用）。
// 需要 ffmpeg：优先用环境变量 FFMPEG_BINARY，否则用 PATH 里的 ffmpeg；都没有就只输出素材并打印命令。
import fs from 'node:fs/promises'
import path from 'node:path'
import { spawnSync } from 'node:child_process'

const cfgPath = path.resolve(process.argv[2] || 'shortppt.json')
const base = path.dirname(cfgPath)
const C = JSON.parse(await fs.readFile(cfgPath, 'utf8'))
const REC = path.resolve(base, C.rec || 'rec')
const OUT = path.resolve(base, C.out || 'shortppt')
await fs.mkdir(OUT, { recursive: true })
const rec = JSON.parse(await fs.readFile(path.join(REC, 'rec.json'), 'utf8'))

// 兼容两种录屏格式：harness.js（frames: [[文件名, 绝对时间]], marks: [{key,t}]）和 { frames: [{i,t}], marks: {key: t} }
let fr, marks = {}
if (Array.isArray(rec.frames[0])) {
  const t0 = rec.frames[0][1] <= 1e6 ? 0 : rec.t0
  fr = rec.frames.map(([n, ts]) => ({ file: path.join(REC, 'frames', n), t: ts - t0 }))
} else {
  fr = rec.frames.map((f) => ({ file: path.join(REC, 'frames', String(f.i).padStart(5, '0') + '.jpg'), t: f.t }))
}
if (Array.isArray(rec.marks)) for (const m of rec.marks) marks[m.key] = m.t
else marks = rec.marks || {}
const at = (v) => {
  if (typeof v === 'number') return v
  const m = String(v).match(/^([\w-]+)\s*([+-]\s*[\d.]+)?$/)
  if (!m || !(m[1] in marks)) throw new Error('找不到 mark：' + v)
  return marks[m[1]] + (m[2] ? parseFloat(m[2].replace(/\s/g, '')) : 0)
}

// ---------- 画面：按段取帧、变速，拼成 concat 清单 ----------
const lines = [], chapters = [], cues = [], segOut = []
let out = 0, lastFile = null
for (const s of C.segments) {
  const a = at(s.from), b = at(s.to), sp = s.speed || 1
  const s0 = out
  for (let k = 0; k < fr.length; k++) {
    const t0 = Math.max(fr[k].t, a), t1 = Math.min(k + 1 < fr.length ? fr[k + 1].t : b, b)
    if (t1 <= t0) continue
    lastFile = fr[k].file.replace(/\\/g, '/')
    lines.push(`file '${lastFile}'`, `duration ${((t1 - t0) / sp).toFixed(5)}`)
    out += (t1 - t0) / sp
  }
  segOut.push({ a, b, sp, s0, s1: out })
  if (s.cap) cues.push([s0 + 0.12, out - 0.12, s.cap])
  chapters.push({ start: +s0.toFixed(2), end: +out.toFixed(2), title: s.title, subtitle: s.sub || '', evidence: { cue_start: Math.max(1, cues.length), cue_end: Math.max(1, cues.length) } })
}
lines.push(`file '${lastFile}'`)
const total = out
await fs.writeFile(path.join(OUT, 'frames.txt'), lines.join('\n'))
await fs.writeFile(path.join(OUT, 'chapters.json'), JSON.stringify({ version: 1, chapters }, null, 1))
const ts = (x) => { const ms = Math.round(x * 1000); const h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60, s = Math.floor(ms / 1000) % 60; return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms % 1000).padStart(3, '0')}` }
await fs.writeFile(path.join(OUT, 'captions.srt'), cues.map((c, k) => `${k + 1}\n${ts(c[0])} --> ${ts(c[1])}\n${c[2]}\n`).join('\n'))
const remap = (t) => { for (const g of segOut) if (t >= g.a && t < g.b) return g.s0 + (t - g.a) / g.sp; return null }

// ---------- 声音：律动 BGM（鼓 / 贝斯 / 反拍和弦 / 两小节一句的旋律）+ 交互音效 ----------
const SR = 44100, N = Math.ceil(SR * (total + 1.2))
const music = new Float32Array(N), sfx = new Float32Array(N)
let seed = 11; const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647) * 2 - 1
const midi = (n) => 440 * Math.pow(2, (n - 69) / 12)
function add(dst, t0, len, fn) { const s0 = Math.floor(t0 * SR), n = Math.floor(len * SR); for (let i = 0; i < n && s0 + i < N; i++) if (s0 + i >= 0) dst[s0 + i] += fn(i / SR, i / n) }
const kick = (t) => { let ph = 0; add(music, t, 0.22, (x) => { ph += 2 * Math.PI * (45 + 90 * Math.exp(-x * 30)) / SR; return Math.sin(ph) * Math.exp(-x * 14) * 0.55 }) }
const snare = (t) => { let lp = 0; add(music, t, 0.18, (x) => { lp += (rnd() - lp) * 0.45; return (lp * 0.6 + Math.sin(2 * Math.PI * 190 * x) * 0.25) * Math.exp(-x * 22) * 0.42 }) }
const hat = (t, v) => { let prev = 0; add(music, t, 0.05, (x) => { const r = rnd(); const h = r - prev; prev = r; return h * Math.exp(-x * 90) * v }) }
const bass = (t, n, len) => { const f = midi(n); add(music, t, len, (x, p) => Math.tanh((Math.sin(2 * Math.PI * f * x) + 0.35 * Math.sin(4 * Math.PI * f * x)) * 1.4) * Math.min(1, x * 200) * (1 - p) ** 0.6 * 0.2) }
const stab = (t, notes, len = 0.13, v = 0.07) => notes.forEach((n) => { const f = midi(n); add(music, t, len, (x) => (Math.sin(2 * Math.PI * f * x) + 0.3 * Math.sin(6 * Math.PI * f * x) + 0.15 * Math.sin(10 * Math.PI * f * x)) * Math.exp(-x * 18) * v) })
const bell = (t, n) => { const f = midi(n); add(music, t, 0.6, (x) => (Math.sin(2 * Math.PI * f * x) + 0.25 * Math.sin(2 * Math.PI * f * 2.01 * x)) * Math.exp(-x * 5) * Math.min(1, x * 300) * 0.09) }
const pad = (t, notes, len) => notes.forEach((n) => { const f = midi(n); add(music, t, len, (x, p) => (Math.sin(2 * Math.PI * f * x) + 0.5 * Math.sin(2 * Math.PI * f * 1.003 * x)) * Math.min(1, x * 4, (1 - p) * 4) * 0.022) })

const BEAT = 60 / (C.bpm || 116), BAR = BEAT * 4
const PROG = [[48, [60, 64, 67]], [43, [59, 62, 67]], [45, [60, 64, 69]], [41, [60, 65, 69]]] // C G Am F
const MEL = [[0, 76], [1, 79], [1.5, 76], [2, 74], [3, 72], [4, 74], [5, 76], [5.5, 79], [6, 81], [7, 79]] // 两小节一句，C 大调五声
const drop = C.drop_at != null ? remap(at(C.drop_at)) : null
const bars = Math.ceil(total / BAR)
for (let bi = 0; bi < bars; bi++) {
  const t0 = bi * BAR, [root, chord] = PROG[bi % 4], intro = bi === 0
  pad(t0, chord.map((n) => n - 12), BAR + 0.1)
  for (let b = 0; b < 4; b++) {
    const tb = t0 + b * BEAT
    const muted = drop != null && tb >= drop - 0.05 && tb < drop + BEAT * 1.5
    if (!intro && !muted) {
      if (b === 0 || b === 2) kick(tb)
      if (b === 1 || b === 3) snare(tb)
      if (b === 3 && bi % 2 === 1) kick(tb + BEAT / 2)
      bass(tb, root, BEAT * 0.45); bass(tb + BEAT / 2, b === 2 ? root + 12 : root, BEAT * 0.4)
    }
    if (!muted) { hat(tb, 0.05); hat(tb + BEAT / 2, 0.09); stab(tb + BEAT / 2, chord) }
  }
  if (bi % 2 === 0 && bi > 0 && t0 + 2 * BAR < total + 0.5) for (const [beat, n] of MEL) bell(t0 + beat * BEAT, n)
}
stab(total - 0.2, [60, 64, 67, 72], 1.2, 0.08) // 收在主和弦上
const tone = (t0, len, f0, f1, vol, noise) => { let ph = 0; add(sfx, t0, len, (x, p) => { ph += 2 * Math.PI * (f0 + (f1 - f0) * p) / SR; return (noise ? rnd() : Math.sin(ph)) * Math.min(1, x * 250) * (1 - p) ** 2 * vol }) }
// 常见交互音效的名字；没列到的音效名统一用一声「啵」
const FX = {
  plop: (t) => tone(t, 0.08, 560, 280, 0.14),
  click: (t) => tone(t, 0.03, 1500, 1200, 0.1),
  tap: (t) => tone(t, 0.03, 1500, 1200, 0.1),
  lever: (t) => { tone(t, 0.05, 900, 600, 0.1); tone(t + 0.03, 0.08, 220, 160, 0.12) },
  tip: (t) => tone(t, 0.12, 700, 1100, 0.12),
  done: (t) => [72, 76, 79, 84].forEach((n, i) => tone(t + i * 0.07, 0.3, midi(n), midi(n), 0.11)),
  unlock: (t) => [79, 84].forEach((n, i) => tone(t + i * 0.1, 0.35, midi(n), midi(n), 0.1)),
  whoosh: (t) => tone(t, 0.35, 0, 0, 0.1, true),
  splat: (t) => { tone(t, 0.3, 0, 0, 0.2, true); tone(t, 0.3, 170, 55, 0.3) },
  creak: () => {},
}
let last = {}
for (const [k, t] of rec.sfx || []) {
  const nt = remap(t); if (nt == null) continue
  if (nt - (last[k] ?? -1) < 0.22) continue // 加速段同一音效别太密
  last[k] = nt
  ;(FX[k] || FX.plop)(nt)
}
const mix = new Float32Array(N); let peak = 1e-6
for (let i = 0; i < N; i++) { const t = i / SR; const fade = Math.min(1, t / 0.3, Math.max(0, (total + 1 - t) / 1)); mix[i] = Math.tanh((music[i] * 0.9 * fade + sfx[i]) * 1.2); peak = Math.max(peak, Math.abs(mix[i])) }
const pcm = Buffer.alloc(44 + N * 2)
pcm.write('RIFF', 0); pcm.writeUInt32LE(36 + N * 2, 4); pcm.write('WAVEfmt ', 8)
pcm.writeUInt32LE(16, 16); pcm.writeUInt16LE(1, 20); pcm.writeUInt16LE(1, 22); pcm.writeUInt32LE(SR, 24); pcm.writeUInt32LE(SR * 2, 28); pcm.writeUInt16LE(2, 32); pcm.writeUInt16LE(16, 34)
pcm.write('data', 36); pcm.writeUInt32LE(N * 2, 40)
for (let i = 0; i < N; i++) pcm.writeInt16LE(Math.round(mix[i] * (0.9 / peak) * 32767), 44 + i * 2)
await fs.writeFile(path.join(OUT, 'audio.wav'), pcm)

// ---------- 拼成 source.mp4 ----------
const ff = process.env.FFMPEG_BINARY || 'ffmpeg'
const args = ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', path.join(OUT, 'frames.txt'), '-i', path.join(OUT, 'audio.wav'),
  '-vf', `fps=30,scale=${C.width || 1080}:-2:flags=lanczos,setsar=1,format=yuv420p`, '-c:v', 'libx264', '-crf', '18', '-c:a', 'aac', '-b:a', '192k', '-shortest', path.join(OUT, 'source.mp4')]
const r = spawnSync(ff, args, { stdio: 'inherit' })
if (r.error || r.status !== 0) console.log('没找到可用的 ffmpeg，手动运行：\n' + ff + ' ' + args.map((x) => (/\s/.test(x) ? `"${x}"` : x)).join(' '))
console.log({ total: +total.toFixed(2), nodes: chapters.length, avg: +(total / chapters.length).toFixed(2), captions: cues.length, drop: drop && +drop.toFixed(2) })
for (const c of chapters) if (c.end - c.start > 4 || c.end - c.start < 2) console.log('⚠ 节点时长不在 2～4 秒：', c.title, (c.end - c.start).toFixed(2))
