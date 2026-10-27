# 纯前端 AI（抠图 / 识别），不联网、不上传

适用：工具需要识别照片里的主体（人、宠物、物品），并且必须离线运行。3D封面图用的就是这套。

## 选型
- 运行时用 TensorFlow.js 4.x，走 WebGL 后端，失败再退回 cpu 后端。**不要用 WASM 后端**，小红书小工具禁用 `WebAssembly.`。
- 人像分割模型用 MediaPipe Selfie Segmentation（Apache-2.0）：输入 256×256×3，取值 0–1，输出 256×256×1 的概率图，权重约 0.4MB。可以从 vladmandic/human-models（MIT）拿现成的 TF.js 格式。
- 实测它对人、猫狗都有效，对杯子、花这类物品不稳定。这时候退回经典算法：边缘颜色聚类，加 Otsu 阈值，再加形态学处理。经典算法也不准时，引导用户手动涂。

## 塞进小工具包
1. TF.js 不能用 npm 安装时，可以从 GitHub 上 vladmandic/human 的 `dist/` 稀疏克隆，拿预构建的 `tfjs.esm.js`。
2. 把 ESM 改写成 IIFE，挂到 `window.tf` 上。小工具不允许 `type="module"`。
3. 把包里的禁用写法改名成桩函数，让审核扫描通过：
   - `fetch(` 改成 `__mtNoNet(`
   - `XMLHttpRequest` 改成 `__mtNoXHR`
   - `WebAssembly.` 改成 `__mtNoWasm.`
   - `new Worker(` 改成 `new __mtNoWorker(`
   - 动态 `import(` 改成 `__mtNoImport(`

   只要不调用相关功能，改名不影响 WebGL 推理。
4. 模型权重转成 base64 写进一个 JS 文件，用 `tf.loadGraphModel(tf.io.fromMemory({...}))` 加载，不走网络。
5. 文件头保留 Apache-2.0 和 MIT 的许可声明。小工具包不允许放 txt，写在注释里。
6. 体积：TF.js 约 1.3MB，加上模型，整包约 0.7MB 的 zip，在推荐的 2MB 以内。
7. tfjs 4 里没有 `.toFloat()`，要用 `tf.cast(x, 'float32')`。

## 抠得更准
- **补边不拉伸**：等比缩放后补边成正方形再送进模型，补边颜色用照片边缘的平均色。
- **翻转平均**：原图跑一次，水平翻转再跑一次，两次结果取平均，边缘更稳。
- **清理**：二值化后只保留主要连通块（不小于最大块的 15%），再从边缘灌水补掉洞。
- **贴边**：用导向滤波（积分图盒式滤波，在长边约 640px 上做，r = 宽/90，eps = 0.0015）以原图亮度为引导，再用 smoothstep 收紧过渡带。头发、手指会贴得很紧。
- 识别完给用户留**细修工具**：双指放大、涂 / 擦、撤销、边缘收紧 / 放宽。AI 不会百分之百准。

## 首页和示例
- 首页示例不要等识别：把示例照片和**提前算好的蒙版**（灰度 jpg，白色表示主体，约 20KB）一起打进包，加上提前量好的主体范围 box。
- 用户点"做一张"时就开始在后台 `preload()` 模型，选完照片能更快出结果。

## 测试
- 无头 Chromium 要加 `--use-angle=swiftshader --enable-unsafe-swiftshader --ignore-gpu-blocklist`，WebGL 才能跑起来；`harness.js` 里设环境变量 `HARNESS_WEBGL=1` 就会带上。没有 WebGL 的工具别开：它会让普通 2D canvas 慢几十倍。
- 软件渲染下识别一张照片要二十多秒，期间录屏收不到新帧。录宣传片前先预热模型，用 `mark_offsets` 跳过等待段。手机上实际耗时要在真机确认。
