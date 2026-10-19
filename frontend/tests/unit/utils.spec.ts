import { describe, expect, it, vi } from 'vitest'

import { ApiError } from '@/api/client'
import {
  type Catalog,
  type Declaration,
  findItem,
  groupedItems,
  itemName,
  optionName,
  reviewFlags,
} from '@/utils/catalog'
import { errorMessage } from '@/utils/errors'
import { filenameFrom, fileUpload, saveBlob, toCsv } from '@/utils/files'
import { formatTime, normalizeDecimal, sameDecimal, scoreText } from '@/utils/format'
import { ruleNames } from '@/utils/rules'

const catalog = {
  id: 'c',
  title: 't',
  source_document: 's',
  notes: '',
  concurrent_coefficients: ['1'],
  caps: [],
  items: [
    {
      code: 'honor',
      group: '评先树优',
      name: '校级荣誉',
      scoring: 'fixed',
      options: [{ code: 'a', name: '十佳', score: '5' }],
      source: 'x',
    },
    { code: 'deeds', group: '社会工作', name: '突出事迹', scoring: 'manual', source: 'y' },
    {
      code: 'cadre',
      group: '社会工作',
      name: '学生干部',
      scoring: 'fixed',
      options: [],
      source: 'z',
    },
  ],
} as unknown as Catalog

const declaration = (overrides: Partial<Declaration>): Declaration =>
  ({
    claimed_score: null,
    suggested_score: null,
    evidence: [{ id: 1 }],
    ...overrides,
  }) as Declaration

describe('format', () => {
  it('UTC 时间显示为北京时间', () => {
    expect(formatTime('2026-10-12T16:00:00+00:00')).toBe('2026/10/13 00:00')
    expect(formatTime(null)).toBe('—')
    expect(formatTime('not a date')).toBe('—')
  })

  it('十进制字符串比较不受末尾 0 影响', () => {
    expect(normalizeDecimal('5.0000')).toBe('5')
    expect(normalizeDecimal('4.50')).toBe('4.5')
    expect(normalizeDecimal('-0.000')).toBe('0')
    expect(normalizeDecimal('007.10')).toBe('7.1')
    expect(sameDecimal('3', '3.0000')).toBe(true)
    expect(sameDecimal('3', '3.5')).toBe(false)
    expect(sameDecimal(null, undefined)).toBe(true)
    expect(sameDecimal('1', null)).toBe(false)
    expect(scoreText(null)).toBe('—')
    expect(scoreText('2.5')).toBe('2.5')
  })
})

describe('catalog', () => {
  it('查找项目与选项名称', () => {
    expect(findItem(catalog, 'honor')?.name).toBe('校级荣誉')
    expect(itemName(catalog, 'nope')).toBe('nope')
    expect(optionName(catalog, 'honor', 'a')).toBe('十佳')
    expect(optionName(catalog, 'honor', 'zzz')).toBe('zzz')
    expect(optionName(catalog, 'honor', null)).toBe('—')
    expect(optionName(null, 'deeds', 'x')).toBe('x')
    expect(groupedItems(catalog).map((g) => [g.group, g.items.length])).toEqual([
      ['评先树优', 1],
      ['社会工作', 2],
    ])
    expect(groupedItems(null)).toEqual([])
  })

  it('审核标红：申报分与建议分不一致、需人工给分、未上传材料', () => {
    const honor = findItem(catalog, 'honor')
    expect(
      reviewFlags(declaration({ claimed_score: '5', suggested_score: '5.0000' }), honor),
    ).toEqual([])
    expect(
      reviewFlags(declaration({ claimed_score: '4', suggested_score: '5.0000' }), honor),
    ).toEqual(['申报分与建议分不一致'])
    expect(reviewFlags(declaration({ evidence: [] }), findItem(catalog, 'deeds'))).toEqual([
      '需人工给分',
      '未上传证明材料',
    ])
  })
})

describe('files', () => {
  it('从 Content-Disposition 取中文文件名', () => {
    const response = (header: string | null) =>
      new Response('', { headers: header ? { 'Content-Disposition': header } : {} })
    expect(
      filenameFrom(response("attachment; filename*=UTF-8''2025-2026-%E7%BB%BC%E6%B5%8B.xlsx"), 'x'),
    ).toBe('2025-2026-综测.xlsx')
    expect(filenameFrom(response(null), 'fallback.xlsx')).toBe('fallback.xlsx')
    expect(filenameFrom(response("attachment; filename*=UTF-8''%E0%A4%A"), 'bad.xlsx')).toBe(
      'bad.xlsx',
    )
  })

  it('CSV：带 BOM、转义引号逗号、防公式注入', async () => {
    const blob = toCsv([
      ['学号', '密码'],
      ['TEST1', '=cmd'],
      ['TEST2', 'a,"b"'],
    ])
    // jsdom 的 Blob 没有 arrayBuffer()，用 FileReader 读取
    const buffer = await new Promise<ArrayBuffer>((resolve) => {
      const reader = new FileReader()
      reader.onload = () => resolve(reader.result as ArrayBuffer)
      reader.readAsArrayBuffer(blob)
    })
    const bytes = new Uint8Array(buffer)
    expect([...bytes.slice(0, 3)]).toEqual([0xef, 0xbb, 0xbf])
    const text = new TextDecoder().decode(bytes.slice(3))
    expect(text).toBe('学号,密码\r\nTEST1,\'=cmd\r\nTEST2,"a,""b"""')
  })
})

describe('upload and save', () => {
  it('multipart 上传把文件放进 file 字段', () => {
    const file = new File(['%PDF-1.4'], '证书.pdf', { type: 'application/pdf' })
    const { body, bodySerializer } = fileUpload(file)
    const form = bodySerializer(body)
    const sent = form.get('file') as File
    expect(sent.name).toBe('证书.pdf')
    expect(sent.size).toBe(file.size)
  })

  it('保存文件：生成临时链接并点击下载', () => {
    const create = vi.fn(() => 'blob:mock')
    const revoke = vi.fn()
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: create, revokeObjectURL: revoke }))
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    saveBlob(new Blob(['x']), '排名.xlsx')
    expect(create).toHaveBeenCalledOnce()
    expect(click).toHaveBeenCalledOnce()
    expect(revoke).toHaveBeenCalledWith('blob:mock')
    expect(document.querySelector('a')).toBeNull()
    click.mockRestore()
    vi.unstubAllGlobals()
  })
})

describe('errors and rules', () => {
  it('错误提示', () => {
    expect(errorMessage(new ApiError(400, 'bad_request', '原密码不正确'))).toBe('原密码不正确')
    expect(
      errorMessage(
        new ApiError(422, 'validation_error', '请求参数不合法', [{ msg: 'String should match' }]),
      ),
    ).toBe('请求参数不合法：String should match')
    expect(errorMessage(new ApiError(422, 'validation_error', '请求参数不合法', []))).toBe(
      '请求参数不合法',
    )
    expect(errorMessage(new Error('x'))).toBe('操作失败，请稍后重试')
  })

  it('从规则文件收集规则名', () => {
    const rules = {
      final: { id: 'final', name: '综合测评成绩' },
      moral: {
        id: 'moral',
        name: '思想品德',
        items: [{ id: 'moral.political', name: '政治素养' }],
      },
      academic: { id: 'academic', name: '' },
    }
    expect(ruleNames(rules)).toEqual({
      final: '综合测评成绩',
      moral: '思想品德',
      'moral.political': '政治素养',
    })
  })
})
