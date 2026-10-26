// 录屏脚本示例（光栅小卡机）。每个 mark 是宣传片里的一个镜头，key 要和 promo.json 的 segments 对应。
module.exports = async function (api) {
  const { mark, wait, tap, drag, pickFiles } = api
  mark('intro')
  await wait(3200)
  mark('pick')
  await tap('#toPick', 400)
  await pickFiles('.slot.empty', ['photos/cat.jpg', 'photos/dog.jpg', 'photos/coffee.jpg'])
  await wait(900)
  mark('make')
  await tap('#pickNext', 900)
  mark('lr')
  await drag('#cardCanvas', [[-120, 0], [120, 0], [0, 0]], 40)
  mark('ud')
  await drag('#cardCanvas', [[0, 150], [0, 0]], 38)
  mark('save')
  await tap('#saveGifBtn', 1500)
}
