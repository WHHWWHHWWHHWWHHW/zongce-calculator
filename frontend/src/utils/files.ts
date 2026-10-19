/** 文件上传与下载的辅助函数。 */

/** 从 Content-Disposition（filename*=UTF-8''...）中取文件名。 */
export function filenameFrom(response: Response, fallback: string): string {
  const header = response.headers.get('Content-Disposition') ?? ''
  const match = /filename\*=UTF-8''([^;]+)/i.exec(header)
  if (!match?.[1]) return fallback
  try {
    return decodeURIComponent(match[1])
  } catch {
    return fallback
  }
}

/** 让浏览器保存一个 Blob。 */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

/** openapi-fetch 的 multipart 上传参数（后端字段名为 file）。 */
export function fileUpload(file: File) {
  return {
    body: { file: file as unknown as string },
    bodySerializer: (body: { file: string }) => {
      const form = new FormData()
      form.append('file', body.file as unknown as Blob, file.name)
      return form
    },
  }
}

/** 生成 CSV（UTF-8 BOM，Excel 可直接打开）。以 = + - @ 开头的单元格加前缀，防止公式注入。 */
export function toCsv(rows: string[][]): Blob {
  const escape = (cell: string) => {
    const safe = /^[=+\-@]/.test(cell) ? `'${cell}` : cell
    return /[",\n]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe
  }
  const text = rows.map((row) => row.map(escape).join(',')).join('\r\n')
  return new Blob(['﻿', text], { type: 'text/csv;charset=utf-8' })
}
