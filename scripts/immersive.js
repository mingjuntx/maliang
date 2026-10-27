// 马良 · 沉浸式布局的小工具函数：抽屉开关、拖动舞台时界面淡出、画面提示
// 用法：
//   Immersive.init({ root: $('studio'), stage: $('stage'), drawers: ['lookDrawer', 'shareDrawer'], dimOnDrag: true })
//   $('lookBtn').addEventListener('click', function () { Immersive.toggle('lookDrawer') })
//   Immersive.hint('拖一拖试试', 4000)
;(function () {
  const api = { root: null, drawers: [], onOpen: null }
  function $(id) {
    return document.getElementById(id)
  }
  let dimTimer = 0
  api.init = function (o) {
    api.root = o.root
    api.drawers = o.drawers || []
    api.onOpen = o.onOpen || null
    api.drawers.forEach(function (id) {
      const d = $(id)
      const h = d && d.querySelector('.drawer-handle')
      if (h) h.addEventListener('click', api.close)
    })
    if (o.stage) {
      o.stage.addEventListener('pointerdown', function () {
        api.close()
        if (o.dimOnDrag === false) return
        clearTimeout(dimTimer)
        api.root.classList.add('dim')
        api.hideHint()
      })
      const up = function () {
        clearTimeout(dimTimer)
        dimTimer = setTimeout(function () {
          api.root.classList.remove('dim')
        }, 700)
      }
      o.stage.addEventListener('pointerup', up)
      o.stage.addEventListener('pointercancel', up)
    }
  }
  api.isOpen = function (id) {
    const d = $(id)
    return !!d && d.classList.contains('open')
  }
  api.open = function (id) {
    api.drawers.forEach(function (d) {
      const el = $(d)
      if (el) el.classList.toggle('open', d === id)
    })
    if (api.onOpen) api.onOpen(id)
  }
  api.close = function () {
    api.drawers.forEach(function (d) {
      const el = $(d)
      if (el) el.classList.remove('open')
    })
  }
  api.toggle = function (id) {
    if (api.isOpen(id)) api.close()
    else api.open(id)
  }
  let hintTimer = 0
  api.hint = function (text, ms) {
    const el = api.root && api.root.querySelector('.stage-hint')
    if (!el) return
    el.textContent = text
    el.classList.remove('gone')
    clearTimeout(hintTimer)
    if (ms) hintTimer = setTimeout(api.hideHint, ms)
  }
  api.hideHint = function () {
    const el = api.root && api.root.querySelector('.stage-hint')
    if (el) el.classList.add('gone')
  }
  window.Immersive = api
})()
