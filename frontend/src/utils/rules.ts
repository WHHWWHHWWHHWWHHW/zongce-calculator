/** 从规则文件中收集“规则 id → 中文名”，用于展示计分明细。 */
import { unwrap } from '@/api/client'
import { useAuthStore } from '@/stores/auth'

export function ruleNames(content: unknown): Record<string, string> {
  const names: Record<string, string> = {}
  const visit = (node: unknown): void => {
    if (Array.isArray(node)) {
      node.forEach(visit)
    } else if (node && typeof node === 'object') {
      const record = node as Record<string, unknown>
      if (typeof record.id === 'string' && typeof record.name === 'string' && record.name) {
        names[record.id] = record.name
      }
      Object.values(record).forEach(visit)
    }
  }
  visit(content)
  return names
}

const cache = new Map<number, Record<string, string>>()

/** 读取某个规则版本的名称表（按版本缓存）。 */
export async function loadRuleNames(versionId: number): Promise<Record<string, string>> {
  const cached = cache.get(versionId)
  if (cached) return cached
  const auth = useAuthStore()
  const content = unwrap(
    await auth.api.GET('/api/v1/rules/{version_id}/content', {
      params: { path: { version_id: versionId } },
    }),
  )
  const names = ruleNames(content.rules)
  cache.set(versionId, names)
  return names
}
