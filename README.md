# chaoxing-ops（学习通教学运营 Skill）

学习通（超星 mooc2-ans）教师端运营操作的 Agent Skill。把「出题 → 题库导入 → 章节归位 → 作业发布 → 结果验证」全流程沉淀为**两层知识**：

| 层 | 文件 | 解决什么 |
|---|---|---|
| 原子操作手册 | `references/atomic-operations.md` | 单个动作「怎么点才生效」：前提/界面 → 触发 → 失败原因 → 成功方法 |
| 任务剧本（思维链） | `references/playbooks.md` | 一类任务「先做什么、何时分支、什么算完成、失败往哪退」：目标终态 → 前置检查 → 事务边界 → 决策分支 → 验证断言 → 失败回退 |
| 执行机制 | `SKILL.md` 启动协议 + `references/chain-template.md` | 每次执行时把链拉起来、跨调用保持住、留下可续跑台账 |

原子是词汇，剧本是句式，台账是这一次任务写到哪了。接到完整任务先读剧本 → 按启动协议写出链并建台账 → 执行到具体步骤再按 `[D7]` 之类编号查原子。

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

仓库地址：**https://github.com/Teaching-Works-Lab/chaoxing-ops**（public，main 分支）。

方式一（推荐，便于后续更新）：

```bash
git clone https://github.com/Teaching-Works-Lab/chaoxing-ops.git ~/.workbuddy/skills/chaoxing-ops
```

方式二：直接把本仓库内容复制到 Agent 的 skills 目录 `~/.workbuddy/skills/chaoxing-ops/`。

保留目录结构：

```
chaoxing-ops/
├── SKILL.md                         # 主入口：思维链启动协议 + 两层分流 + 决策树 + 5 项铁律
├── README.md                        # 安装、环境、能力清单、维护方式
├── CHANGELOG.md                     # 版本明细（按「原子操作更新 / 思维链更新」分栏）
├── .gitignore                       # 忽略生成物（outputs/、*.xls 等）
├── references/
│   ├── playbooks.md                 # 任务剧本/思维链（六段式，按目标索引 P1–P5）
│   ├── chain-template.md            # 执行台账模板（把剧本在单次任务里实例化，可续跑）
│   └── atomic-operations.md         # 全部原子操作（前提→触发→失败→成功）
└── scripts/
    └── gen_qbank.py                 # 学习通官方 20 列题库 xls 生成器
```

Skill 由文件系统直接加载，clone / 更新后**无需重启或注册**，下次调用即读新内容。

## 版本与更新

变更明细见 `CHANGELOG.md`。若用方式一安装（本地已是 git 仓库且 `origin` 指向上述地址）：

```bash
# 拉取最新版本
git -C ~/.workbuddy/skills/chaoxing-ops pull origin main

# 本地改完同步回 GitHub
git -C ~/.workbuddy/skills/chaoxing-ops add -A
git -C ~/.workbuddy/skills/chaoxing-ops commit -m "feat: ..."
git -C ~/.workbuddy/skills/chaoxing-ops push origin main
```

维护约定：

- 控件级新坑 → 补 `references/atomic-operations.md`；流程 / 顺序 / 回滚问题 → 修订 `references/playbooks.md`；两类变更建议**分开提交**，便于在 GitHub 历史里区分；
- 不把课程 ID、班级 ID、教师姓名、题号等一次性业务数据写进仓库；
- 本机走代理时 git over https 偶发 `schannel: failed to receive handshake` 或 `CONNECT tunnel failed 502`，**直接重试同一命令即可**；推送凭证由 `gh auth setup-git` 配置。

## 能做什么

- **题库**：按官方 20 列模板生成单选题/判断题 `.xls`，批量导入；
- **章节**：在 ExtJS 目录树中新建/重命名/删除章节，精确定位 `recordid`；
- **章节测验**：创建测验并挂载为任务点（章节「开放」即生效）；
- **作业发布**：新建手动作业 → 从题库选题 → 保存并发布 → 选班级发放；
- **验证**：以作业/章节页面数据（班级、人数、已交/未交）证明发布成功；
- **资料库**：上传讲义、题库等资料到课程资源中心；
- **流程决策**：批量补发幂等续跑、跨调用事务边界、双班发布、重复副本回滚、掉线后只补差集；
- **思维链执行**：每次任务先写出链（终态／前置检查／事务边界／验证断言／回退路径），批量任务填执行台账，逐步更新、断言失败即停、留续跑点。

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
