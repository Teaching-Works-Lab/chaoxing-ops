---
name: chaoxing-ops
description: 学习通（超星 mooc2-ans）教学运营操作skill。当需要在学习通出题、题库批量导入（官方xls模板）、新建/重命名/删除章节目录、给章节挂载测验任务点、创建并发布作业给指定班级、验证发布结果时使用。基于 ego-browser 操作，沉淀了每次调用页面重置、ref失效、ExtJS控件触发等原子级踩坑与成功触发方法。触发词：学习通、超星、chaoxing、题库导入、出题、发作业、章节、任务点、发布给班级。
agent_created: true
---

# 学习通操作（Chaoxing Ops）

## Overview

在学习通教师端（mooc2-ans）完成出题→题库导入→章节归位→作业发布这一套运营流程。核心价值在于**原子化操作手册**：把每个界面在特定前提下的触发方式、失败原因、成功触发方法固化下来，避免每次从头试错。

## 环境要求 / Prerequisites（务必先配好）

- **浏览器驱动：ego-browser（eglite）**。本 Skill 所有页面操作均基于 ego-browser，脚本形态为 `ego-browser nodejs <<'EOF' ... EOF`。执行前需在 Agent 环境加载 ego-browser 技能，并保持学习通教师端登录会话有效。
  - 唯一经过验证的驱动方式。改用 Playwright/Puppeteer 原生脚本时，ExtJS 确认框、filechooser 等触发方式需自行改写，不在覆盖范围。
  - 遵守铁律：每次 nodejs 调用结束页面重置、ref 跨调用失效（下文「铁律」详述）。
- **平台与权限**：学习通教师端 `mooc2-ans.chaoxing.com`，账号需具备课程/班级管理权限。
- **课程参数**：`courseId`、`clazzId`、`cpi`、`enc`，从教师端 URL 读取（URL 清单见 `references/atomic-operations.md`）。
- **Python 依赖**：`xlrd`、`xlwt`（仅在生成/解析题库 xls 时需要）。

## 铁律（每次操作前必读）

1. **ego-browser 每次 nodejs 调用结束，页面状态会重置**（回到新标签/门户）。因此：
   - 把"导航 → 一系列操作 → 验证"尽量放进**单次调用**完成；
   - 跨调用复用页面时，一律用**直接 goto 已知 URL** 重建现场（URL 清单见 `references/atomic-operations.md`）。
2. **ref 跨调用必失效**。同一次调用内若要用 `@N`，必须先 `await page.snapshot()` 再点击；否则报 `Unknown ref`。
3. **优先用 DOM 定位 + evaluate 触发**，其次才是 ref/文本点击。ExtJS 控件（学习通大量使用）对原生 `element.click()` 和 `page.click` 经常无响应，需专门触发方式（见原子操作 A6/A7）。
4. **破坏性操作（删除目录）前确认 recordid**，用 `tr#treeview-...-record-<id>` 精确定位，避免误删。
5. **发布类操作后必须验证**：作业列表 / 章节页截图确认班级、人数、状态，不能只看"点击后页面跳转"就当成功。

## Workflow Decision Tree

用户意图 → 入口：
- **出题/整理题库** → 任务 A（题库）
- **建/改/删章节** → 任务 B（章节编辑器，ExtJS）
- **挂载测验到章节** → 任务 C（章节测验）
- **发作业给班级** → 任务 D（作业应用）
- **验证是否发布成功** → 任务 E（验证）
- **每次操作结束后** → 任务 F（复盘沉淀，追加到 `references/atomic-operations.md`）

完整流程通常是 A → B →（C）→ D → E → F。

## 任务 A：题库操作

- 用 `scripts/gen_qbank.py` 生成官方模板格式的 .xls（20列，单选/判断）。
- 导入：批量导入 → 模板导入 → 捕获 filechooser 选文件 → 结果弹窗"共N条数据，成功导入N条"。
- 详细原子步骤 A1–A3 见 `references/atomic-operations.md`。

## 任务 B：章节编辑器（ExtJS，踩坑最多）

- 入口 URL 可直接 goto：`https://mooc1.chaoxing.com/edit/chapters/<courseId>/<chapterId>?...`（从"编辑章节"弹出的新标签页取）。
- 新建子目录、重命名、删除都是原子操作，**删除尤其注意 ExtJS 确认框**。
- 详细原子步骤 B1–B5 见 `references/atomic-operations.md`。

## 任务 C：章节测验任务点

- 编辑器工具栏"测验" → 创建新测验 → 选题（从题库）→ 勾选 → 完成 → 保存。
- 测验作为任务点挂载；章节状态"开放"即对学生生效（学习通章节测验无独立发布按钮）。
- 详细原子步骤 C1–C3 见 `references/atomic-operations.md`。

## 任务 D：作业发布

- 门户 → 作业 → 新建作业 → 手动创建 → 填标题 → 选题 → 保存并发布 → 发放设置 → 发放对象 → 勾选班级 → 发放。
- **这是用户说"发布到作业里"时的正确路径**（区别于章节测验）。
- 详细原子步骤 D1–D6 见 `references/atomic-operations.md`。

## 任务 E：验证

- 作业列表 URL 直接 goto，看班级/作答时间/统计（N未交=已发放N人）；截图确认。
- 章节页确认目录树、任务点数、开放状态。

## 任务 F：复盘沉淀（每次操作后必做）

把本次新遇到的原子操作/踩坑，按统一格式追加到 `references/atomic-operations.md`：
`【原子编号】名称` → `前提/界面特征` / `触发` / `失败原因` / `成功方法` / `目的` / `首次记录日期`。
只记非显而易见、下次能省时间的内容；不要记一次性数据（具体题号、人名）。

## Resources

- `references/atomic-operations.md` — **核心**：全部原子操作手册（前提→触发→失败→成功→目的），含本次所有踩坑与验证。
- `scripts/gen_qbank.py` — 学习通官方题库 xls 模板生成器（单选/判断，20列）。
