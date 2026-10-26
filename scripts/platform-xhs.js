// 小红书小工具平台适配层：版本门槛、存相册、发笔记、存储、文件、陀螺仪、振动、关注作者。按需删减。
(function () {
  function mt() {
    return (window.xhs && window.xhs.miniTool) || null
  }
  function has(name) {
    const m = mt()
    return !!(m && typeof m[name] === 'function')
  }

  let envPromise = null
  function readEnv(o) {
    return (o && o.miniToolEnv) || null
  }
  // 启动参数：同步优先，异步兜底
  function getEnv() {
    if (envPromise) return envPromise
    envPromise = (async function () {
      const sync = readEnv(window.xhs && window.xhs.launchOptions)
      if (sync && sync.buildVersion) return sync
      if (!has('getLaunchOptions')) return sync || {}
      try {
        return readEnv(await mt().getLaunchOptions()) || {}
      } catch (e) {
        return sync || {}
      }
    })()
    return envPromise
  }
  async function clientAtLeast(v) {
    const env = await getEnv()
    return Math.floor((Number(env.buildVersion) || 0) / 1000) >= v
  }

  // ---------- 窗口信息（9.49+） ----------
  async function getWindowInfo() {
    if (!has('getWindowInfo')) return null
    try {
      return await mt().getWindowInfo()
    } catch (e) {
      return null
    }
  }

  // ---------- 振动（9.50+） ----------
  function vibrate(type) {
    if (has('vibrateShort')) {
      try {
        const r = mt().vibrateShort({ type: type || 'medium' })
        if (r && typeof r.catch === 'function') r.catch(function () {})
      } catch (e) {}
      return
    }
    try {
      if (navigator.vibrate) navigator.vibrate(type === 'heavy' ? 30 : type === 'light' ? 8 : 15)
    } catch (e) {}
  }

  // ---------- 图片：存相册 / 发笔记 ----------
  async function toLocalPath(dataUrl) {
    if (has('writeTempFile')) {
      try {
        const r = await mt().writeTempFile({ data: dataUrl })
        if (r && r.filePath) return r.filePath
      } catch (e) {}
    }
    return dataUrl
  }
  // 返回 'ok' | 'fail' | 'unsupported'
  async function saveImage(dataUrl) {
    if (!has('saveImageToPhotosAlbum')) return 'unsupported'
    try {
      await mt().saveImageToPhotosAlbum({ filePath: await toLocalPath(dataUrl) })
      return 'ok'
    } catch (e) {
      return 'fail'
    }
  }
  async function postNote(opts) {
    if (!has('postNote')) return 'unsupported'
    try {
      const images = []
      for (const d of opts.images) images.push({ url: await toLocalPath(d) })
      await mt().postNote({
        title: opts.title,
        content: opts.content,
        pageType: 'photo_publish',
        mediaInfo: { image_resources: images },
      })
      return 'ok'
    } catch (e) {
      return 'fail'
    }
  }

  // ---------- 小数据缓存（9.46+ 用 Storage，否则浏览器存储） ----------
  async function getJSON(key, def) {
    if ((await clientAtLeast(9460)) && has('getStorage')) {
      try {
        const r = await mt().getStorage({ key })
        return r && typeof r.data === 'string' ? JSON.parse(r.data) : def
      } catch (e) {
        return def
      }
    }
    try {
      const v = localStorage.getItem(key)
      return v ? JSON.parse(v) : def
    } catch (e) {
      return def
    }
  }
  async function setJSON(key, value) {
    let str
    try {
      str = JSON.stringify(value)
    } catch (e) {
      return false
    }
    if ((await clientAtLeast(9460)) && has('setStorage')) {
      try {
        await mt().setStorage({ key, data: str })
        return true
      } catch (e) {
        return false
      }
    }
    try {
      localStorage.setItem(key, str)
      return true
    } catch (e) {
      return false
    }
  }

  // ---------- 图片文件（9.49+ 用文件系统） ----------
  async function fileSystemRoot() {
    if (!(await clientAtLeast(9490))) return null
    if (!['writeTempFile', 'saveFile', 'readFile', 'unlink', 'mkdir'].every(has)) return null
    const env = await getEnv()
    return env.userDataPath || null
  }
  async function savePng(dataUrl, name) {
    const root = await fileSystemRoot()
    if (!root) return null
    const dir = root + '/works'
    try {
      await mt().mkdir({ dirPath: dir, recursive: true })
    } catch (e) {} // 已存在时会失败，忽略
    const tmp = await mt().writeTempFile({ data: dataUrl })
    const r = await mt().saveFile({ tempFilePath: tmp.filePath, filePath: dir + '/' + name })
    return r.savedFilePath
  }
  async function readPngAsDataUrl(filePath, mime) {
    let chunk = 0
    if (has('getFileStorageInfo')) {
      try {
        chunk = (await mt().getFileStorageInfo()).readChunkMaxBytes || 0
      } catch (e) {}
    }
    let out = ''
    let pos = 0
    for (;;) {
      const opts = { filePath, encoding: 'base64' }
      if (chunk) {
        // base64 分片需按 3 字节对齐才能直接拼接
        opts.position = pos
        opts.length = chunk - (chunk % 3)
      }
      const r = await mt().readFile(opts)
      out += r.data || ''
      pos += r.bytesRead || 0
      if (!chunk || r.eof || !r.bytesRead) break
    }
    return 'data:' + (mime || (/\.jpe?g$/i.test(filePath) ? 'image/jpeg' : 'image/png')) + ';base64,' + out
  }
  async function removeFile(filePath) {
    if (!has('unlink')) return
    try {
      await mt().unlink({ filePath })
    } catch (e) {}
  }

  // ---------- 陀螺仪（9.50+）：回调得到角速度 {x,y,z}，单位 rad/s ----------
  let gyroCb = null
  async function startGyro(cb) {
    if (!(await clientAtLeast(9500))) return false
    if (!['startGyroscope', 'onGyroscopeChange'].every(has)) return false
    try {
      gyroCb = function (res) {
        if (res && isFinite(res.x)) cb(res)
      }
      mt().onGyroscopeChange(gyroCb)
      await mt().startGyroscope({ interval: 'ui' })
      return true
    } catch (e) {
      return false
    }
  }
  function stopGyro() {
    try {
      if (gyroCb && has('offGyroscopeChange')) mt().offGyroscopeChange(gyroCb)
      if (has('stopGyroscope')) {
        const r = mt().stopGyroscope()
        if (r && typeof r.catch === 'function') r.catch(function () {})
      }
    } catch (e) {}
    gyroCb = null
  }

  // 关注作者（9.51+）：只能关注本工具作者；status -1失败 0未关注 1已关注 2作者本人
  async function followSupported() {
    return (await clientAtLeast(9510)) && has('followAuthor') && has('getFollowStatus')
  }
  async function getFollowStatus() {
    if (!(await followSupported())) return -1
    try {
      const r = await mt().getFollowStatus()
      const s = r && (r.follow_status !== undefined ? r.follow_status : r.data && r.data.follow_status)
      return typeof s === 'number' ? s : -1
    } catch (e) {
      return -1
    }
  }
  let following = false
  async function followAuthor() {
    if (following) return { status: -1, code: 10003 }
    if (!(await followSupported())) return { status: -1, code: 'unsupported' }
    following = true
    try {
      const r = await mt().followAuthor()
      const s = r && (r.follow_status !== undefined ? r.follow_status : r.data && r.data.follow_status)
      return { status: typeof s === 'number' ? s : -1 }
    } catch (e) {
      return { status: -1, code: e && (e.errCode || e.code) }
    } finally {
      following = false
    }
  }

  window.Platform = {
    followSupported,
    getFollowStatus,
    followAuthor,
    startGyro,
    stopGyro,
    getWindowInfo,
    vibrate,
    saveImage,
    postNote,
    getJSON,
    setJSON,
    savePng,
    readPngAsDataUrl,
    removeFile,
  }
})()
