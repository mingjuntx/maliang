# Web 单页

> 这一形态测试最少，1.0 先给规则，后续实测后补充。

- 只交付一个自包含的 HTML（内联 CSS 和 JS，素材用代码绘制或 data URI），双击就能离线打开。
- 移动端优先。桌面端居中显示成手机宽度（`max-width: 430px`），两侧用和舞台一致的深色背景。
- 存图：
  - 用 `a[download]` 下载 PNG 或 GIF；
  - 支持 `navigator.canShare({files})` 时，优先调系统分享，iOS 上可以直接存进相册。
- 倾斜：
  - 用 `deviceorientation` 事件；
  - iOS 13+ 必须在点击回调里调 `DeviceOrientationEvent.requestPermission()`；
  - 始终保留手指拖动兜底。
- 存储：localStorage 存设置，IndexedDB 存作品；每次读写都要 try/catch。
- 发布：
  - 需要一个链接时，发布成 artifact 页面；
  - 用户有自己的站点（比如 GitHub Pages）时，交付静态文件。
- 自测：`scripts/harness.js shoot` 不用改就能跑（mock 不影响 Web）。
