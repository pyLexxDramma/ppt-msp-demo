import { describe, expect, it } from 'vitest'
import { placeSelectMenu } from './placeSelectMenu'

const vp = { width: 1280, height: 800 }

describe('placeSelectMenu', () => {
  it('делает список шире узкого поля, чтобы длинные названия не обрезались', () => {
    const pos = placeSelectMenu({ top: 200, left: 40, bottom: 236, width: 180, height: 36 }, vp)
    expect(pos.width).toBeGreaterThanOrEqual(280)
    expect(pos.top).toBe(240)
    expect(pos.left).toBe(40)
  })

  it('не вылезает за правый край экрана', () => {
    const pos = placeSelectMenu({ top: 200, left: 1100, bottom: 236, width: 160, height: 36 }, vp, {
      minWidth: 320,
    })
    expect(pos.left + pos.width).toBeLessThanOrEqual(vp.width - 8)
    expect(pos.left).toBeGreaterThanOrEqual(8)
  })

  it('открывается вверх, если снизу мало места', () => {
    const pos = placeSelectMenu({ top: 740, left: 40, bottom: 776, width: 200, height: 36 }, vp)
    expect(pos.top).toBeLessThan(740)
    expect(pos.maxHeight).toBeGreaterThanOrEqual(96)
  })

  it('не уже самого поля, если поле широкое', () => {
    const pos = placeSelectMenu({ top: 120, left: 20, bottom: 156, width: 400, height: 36 }, vp)
    expect(pos.width).toBe(400)
  })
})
