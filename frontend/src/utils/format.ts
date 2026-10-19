/** 展示用的格式化工具。分数是后端给出的十进制字符串，这里只做比较与展示，不做计算。 */
import type { Schemas } from '@/api/client'

const timeFormat = new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

/** 后端时间均为带时区的 ISO 8601（UTC），统一显示为北京时间。 */
export function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : timeFormat.format(date)
}

/** 十进制字符串规范化（去掉末尾多余的 0），用于比较 "4.5" 与 "4.5000" 是否相同。 */
export function normalizeDecimal(value: string): string {
  let text = value.trim()
  if (text.includes('.')) text = text.replace(/0+$/, '').replace(/\.$/, '')
  if (/^-0*$/.test(text)) text = '0'
  return text.replace(/^(-?)0+(?=\d)/, '$1')
}

export function sameDecimal(a: string | null | undefined, b: string | null | undefined): boolean {
  if (a == null || b == null) return a == b
  return normalizeDecimal(a) === normalizeDecimal(b)
}

export function scoreText(value: string | null | undefined): string {
  return value == null ? '—' : value
}

type DeclarationStatus = Schemas['DeclarationStatus']
type YearStatus = Schemas['YearStatus']
type AppealStatus = Schemas['AppealStatus']
type Role = Schemas['Role']

export const DECLARATION_STATUS: Record<DeclarationStatus, { label: string; type: string }> = {
  draft: { label: '草稿', type: 'info' },
  submitted: { label: '待审核', type: 'warning' },
  approved: { label: '已通过', type: 'success' },
  rejected: { label: '已驳回', type: 'danger' },
  withdrawn: { label: '已撤回', type: 'info' },
}

export const YEAR_STATUS: Record<YearStatus, string> = {
  draft: '未开放',
  open: '申报中',
  reviewing: '审核中',
  closed: '已结束',
}

export const APPEAL_STATUS: Record<AppealStatus, { label: string; type: string }> = {
  pending: { label: '待处理', type: 'warning' },
  accepted: { label: '已采纳', type: 'success' },
  rejected: { label: '未采纳', type: 'info' },
}

export const ROLE_NAMES: Record<Role, string> = {
  student: '学生',
  class_reviewer: '班级审核员',
  college_admin: '学院管理员',
}
