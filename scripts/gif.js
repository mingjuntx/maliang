// 极简 GIF 编码器：固定 6×7×6 调色板 + 有序抖动 + LZW，纯 JS，离线可用
(function () {
  const PAL = []
  for (let r = 0; r < 6; r++) for (let g = 0; g < 7; g++) for (let b = 0; b < 6; b++) PAL.push([Math.round((r * 255) / 5), Math.round((g * 255) / 6), Math.round((b * 255) / 5)])
  while (PAL.length < 256) PAL.push([0, 0, 0])
  const BAYER = [0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5]

  function quantize(data, w, h) {
    const out = new Uint8Array(w * h)
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = y * w + x
        const d = BAYER[(y & 3) * 4 + (x & 3)] / 16 - 0.5
        const r = Math.max(0, Math.min(5, Math.round((data[i * 4] / 255) * 5 + d)))
        const g = Math.max(0, Math.min(6, Math.round((data[i * 4 + 1] / 255) * 6 + d)))
        const b = Math.max(0, Math.min(5, Math.round((data[i * 4 + 2] / 255) * 5 + d)))
        out[i] = r * 42 + g * 6 + b
      }
    }
    return out
  }

  function Writer() {
    this.buf = []
  }
  Writer.prototype.byte = function (b) {
    this.buf.push(b & 255)
  }
  Writer.prototype.short = function (v) {
    this.byte(v)
    this.byte(v >> 8)
  }
  Writer.prototype.str = function (s) {
    for (let i = 0; i < s.length; i++) this.byte(s.charCodeAt(i))
  }

  function lzw(w, pixels) {
    const minSize = 8
    const clear = 1 << minSize
    const eoi = clear + 1
    let codeSize = minSize + 1
    let next = eoi + 1
    let dict = new Map()
    const out = []
    let cur = 0
    let bits = 0
    const emit = function (code) {
      cur |= code << bits
      bits += codeSize
      while (bits >= 8) {
        out.push(cur & 255)
        cur >>= 8
        bits -= 8
      }
    }
    emit(clear)
    let prefix = pixels[0]
    for (let i = 1; i < pixels.length; i++) {
      const k = pixels[i]
      const key = prefix * 4096 + k
      const hit = dict.get(key)
      if (hit !== undefined) {
        prefix = hit
        continue
      }
      emit(prefix)
      if (next < 4096) {
        dict.set(key, next++)
        if (next > 1 << codeSize && codeSize < 12) codeSize++
      } else {
        emit(clear)
        dict = new Map()
        codeSize = minSize + 1
        next = eoi + 1
      }
      prefix = k
    }
    emit(prefix)
    emit(eoi)
    if (bits > 0) out.push(cur & 255)
    // 分块
    w.byte(minSize)
    for (let i = 0; i < out.length; i += 255) {
      const n = Math.min(255, out.length - i)
      w.byte(n)
      for (let j = 0; j < n; j++) w.byte(out[i + j])
    }
    w.byte(0)
  }

  // frames: [{ data: ImageData.data, delay: 毫秒 }]
  function header(w, width, height) {
    w.str('GIF89a')
    w.short(width)
    w.short(height)
    w.byte(0xf7)
    w.byte(0)
    w.byte(0)
    PAL.forEach(function (c) {
      w.byte(c[0])
      w.byte(c[1])
      w.byte(c[2])
    })
    // 无限循环
    w.byte(0x21)
    w.byte(0xff)
    w.byte(11)
    w.str('NETSCAPE2.0')
    w.byte(3)
    w.byte(1)
    w.short(0)
    w.byte(0)
  }
  function frame(w, f, width, height) {
    {
      w.byte(0x21)
      w.byte(0xf9)
      w.byte(4)
      w.byte(0)
      w.short(Math.round((f.delay || 80) / 10))
      w.byte(0)
      w.byte(0)
      w.byte(0x2c)
      w.short(0)
      w.short(0)
      w.short(width)
      w.short(height)
      w.byte(0)
      lzw(w, quantize(f.data, width, height))
    }
  }
  function encode(frames, width, height) {
    const w = new Writer()
    header(w, width, height)
    frames.forEach(function (f) {
      frame(w, f, width, height)
    })
    w.byte(0x3b)
    return new Uint8Array(w.buf)
  }

  // 逐帧编码并让出主线程，onProgress(0~1)
  function encodeAsync(getFrame, count, width, height, onProgress) {
    return new Promise(function (resolve) {
      const w = new Writer()
      header(w, width, height)
      let k = 0
      function step() {
        const t0 = Date.now()
        while (k < count && Date.now() - t0 < 30) {
          frame(w, getFrame(k), width, height)
          k++
        }
        if (onProgress) onProgress(k / count)
        if (k < count) return setTimeout(step, 0)
        w.byte(0x3b)
        resolve(new Uint8Array(w.buf))
      }
      setTimeout(step, 0)
    })
  }

  function toDataUrl(bytes) {
    let s = ''
    for (let i = 0; i < bytes.length; i += 8192) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 8192))
    return 'data:image/gif;base64,' + btoa(s)
  }

  window.Gif = { encode: encode, encodeAsync: encodeAsync, toDataUrl: toDataUrl }
})()
