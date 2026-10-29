# 踩过的坑

| 现象 | 原因 | 做法 |
|---|---|---|
| 小红书上传报错 | 做成了 `.xhsml` 小程序，或者 zip 里放了 README | 做成 H5 离线 zip，按 `minitool-zip-builder` 打包 |
| 版本判断总是不通过 | `buildVersion` 在 `getLaunchOptions().miniToolEnv` 里，不在顶层 | 读 `miniToolEnv.buildVersion` |
| iOS 上画布模糊不生效 | 部分 WebView 不支持 `ctx.filter`。给对象赋值 `ctx.filter = ...` 不会报错，检测会误判 | 用 `'filter' in CanvasRenderingContext2D.prototype` 检测；不支持时逐级缩小再放大 |
| 小图拉大后出现马赛克 | 一步放大太多倍 | 分两级放大，或者用 `filter: blur` |
| 首次进入页面画布是空的 | 页面还没布局完就开始画 | 切页面后 `requestAnimationFrame` 再计算尺寸；录屏时用 `mark_offsets` 跳过 |
| 加载草稿时弹出一堆提示 | 恢复数据走了用户操作的逻辑 | 恢复时加一个 silent 标记 |
| 宽画面在手机上太小 | 按高度去适配 | 对宽内容自动放大，再按步骤平移镜头 |
| 理解错了用户想要的效果 | 只看文字描述就去猜（例如 iPhone Duo 的"折叠屏效果"其实指虚焦） | 先要录屏或截图 |
| 把核心交互做在了现实里 | 照着视频原样做 | 默认把交互搬进手机里，现实操作只做辅助 |
| 录屏太糊 | 用了 Playwright 的 recordVideo | 用 3 倍缩放 + CDP screencast |
| 字幕被遮挡 | 叠加层盖住了字幕区域 | 固定字幕区，抽帧自查 |
| 运行环境上不了网 | 部分环境只能访问软件包仓库 | 素材问用户要，文档用网页抓取工具查 |
| Python 3.13 没有 audioop | 标准库移除了这个模块 | 音频统一用 ffmpeg 转码 |
| 小工具里跑不了 TF.js | 包里有 `fetch`、`WebAssembly.` 等禁用写法，还是 ESM 模块 | 改写成 IIFE，禁用写法改名成桩函数，见 `ai-on-device.md` |
| 无头浏览器里 WebGL 不可用 | 默认没有 GPU | 加 swiftshader 启动参数 |
| 页面一直在跑动画时，Playwright 截图超时 | 高 DPR 加 rAF 循环，`page.screenshot` 等不到稳定帧 | 改用 CDP 的 `Page.captureScreenshot` |
| 首页示例要等 AI 识别才出来 | 打开时现场识别 | 示例照片和蒙版提前算好打进包 |
| 抠图后背景变黑 | 识别结果缺少背景色字段，被当成 undefined 用了 | 字段存在时才覆盖 |
| 笔刷几乎看不见 | 半径没乘画布高度 | 半径统一用"占画布高度的比例 × 高度" |
| 素材图里的卡片两边有色块接缝 | 直接截了带背景和暗角的渲染图 | 渲染器加 `transparent` 选项，只画主体，再合到新背景上 |
| 用户说"像 XX 效果"却做错 | 没看到参考就开做（出框封面先后做了杂志版、透视版） | 先要参考截图，确认格式后再画 |
| 亮背景上的白色粒子看不见 | 只用 lighter 叠加 | 先垫一层很淡的暗影，再叠加 |
| 宣传片的关键瞬间对不上 | 脚本里 mark 的时间和画面有偏差 | 用音效打点的时间定位，直接写进 rec.json 的 marks |
| 智能体停下来索要「官方改写口令」 | 把官方校验 skill 写成了必须先加载的前置条件 | 用自带的 `check_xhs_zip.py` 自检，官方校验放到上传前、可选 |
| 想用的开源图库其实不能用 | 「免费可商用」只许参考、禁止再分发；GitHub 镜像的 MIT 只覆盖代码 | 先读原作者条款和仓库 LICENSE 的适用范围，再决定；不行就自己画 |
| Playwright 点不到按钮，一直报「element is not stable」 | 按钮带呼吸动画 | 点击时加 `{ force: true }` |
| 测不到「转发给 TA」按钮 | 平台 mock 里没有 `getWindowInfo` / `menuButtons.share` | harness 的 `xhsMock` 已补上右上角三个按钮的位置 |
| 游戏一开局就撞车 | 开局车流离玩家太近，倒计时一结束就撞上 | 开局前方留一段空路 |
| 结算卡上的截图一片白 | 撞车闪白的那一帧被截下来 | 等闪光退掉（约 0.3 秒、车飞在半空）再截 |
| 宣传片里游戏玩几秒就翻车 | 录屏时没人操作 | 场景脚本里注入一个自动驾驶（只在录屏时用），演示撞车时再主动放一辆车到前面 |
| 微信小程序分享按钮又宽又带框 | `button` 默认宽 184px，`::after` 有边框 | `width: auto !important` + `button::after { border: none }` |
| 句子之间停顿忽长忽短 | 画面段长固定，口播有长有短 | 段长跟着口播走，再取整到半拍（`vo_fit: tight`） |
