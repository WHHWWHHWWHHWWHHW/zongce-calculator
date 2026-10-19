/** 名单比对（AI 辅助审核）的展示辅助。建议由后端给出，这里只做标签与筛选。 */
import type { Schemas } from '@/api/client'

export type Suggestion = Schemas['MatchSuggestionOut']
type Status = Schemas['MatchStatus']
type Route = Schemas['Route']

export const MATCH_STATUS: Record<Status, string> = {
  consistent: '与申报一致',
  option_mismatch: '等级不符',
  uncertain: '等级无法确定',
  not_declared: '未申报',
  unknown_student: '学号不存在',
  name_mismatch: '姓名不符',
  duplicate: '名单重复',
}

export const ROUTE_LABEL: Record<Route, string> = {
  fast_track: '可快速通过',
  manual: '人工复核',
  info: '仅提示',
}

export const ROUTE_TAG: Record<Route, 'success' | 'danger' | 'info'> = {
  fast_track: 'success',
  manual: 'danger',
  info: 'info',
}

/** 只有“可快速通过”且对应一条申报的行可以勾选确认。 */
export function canConfirm(s: Suggestion): boolean {
  return s.route === 'fast_track' && s.declaration_id !== null
}

/** 所选行对应的申报编号（去重，保持顺序）。 */
export function selectedDeclarations(rows: Suggestion[]): number[] {
  const ids = rows.filter(canConfirm).map((s) => s.declaration_id as number)
  return [...new Set(ids)]
}

/** 只适合按名单比对的项目：有固定等级选项。 */
export function matchableItems(
  catalog: Schemas['AbilityCatalog'] | null,
): Schemas['CatalogItem'][] {
  return (catalog?.items ?? []).filter((item) => (item.options?.length ?? 0) > 0)
}
