// 微信小程序常用 API 的 Promise 封装（来自邮票压花器，按需改提示文案）

function getImageInfo(src) {
  return new Promise((resolve, reject) => wx.getImageInfo({ src, success: resolve, fail: reject }))
}

function loadImage(canvas, src) {
  return new Promise((resolve, reject) => {
    const img = canvas.createImage()
    img.onload = () => resolve(img)
    img.onerror = reject
    img.src = src
  })
}

function canvasToFile(canvas) {
  return new Promise((resolve, reject) =>
    wx.canvasToTempFilePath({
      canvas,
      fileType: 'png',
      success: (res) => resolve(res.tempFilePath),
      fail: reject,
    })
  )
}

function getCanvas(page, selector) {
  return new Promise((resolve, reject) => {
    wx.createSelectorQuery()
      .in(page)
      .select(selector)
      .fields({ node: true, size: true })
      .exec((res) => (res && res[0] && res[0].node ? resolve(res[0].node) : reject(new Error('canvas not found'))))
  })
}

function saveToAlbum(filePath) {
  return new Promise((resolve, reject) => {
    wx.saveImageToPhotosAlbum({
      filePath,
      success: () => {
        wx.showToast({ title: '已保存到相册', icon: 'success' })
        resolve()
      },
      fail: (err) => {
        const msg = (err && err.errMsg) || ''
        if (/auth|deny|denied|permission/i.test(msg)) {
          wx.showModal({
            title: '需要相册权限',
            content: '请允许「保存到相册」，作品才能存到手机里',
            confirmText: '去设置',
            success: (r) => r.confirm && wx.openSetting(),
          })
        } else if (!/cancel/i.test(msg)) {
          wx.showToast({ title: '保存失败', icon: 'none' })
        }
        reject(err)
      },
    })
  })
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

module.exports = { getImageInfo, loadImage, canvasToFile, getCanvas, saveToAlbum, sleep }
