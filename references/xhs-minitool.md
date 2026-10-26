# 小红书小工具（H5 离线 zip）

> 先加载官方 `minitool-zip-builder` skill（在创服平台下载）。官方文档：https://miniapp-sandbox.xiaohongshu.com/minitool/doc
> 本文是实战中整理的要点，以官方最新文档为准。

## 形态
- 产物是离线 H5 的 zip 包，`index.html` 必须在 zip 根目录。**不要**做成 `.xhsml` 小程序。
- 允许的文件类型：html、css、js、json、png、jpg、jpeg、gif、webp、svg、woff、woff2。**不要放 README**，否则上传报错。
- 打包：`cd dir && zip -qr -D -X ../x.zip . -x '*.DS_Store'`。`-D` 表示不写入目录条目。
- 打完包跑官方的 `audit_artifact.mjs` 和 `audit_artifact.py`。

## 禁用写法
- 内联脚本、HTML 上的 `onclick` 属性、`type="module"`、`eval`、`new Function`。
- 网络与外跳：`fetch`、外链资源、`a[download]`、`window.open`、`target=_blank`。
- 设备：`DeviceOrientation`（用平台陀螺仪代替）、蓝牙。
- 事件绑定一律用 `addEventListener`。连 `el.onclick = ...` 这种写法也避免，免得被扫描误判。

## 兼容基线
- JS 写到 ES2017；CSS 按 Chrome 61 来写。
- 不能用：flex `gap`、`inset`、`aspect-ratio`。
- `backdrop-filter` 只能放在 `@supports` 里。
- `background-clip:text` 要同时写 `-webkit-` 前缀。
- 安全区：
  - 用 `var(--safe-area-inset-top, env(safe-area-inset-top))` 读，并配一个探针元素；
  - 再用 `getWindowInfo()` 的 `safeArea` 和 `menuButtons`（back、me、share）把顶部让开。

## 平台 API（`window.xhs.miniTool`）
**版本判断**：`getLaunchOptions()` 返回 `{ miniToolEnv: { buildVersion } }`，用 `Math.floor(buildVersion / 1000)` 和 9460、9500 这类门槛比较。
注意 `buildVersion` 在 `miniToolEnv` 里面，不在顶层。

| 能力 | API | 版本 | 要点 |
|---|---|---|---|
| 存相册 | `writeTempFile({data})` → `saveImageToPhotosAlbum({filePath})` | — | 支持 png、jpeg、webp、gif、mp4 |
| 发笔记 | `postNote({title, content, pageType:'photo_publish', mediaInfo:{image_resources:[{url}]}})` | — | 标题 ≤20 字，正文 ≤1000 字，图片 1–18 张，`url` 用 `writeTempFile` 返回的路径 |
| 本地存储 | `setStorage` / `getStorage` | 9.46+ | 低版本退回浏览器存储 |
| 文件系统 | `saveFile` / `readFile` / `unlink` / `mkdir` | 9.49+ | 根目录是 `userDataPath`；分片读取时，每片长度要按 3 字节对齐，base64 才能直接拼接 |
| 窗口信息 | `getWindowInfo` | 9.49+ | `safeArea`、`menuButtons` |
| 振动 | `vibrateShort({type})` | 9.50+ | 低版本用 `navigator.vibrate` |
| 陀螺仪 | `startGyroscope({interval:'ui'})` + `onGyroscopeChange` | 9.50+ | 返回角速度 `{x,y,z}`，单位 rad/s，要自己积分并缓慢回中；不支持时报错 10002；**必须留手指拖动兜底** |
| 关注作者 | `getFollowStatus` / `followAuthor` | 9.51+ | 只能关注本工具作者；`follow_status` 取值：0 未关注，1 已关注，2 是作者本人，-1 失败；每人每天最多弹 10 次确认框（错误码 15404）；用户取消是 20002 |
| 评论区 | `interactionOpenApi({payload:{action:'post_comment',...}})` | 9.49+ | 只支持图片 |

现成封装见 `scripts/platform-xhs.js`：所有能力都返回 `'ok'`、`'fail'` 或 `'unsupported'`，并按版本自动降级。

## 关注作者的放法（涨粉）
- **不要**一打开工具就弹关注。
- 放在「存相册成功」或「发笔记成功」之后的完成面板里，只对未关注的用户显示。
- 文案示例：「喜欢的话关注一下作者，下一个小工具做好第一时间看到」。

## 自测
- `scripts/harness.js` 自带 `xhsMock(buildVersion)`，会把每次平台调用记录到 `window.__calls`。
- 选图用 `<input type=file accept="image/*" multiple>`，测试时用 Playwright 的 `filechooser` 事件喂文件。

## 解锁玩法（关注 / 发笔记）
- 核心功能永远免费。只把**额外的样式**（皮肤、相框、背景色）上锁，并在样式按钮上标 🔒。
- 点到上锁的样式时，弹出解锁面板，给两条路任选：`followAuthor` 成功（`follow_status` 为 1 或 2），或者 `postNote` 返回 ok。完成一次就永久解锁，存进本地存储。
- 解锁后直接帮用户换上刚才点的那个样式，不用再点一次。
- 平台不支持关注时隐藏关注按钮，不支持发笔记时隐藏发笔记按钮；两个都不支持时（比如浏览器预览）全部开放。
- 小工具没有单独的"分享"接口。用户说"分享解锁"时，用发笔记来实现。
- **风险要告诉用户**：小红书社区规范把"用利益诱导点赞、关注、分享、发文"列为违规。只锁额外样式比锁核心功能风险低，但仍是灰区。发布文案里不要写"关注才能用"。

## 上架素材（创服平台后台）
| 素材 | 规格 |
|---|---|
| 图标 | png / jpg，不超过 5MB，推荐 1:1。出 1024×1024 |
| 封面 | jpg / png，不超过 10MB，固定裁剪成 3:4。出 1080×1440，标题两侧至少留 100px |

做法见 `references/promo.md` 的「图标」和「上架封面」两节。
