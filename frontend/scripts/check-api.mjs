// 检查 src/api/schema.d.ts 是否由当前的 docs/api/openapi.json 生成（防止前后端接口类型脱节）。
import { execFileSync } from 'node:child_process'
import { mkdtempSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const out = join(mkdtempSync(join(tmpdir(), 'zongce-api-')), 'schema.d.ts')
const bin = (name) => join('node_modules', '.bin', name)
execFileSync(bin('openapi-typescript'), ['../docs/api/openapi.json', '-o', out], {
  stdio: 'ignore',
})
execFileSync(bin('prettier'), ['--config', '.prettierrc.json', '--write', out], { stdio: 'ignore' })
if (readFileSync(out, 'utf8') !== readFileSync('src/api/schema.d.ts', 'utf8')) {
  console.error('src/api/schema.d.ts 与 docs/api/openapi.json 不一致，请运行 pnpm gen:api')
  process.exit(1)
}
console.log('API 类型与 OpenAPI 文档一致')
