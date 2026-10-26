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
- 分享：
  - `onShareAppMessage` 返回自定义标题和分享图（先用画布画一张 5:4 的图）；
  - 分享到朋友圈用 `onShareTimeline`。
- 存储：小数据用 `wx.setStorageSync`；作品图片用 `wx.getFileSystemManager().saveFile` 存到 `wx.env.USER_DATA_PATH`。
- 传感器：`wx.startGyroscope({interval:'ui'})` + `wx.onGyroscopeChange`；振动用 `wx.vibrateShort({type:'light'})`。
- 音效：小程序里没有 WebAudio 合成。用 `wx.createInnerAudioContext` 播放预先生成的短音频（可以用 Python 合成 wav，再转成 mp3），或者干脆只用振动。

## 上线提醒（交付时告诉用户）
- 选对服务类目；涉及用户上传图片的，可能需要内容安全相关的说明。
- 首次提交审核前，要先填好用户隐私保护指引（相册、相机的用途）。

## 自测
- 渲染核心（utils）可以单独放进浏览器 H5 外壳里，用 Playwright 测渲染结果。
- 页面逻辑提醒用户在微信开发者工具里预览，并真机扫码确认。
