# 综合测评成绩计算器 · Zongce Calculator

面向济南大学（UJN）学生的综合测评成绩计算器 —— 纯前端单文件 HTML 工具，本地计算、无需联网、数据不上传。

A single-file HTML calculator for University of Jinan (UJN) students' comprehensive assessment ("综测") score — runs fully client-side, no install, no server, no data upload.

**语言 / Language:** [中文](#中文) ｜ [English](#english)

---

## 中文

### 简介

「综合测评成绩计算器」用于按学院规则一键算出综合测评总分：

- **学业水平评价**：占总分 **75%**
- **综合素质评价**：占总分 **25%**（原始分 ÷ 20 折算）

整个工具就是一个 `.html` 文件，双击用浏览器打开即可使用，不依赖任何后端服务，所有计算都在你自己的浏览器里完成，数据不会上传到任何服务器。

### 功能特性

- **纯本地计算**：不联网、不收集、不上传任何数据，隐私安全
- **表格导入**：支持粘贴或上传 `.csv` / `.txt` / `.tsv` 纯文本表格，一键自动填入全部项目（含评议名单）；`.xlsx` 请先在 Excel / WPS 中"另存为 CSV"后再导入
- **示例模板**：内置一键填入的示例模板，方便快速体验各项功能
- **深色 / 浅色主题**：自动跟随系统外观，并可手动切换
- **移动端适配**：手机、平板浏览器均可正常使用

### 使用方法

1. 从 [Releases](../../releases) 页面下载最新版本的 `zongce-calculator.html`（或直接下载仓库中的同名文件）
2. 用浏览器（Chrome / Edge / Firefox / Safari 等）直接打开该文件即可使用
3. （可选）参考仓库内的 `test.xlsx` 整理你自己的成绩数据，另存为 CSV 后通过页面上的"表格导入"一键填入所有项目

> 该工具计算逻辑基于作者整理的综测细则，仅供参考，最终成绩以学院官方核算结果为准。

### 许可证

本项目基于 [Apache License 2.0](./LICENSE) 开源。

### 支持作者

这个小工具是作者利用课余时间做出来的，从整理综测细则到反复调试计算逻辑都花了不少心思。如果它帮你省下了手动计算、反复核对的时间，欢迎扫描仓库中的 `赏点饭吃.jpg` 请作者喝杯奶茶。你的每一份支持，都是持续维护和更新这个工具的动力，非常感谢！

---

## English

### Overview

**Zongce Calculator** computes a student's comprehensive assessment ("综合测评") score at University of Jinan (UJN) according to the college's rules:

- **Academic Performance Evaluation**: **75%** of the total score
- **Comprehensive Quality Evaluation**: **25%** of the total score (raw score ÷ 20)

The whole app is a single `.html` file — just open it in a browser. There is no backend: every calculation runs locally in your browser and no data ever leaves your machine.

### Features

- **Fully local**: no network requests, no data collection, no uploads
- **Table import**: paste or upload a `.csv` / `.txt` / `.tsv` table to auto-fill every field at once (including committee-review scores); for `.xlsx`, save it as CSV from Excel/WPS first
- **Sample template**: a built-in example you can fill in with one click to try the tool
- **Light / dark theme**: follows your system appearance, with a manual toggle
- **Mobile friendly**: works on phone and tablet browsers

### Usage

1. Download the latest `zongce-calculator.html` from the [Releases](../../releases) page (or grab the same file directly from this repo)
2. Open it with any modern browser (Chrome, Edge, Firefox, Safari, …) — no install or server needed
3. (Optional) Use `test.xlsx` in this repo as a template for your own scores, save it as CSV, then use the "Table import" feature to auto-fill everything

> The calculation logic follows the author's own reading of the assessment rules and is provided for reference only — your college's official result is authoritative.

### License

Released under the [Apache License 2.0](./LICENSE).

### Support the author

This tool was built in the author's spare time — sorting out the assessment rules and debugging the calculation logic took real effort. If it saved you time on manual calculation and double-checking, feel free to scan `赏点饭吃.jpg` in this repo to buy the author a cup of milk tea. Every bit of support keeps this tool maintained and updated — thank you!
