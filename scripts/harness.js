// 马良 · 自测与录屏工具（Playwright + Chromium）
// 用法：
//   node harness.js shoot  <url> <outDir>             逐页截图冒烟测试（需自行在 SCENES 里写步骤）
//   node harness.js record <url> <outDir> <scenario.js> 高清录屏（CDP screencast），输出 frames/ + rec.json
// scenario.js 导出 async function (api) {...}，api 见下方 makeApi。
const fs = require('fs')
const path = require('path')
const { chromium } = require('playwright')

// 小红书小工具 API 模拟：记录所有平台调用到 window.__calls
function xhsMock(buildVersion) {
  return `
window.__calls=[];window.__sfx=[];
(function(){
  function rec(n,o){window.__calls.push([n,o&&JSON.stringify(o).slice(0,120)])}
  var ok=function(n,v){return function(o){rec(n,o);return Promise.resolve(v||{})}};
  window.xhs={miniTool:{
    getLaunchOptions:function(){return Promise.resolve({miniToolEnv:{buildVersion:${buildVersion}}})},
    saveImageToPhotosAlbum:ok('saveImageToPhotosAlbum'),
    writeTempFile:function(o){rec('writeTempFile');return Promise.resolve({filePath:o.data})},
    postNote:ok('postNote'),
    getFollowStatus:function(){return Promise.resolve({follow_status:window.__fs||0})},
    followAuthor:function(){rec('followAuthor');window.__fs=1;return Promise.resolve({follow_status:1})},
    vibrateShort:ok('vibrateShort')
  }};
})();`
}

// 半透明手指光标 + 音效打点（录屏用）
const FINGER = `
document.addEventListener('DOMContentLoaded',function(){
  var d=document.createElement('div');
  d.style.cssText='position:fixed;z-index:99999;width:30px;height:30px;margin:-15px 0 0 -15px;border-radius:50%;background:rgba(255,255,255,.45);border:2px solid rgba(255,255,255,.95);box-shadow:0 2px 10px rgba(0,0,0,.4);pointer-events:none;opacity:0;transition:opacity .15s,transform .12s;left:-100px;top:-100px';
  document.body.appendChild(d);
  addEventListener('mousemove',function(e){d.style.left=e.clientX+'px';d.style.top=e.clientY+'px';d.style.opacity=1},true);
  addEventListener('mousedown',function(){d.style.transform='scale(.75)'},true);
  addEventListener('mouseup',function(){d.style.transform='scale(1)'},true);
  var iv=setInterval(function(){if(window.Sfx&&Sfx.play){clearInterval(iv);var p=Sfx.play;Sfx.play=function(n){window.__sfx.push([n,Date.now()/1000]);return p.apply(Sfx,arguments)}}},5);
});`

// 要跑 WebGL（TF.js 等）时设 HARNESS_WEBGL=1，用 swiftshader 软件渲染。
// 默认不开：swiftshader 会让普通 2D canvas 慢几十倍，录屏会卡成幻灯片。
const GL_ARGS = process.env.HARNESS_WEBGL === '1' ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] : []

function makeApi(page, extra) {
  const W = (ms) => page.waitForTimeout(ms)
  const center = async (sel) => {
    const loc = page.locator(sel).first()
    // 横向滚动条里的元素可能在屏幕外，先滚进可视区再取坐标
    try {
      await loc.scrollIntoViewIfNeeded({ timeout: 2000 })
    } catch (e) {}
    const b = await loc.boundingBox()
    if (!b) throw new Error('元素不可见：' + sel)
    return [b.x + b.width / 2, b.y + b.height / 2]
  }
  return Object.assign(
    {
      page,
      wait: W,
      // 带手指动画的点击
      tap: async (sel, after = 300) => {
        const [x, y] = await center(sel)
        await page.mouse.move(x, y, { steps: 10 })
        await W(120)
        await page.mouse.down()
        await W(90)
        await page.mouse.up()
        await W(after)
      },
      // 以某元素中心为起点拖一串相对位移
      drag: async (sel, pts, steps = 20) => {
        const [x, y] = await center(sel)
        await page.mouse.move(x, y, { steps: 8 })
        await page.mouse.down()
        for (const [dx, dy] of pts) await page.mouse.move(x + dx, y + dy, { steps })
        await page.mouse.up()
      },
      // 点击后在文件选择框里选文件
      pickFiles: async (sel, files) => {
        const [fc] = await Promise.all([page.waitForEvent('filechooser'), (async () => { const [x, y] = await center(sel); await page.mouse.click(x, y) })()])
        await fc.setFiles(files)
      },
    },
    extra || {}
  )
}

