// 交互音效：全部用 WebAudio 现场合成，不需要音频文件（按产品改音色和名字）
(function () {
  let ac = null
  let noise = null
  let muted = false

  function ctx() {
    if (muted) return null
    if (!ac) {
      const AC = window.AudioContext || window.webkitAudioContext
      if (!AC) return null
      try {
        ac = new AC()
      } catch (e) {
        return null
      }
      const len = ac.sampleRate
      noise = ac.createBuffer(1, len, ac.sampleRate)
      const d = noise.getChannelData(0)
      for (let i = 0; i < len; i++) d[i] = Math.random() * 2 - 1
    }
    if (ac.state === 'suspended' && ac.resume) ac.resume()
    return ac
  }

  function burst(opts) {
    const a = ctx()
    if (!a) return
    const t = a.currentTime + (opts.delay || 0)
    const src = a.createBufferSource()
    src.buffer = noise
    const f = a.createBiquadFilter()
    f.type = opts.type || 'bandpass'
    f.frequency.setValueAtTime(opts.freq || 900, t)
    if (opts.freqTo) f.frequency.exponentialRampToValueAtTime(opts.freqTo, t + opts.dur)
    f.Q.value = opts.q || 0.8
    const g = a.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(opts.vol || 0.3, t + (opts.attack || 0.01))
    g.gain.exponentialRampToValueAtTime(0.0001, t + opts.dur)
    src.connect(f)
    f.connect(g)
    g.connect(a.destination)
    src.start(t, Math.random() * 0.5)
    src.stop(t + opts.dur + 0.05)
  }

  function tone(freq, delay, dur, vol) {
    const a = ctx()
    if (!a) return
    const t = a.currentTime + delay
    const o = a.createOscillator()
    o.type = 'sine'
    o.frequency.value = freq
    const g = a.createGain()
    g.gain.setValueAtTime(0.0001, t)
    g.gain.exponentialRampToValueAtTime(vol, t + 0.02)
    g.gain.exponentialRampToValueAtTime(0.0001, t + dur)
    o.connect(g)
    g.connect(a.destination)
    o.start(t)
    o.stop(t + dur + 0.05)
  }

  const play = {
    pick: function () {
      burst({ freq: 2400, dur: 0.06, vol: 0.08, q: 1.5 })
    },
    drop: function () {
      burst({ freq: 700, freqTo: 260, dur: 0.22, vol: 0.32, q: 0.7, attack: 0.012 })
    },
    swish: function () {
      burst({ freq: 600, freqTo: 2200, dur: 0.25, vol: 0.16, q: 0.9, attack: 0.06 })
    },
    crumple: function () {
      for (let i = 0; i < 7; i++) burst({ type: 'highpass', freq: 1800 + Math.random() * 1500, dur: 0.05, vol: 0.12, delay: i * 0.045 + Math.random() * 0.02 })
    },
    fold: function () {
      burst({ freq: 1200, freqTo: 400, dur: 0.18, vol: 0.18, attack: 0.03 })
      burst({ freq: 500, dur: 0.1, vol: 0.2, delay: 0.16 })
    },
    done: function () {
      tone(660, 0, 0.18, 0.12)
      tone(990, 0.1, 0.3, 0.1)
    },
    flip: function () {
      burst({ type: 'highpass', freq: 3200, dur: 0.035, vol: 0.06, q: 1 })
    },
    magic: function () {
      ;[784, 988, 1175, 1568].forEach(function (f, i) {
        tone(f, i * 0.09, 0.4, 0.07)
      })
    },
  }

  window.Sfx = {
    play: function (name) {
      try {
        if (play[name]) play[name]()
      } catch (e) {}
    },
    setMuted: function (m) {
      muted = m
    },
    isMuted: function () {
      return muted
    },
  }
})()
