/** 能力分申报目录的查询辅助（目录由后端按学年提供）。 */
import type { Schemas } from '@/api/client'

import { sameDecimal } from './format'

export type Catalog = Schemas['AbilityCatalog']
export type CatalogItem = Schemas['CatalogItem']
export type Declaration = Schemas['DeclarationOut']

export function findItem(catalog: Catalog | null, code: string): CatalogItem | undefined {
  return catalog?.items.find((item) => item.code === code)
}

export function itemName(catalog: Catalog | null, code: string): string {
  return findItem(catalog, code)?.name ?? code
}

export function optionName(catalog: Catalog | null, code: string, option: string | null): string {
  if (!option) return '—'
  return findItem(catalog, code)?.options?.find((o) => o.code === option)?.name ?? option
}

/** 按“评先树优、社会工作……”分组，保持目录中的顺序。 */
export function groupedItems(catalog: Catalog | null): { group: string; items: CatalogItem[] }[] {
  const groups: { group: string; items: CatalogItem[] }[] = []
  for (const item of catalog?.items ?? []) {
    let entry = groups.find((g) => g.group === item.group)
    if (!entry) {
      entry = { group: item.group, items: [] }
      groups.push(entry)
    }
    entry.items.push(item)
  }
  return groups
}

/** 审核时需要重点核对的原因；任一项存在时在审核工作台标红。 */
export function reviewFlags(declaration: Declaration, item: CatalogItem | undefined): string[] {
  const flags: string[] = []
  const { claimed_score: claimed, suggested_score: suggested } = declaration
  if (claimed != null && suggested != null && !sameDecimal(claimed, suggested)) {
    flags.push('申报分与建议分不一致')
  }
  if (item?.scoring === 'manual') flags.push('需人工给分')
  if (declaration.evidence.length === 0) flags.push('未上传证明材料')
  return flags
}
