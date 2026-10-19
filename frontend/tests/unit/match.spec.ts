import { describe, expect, it } from 'vitest'

import type { Schemas } from '@/api/client'
import {
  canConfirm,
  MATCH_STATUS,
  matchableItems,
  ROUTE_LABEL,
  selectedDeclarations,
  type Suggestion,
} from '@/utils/match'

function suggestion(partial: Partial<Suggestion>): Suggestion {
  return {
    row: 2,
    student_username: 'TEST0001',
    student_name: '测试学生',
    status: 'consistent',
    route: 'fast_track',
    confidence: '0.95',
    declaration_id: 1,
    declaration_title: '某竞赛',
    form_option: 'a',
    form_option_name: 'A',
    declared_option: 'a',
    declared_option_name: 'A',
    reasons: [],
    ...partial,
  }
}

describe('名单比对', () => {
  it('只有可快速通过且有申报的行能确认', () => {
    expect(canConfirm(suggestion({}))).toBe(true)
    expect(canConfirm(suggestion({ route: 'manual' }))).toBe(false)
    expect(canConfirm(suggestion({ declaration_id: null }))).toBe(false)
  })

  it('所选申报去重并跳过不可确认的行', () => {
    const rows = [
      suggestion({ declaration_id: 3 }),
      suggestion({ declaration_id: 3, row: 3 }),
      suggestion({ declaration_id: 4, route: 'manual' }),
      suggestion({ declaration_id: 5 }),
    ]
    expect(selectedDeclarations(rows)).toEqual([3, 5])
  })

  it('只列出有固定等级选项的项目', () => {
    const option = { code: 'x', name: 'X', score: '1' }
    const catalog = {
      items: [
        { code: 'a', name: 'A', options: [option] },
        { code: 'b', name: 'B', options: [] },
        { code: 'c', name: 'C' },
      ],
    } as unknown as Schemas['AbilityCatalog']
    expect(matchableItems(catalog).map((i) => i.code)).toEqual(['a'])
    expect(matchableItems(null)).toEqual([])
  })

  it('每种结果都有中文标签', () => {
    expect(Object.keys(MATCH_STATUS)).toHaveLength(7)
    expect(ROUTE_LABEL.fast_track).toBe('可快速通过')
  })
})