async function shoot(url, outDir) {
  fs.mkdirSync(outDir, { recursive: true })
  const b = await chromium.launch({ args: GL_ARGS })
  const page = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2 })
  const cdp = await page.context().newCDPSession(page)
  const errs = []
  page.on('pageerror', (e) => errs.push(e.message))
  page.on('console', (m) => m.type() === 'error' && errs.push(m.text()))
  await page.addInitScript(xhsMock(9520000))
  await page.goto(url)
  await page.waitForTimeout(1200)
  // 页面一直在跑动画时 page.screenshot 可能超时，用 CDP 直接截
  const shot = await cdp.send('Page.captureScreenshot', { format: 'png' })
  fs.writeFileSync(path.join(outDir, '00-home.png'), Buffer.from(shot.data, 'base64'))
  console.log('calls', JSON.stringify(await page.evaluate(() => window.__calls)))
  console.log('errors', errs)
  await b.close()
}

async function record(url, outDir, scenarioPath) {
  const scenario = require(path.resolve(scenarioPath))
  fs.mkdirSync(outDir, { recursive: true })
  const fdir = path.join(outDir, 'frames')
  fs.rmSync(fdir, { recursive: true, force: true })
  fs.mkdirSync(fdir)
  // 360×640 × 3 倍 = 1080×1920，清晰度远高于 recordVideo
  const b = await chromium.launch({ args: ['--force-device-scale-factor=3'].concat(GL_ARGS) })
  const ctx = await b.newContext({ viewport: { width: 360, height: 640 } })
  await ctx.addInitScript(xhsMock(9520000) + FINGER)
  const page = await ctx.newPage()
  const cdp = await ctx.newCDPSession(page)
  const frames = []
  let fi = 0
  cdp.on('Page.screencastFrame', async (f) => {
    const n = 'f' + String(fi++).padStart(5, '0') + '.jpg'
    fs.writeFileSync(path.join(fdir, n), Buffer.from(f.data, 'base64'))
    frames.push([n, f.metadata.timestamp])
    try {
      await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId })
    } catch (e) {}
  })
  await page.goto(url)
  await page.waitForTimeout(800)
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 90, maxWidth: 1080, maxHeight: 1920 })
  const t0 = Date.now() / 1000
  const marks = []
  const api = makeApi(page, { mark: (key) => marks.push({ key, t: Date.now() / 1000 - t0 }) })
  await scenario(api)
  api.mark('end')
  await page.waitForTimeout(300)
  await cdp.send('Page.stopScreencast')
  const sfx = (await page.evaluate(() => window.__sfx || [])).map(([n, t]) => [n, t - t0])
  fs.writeFileSync(path.join(outDir, 'rec.json'), JSON.stringify({ t0, frames, marks, sfx }))
  console.log(marks.map((m) => m.key + ':' + m.t.toFixed(2)).join(' '), 'frames', frames.length)
  await b.close()
}

module.exports = { xhsMock, makeApi }

if (require.main === module) {
  const [cmd, url, out, sc] = process.argv.slice(2)
  if (cmd === 'shoot') shoot(url, out)
  else if (cmd === 'record') record(url, out, sc)
  else console.log('usage: node harness.js shoot|record <url> <outDir> [scenario.js]')
}
