# chaoxing-ops（学习通教学运营 Skill）

学习通（超星 mooc2-ans）教师端运营操作的 Agent Skill。把「出题 → 题库导入 → 章节归位 → 作业发布 → 结果验证」全流程沉淀为**原子操作手册**，每一步写清「前提/界面 → 触发 → 失败原因 → 成功方法」，避免每次从头试错。

## 运行环境要求（重要）

| 项 | 要求 |
|---|---|
| 浏览器工具 | **ego-browser**（Skill 内所有操作基于它，见下文配置） |
| 平台 | 学习通教师端 `mooc2-ans.chaoxing.com`，需已登录且有教师/课程管理权限 |
| 课程参数 | `courseId`、`clazzId`、`cpi`、`enc`（从教师端 URL 读取，见 `references/atomic-operations.md` 的 URL 清单） |
| Python 依赖 | `xlrd`、`xlwt`（仅题库 xls 生成/解析需要） |

### 配置 ego-browser

本 Skill 的浏览器自动化全部通过 **ego-browser** 完成（即 `@skill:ego-browser`）。运行前确认：

1. 在支持 ego-browser 的 Agent 环境中加载该浏览器技能；
2. 用 `ego-browser nodejs <<'EOF' ... EOF` 的方式驱动页面（Skill 内的代码片段均为该形式）；
3. 已登录学习通教师端，且浏览器会话保持有效；
4. 遵守本 Skill 的铁律：**每次 nodejs 调用后页面状态重置**、**ref 跨调用失效**——完整流程尽量放单次调用，或跨调用用 `goto(已知URL)` 重建现场。

> 说明：ego-browser 是本 Skill 唯一经过验证的浏览器驱动方式。改用 Playwright / Puppeteer 原生脚本时，ExtJS 控件确认框、filechooser 等触发方式需自行重写，不在本 Skill 覆盖范围内。

## 安装

将本仓库放入 Agent 的 skills 目录，例如：

```
~/.workbuddy/skills/chaoxing-ops/
```

保留目录结构：

```
chaoxing-ops/
├── SKILL.md                         # 主入口：工作流决策树 + 5 项铁律
├── references/
│   └── atomic-operations.md         # 核心：全部原子操作（前提→触发→失败→成功）
└── scripts/
    └── gen_qbank.py                 # 学习通官方 20 列题库 xls 生成器
```

## 能做什么

- **题库**：按官方 20 列模板生成单选题/判断题 `.xls`，批量导入；
- **章节**：在 ExtJS 目录树中新建/重命名/删除章节，精确定位 `recordid`；
- **章节测验**：创建测验并挂载为任务点（章节「开放」即生效）；
- **作业发布**：新建手动作业 → 从题库选题 → 保存并发布 → 选班级发放；
- **验证**：以作业/章节页面数据（班级、人数、已交/未交）证明发布成功；
- **资料库**：上传讲义、题库等资料到课程资源中心。

## 铁律摘要

1. 每次 nodejs 调用结束页面重置 → 完整流程塞进单次调用，或下一步 `goto(已知URL)` 重建；
2. `@N` ref 跨调用失效 → 用前先 `page.snapshot()`，或改用 DOM 定位；
3. ExtJS 控件优先 DOM 定位 + `evaluate` 触发，不用原生 click；
4. 删除目录前确认 `recordid`，防止误删；
5. 发布后必须到列表页/章节页验证，不能只看跳转。

详细原因与成功触发方式见 `references/atomic-operations.md`。

## 生成题库文件

```bash
python scripts/gen_qbank.py
```

修改脚本中的 `TOPIC/DIR/TAG` 与 `single/judge` 题目列表后运行，输出 `.xls` 到工作区 `outputs/`（可用环境变量 `CHAOXING_OUTDIR` 覆盖）。

环境提示（本机 pip 场景）：安装 `xlrd xlwt` 前建议设 `CODEBUDDY_SAFE_DELETE_ENABLED=0` 并清空 `http_proxy/https_proxy`，避免删除守卫与代理导致安装失败。

## 免责声明

本 Skill 仅用于合法授权的自己的课程教学工作。操作前确认账号权限与数据备份，批量删除、发布等破坏性/对外操作请自行复核目标对象。
