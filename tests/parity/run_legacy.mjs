// Legacy 对拍执行器。
//
// 用 jsdom 原样加载仓库根目录的 zongce-calculator.html（不改写、不提取函数），
// 按用例把值填进页面输入框，调用页面自己的 calc()，再读取页面上显示的结果。
//
// 用法：node run_legacy.mjs <cases.json>
//   cases.json：用例数组，或 {"cases": [...]}；格式见 tests/golden/cases.json。
//   标准输出：JSON 数组，每项为
//   {id, final_score, gpa, quality_total, moral_total, competence_total}，均为页面显示的字符串；
//   直接输入总分模式下，moral_total / competence_total 为 null。
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { JSDOM, VirtualConsole } from 'jsdom';

const LEGACY = fileURLToPath(new URL('../../zongce-calculator.html', import.meta.url));

// 用例字段 → legacy 页面元素 id
const NUMBER_FIELDS = {
  gpa: 'gpa',
  quality_direct: 'suzhiDirect',
  second_classroom: 'ketang',
  public_service: 'gongyi',
  fitness_test: 'tice',
  dorm_check: 'sushe',
  ability: 'nengli',
};
const MORAL_FIELDS = {
  political: 'zhengzhi',
  morality: 'pinde',
  discipline: 'jilv',
  integrity: 'chengxin',
};

export function loadLegacy() {
  const errors = [];
  const virtualConsole = new VirtualConsole();
  virtualConsole.on('jsdomError', (e) => errors.push(e));
  const dom = new JSDOM(readFileSync(LEGACY, 'utf8'), {
    runScripts: 'dangerously',
    pretendToBeVisual: true,
    url: 'http://localhost/',
    virtualConsole,
  });
  if (errors.length) throw new Error(`legacy 页面加载出错：${errors.map(String).join('; ')}`);
  return { window: dom.window, errors };
}

function setNumber(doc, id, value) {
  const el = doc.getElementById(id);
  const text = value == null ? '' : String(value);
  el.value = text;
  // 数字输入框会清洗非法字符串；为保证 Python 端看到的输入与页面一致，清洗后不同则报错
  if (el.value !== text) throw new Error(`#${id} 不接受输入 ${JSON.stringify(text)}（被清洗为 ${JSON.stringify(el.value)}）`);
}

function readTotal(doc, id) {
  const text = doc.getElementById(id).textContent.split(' / ')[0].trim();
  return text === '—' ? null : text;
}

export function runCase(window, c) {
  const doc = window.document;
  const input = c.input;
  // 1. 清空所有输入，避免上一个用例残留
  for (const id of Object.values(NUMBER_FIELDS)) setNumber(doc, id, '');
  for (const base of Object.values(MORAL_FIELDS)) {
    doc.getElementById(`${base}-score`).value = '';
    doc.getElementById(`${base}-list`).value = '';
  }
  // 2. 模式与取值
  window.setSuzhiMode(input.quality_mode ?? 'detail');
  for (const [field, id] of Object.entries(NUMBER_FIELDS)) setNumber(doc, id, input[field]);
  for (const [field, base] of Object.entries(MORAL_FIELDS)) {
    const item = input[field] ?? { mode: 'direct', value: '' };
    if (item.mode === 'list') {
      window.setPindeMode(base, 'list');
      doc.getElementById(`${base}-list`).value = item.text ?? '';
    } else {
      window.setPindeMode(base, 'direct');
      setNumber(doc, `${base}-score`, item.value);
    }
  }
  // 3. 调用页面自己的 calc()，读取显示结果
  window.calc();
  return {
    id: c.id,
    final_score: doc.getElementById('finalScore').textContent.trim(),
    gpa: doc.getElementById('sumGpa').textContent.trim(),
    quality_total: readTotal(doc, 'sumSuzhi'),
    moral_total: readTotal(doc, 'sumPinde'),
    competence_total: readTotal(doc, 'sumNengli'),
  };
}

function main() {
  const path = process.argv[2];
  if (!path) {
    process.stderr.write('用法：node run_legacy.mjs <cases.json>\n');
    process.exit(2);
  }
  const data = JSON.parse(readFileSync(path, 'utf8'));
  const cases = Array.isArray(data) ? data : data.cases;
  const { window, errors } = loadLegacy();
  const results = cases.map((c) => runCase(window, c));
  if (errors.length) throw new Error(`legacy 运行出错：${errors.map(String).join('; ')}`);
  process.stdout.write(JSON.stringify(results));
  window.close();
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) main();
