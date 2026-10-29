# 微信小程序（原生）

> 第一个项目（邮票压花器）的实战经验，加上官方文档的常规做法。真机细节以微信开发者工具和官方文档为准。

## 结构
```
app.js / app.json / app.wxss / project.config.json / sitemap.json
pages/<page>/<page>.{js,json,wxml,wxss}
utils/   ← 与平台无关的渲染核心，加上 wxp.js（API 的 Promise 封装）
```
- `project.config.json` 里的 `appid` 先写 `touristappid`，交付时提醒用户换成自己的 AppID。
- 代码包：主包 ≤2MB。图片尽量用代码绘制；大素材放分包，或让用户自己选。

## 画布
- 用 `<canvas type="2d" id="c">`，通过 `wx.createSelectorQuery().select('#c').fields({node:true,size:true})` 拿到节点。
- 按 `wx.getWindowInfo().pixelRatio` 设置 `canvas.width/height`，再 `ctx.scale`。
- 加载图片用 `canvas.createImage()`；离屏绘制用 `wx.createOffscreenCanvas({type:'2d'})`。
- 导出用 `wx.canvasToTempFilePath({canvas})`。

## 能力
- 选图：`wx.chooseMedia({mediaType:['image']})`；需要相机时用 `<camera>` 组件。
- 存相册：`wx.saveImageToPhotosAlbum`。
  - 用户拒绝过授权会失败（errMsg 里含 auth deny），这时弹窗引导去 `wx.openSetting`；
  - 用户自己取消的不要报错。
  - 现成封装见 `scripts/platform-wechat.js`。
- 分享（微信比小红书强的地方，裂变就靠它）：
  - 在「刚做好作品」的时刻放一个 `<button open-type="share">`（比如「📮 寄给朋友」），点了直接转发给好友 / 群；
  - `onShareAppMessage(res)` 里 `res.from === 'button'` 时，用作品画一张 **5:4** 分享卡（作品斜放在桌垫上 + 投影），标题写成「我做了一个 XX 送你」；
  - 卡片要现场画时，返回 `{ title, path, imageUrl: 原图, promise }`，promise 在 3 秒内 resolve 成带卡片的对象，超时自动用原图；
  - 每个页面都加 `onShareTimeline`，右上角可以分享到朋友圈；
  - `button` 在 style v2 下默认宽 184px、带边框：要写 `width: auto !important` 和 `button::after { border: none }`。
- 存储：小数据用 `wx.setStorageSync`；作品图片用 `wx.getFileSystemManager().saveFile` 存到 `wx.env.USER_DATA_PATH`。
- 传感器：`wx.startGyroscope({interval:'ui'})` + `wx.onGyroscopeChange`；振动用 `wx.vibrateShort({type:'light'})`。
- 音效：小程序里没有 WebAudio 合成。用 Python 合成 wav、ffmpeg 转成 2KB 左右的 mp3 放进 `assets/`，`wx.createInnerAudioContext` 播放，`obeyMuteSwitch = true`（手机静音时不响）。每种音效复用一个实例，播放前 `stop()` + `seek(0)`。

## 上线提醒（交付时告诉用户）
- 选对服务类目；涉及用户上传图片的，可能需要内容安全相关的说明。
- 首次提交审核前，要先填好用户隐私保护指引（相册、相机的用途）。

## 自测
- 渲染核心（utils）可以单独放进浏览器 H5 外壳里，用 Playwright 测渲染结果。
- 页面逻辑提醒用户在微信开发者工具里预览，并真机扫码确认。
