# 学习通原子操作手册

> 记录格式：**前提/界面特征 → 触发 → 失败原因 → 成功方法 → 目的**
> 只沉淀"下次能省时间"的非显而易见知识。一次性业务数据（题号、人名、具体班级号除作示例外）不记。
> 环境：ego-browser（nodejs 脚本），通过 Bash 调用 `ego-browser nodejs <<'EOF' ... EOF`。

---

## 全局机制（跨所有原子操作）

| 编号 | 现象 | 根因 | 应对 |
|---|---|---|---|
| G1 | 每次 nodejs 调用后页面回到新标签/门户，上一步状态丢失 | ego-browser 的 taskSpace 在脚本进程结束时释放页面 | 完整流程塞进单次调用；或下一步用 `goto(已知URL)` 重建 |
| G2 | `@N` 报 `Unknown ref` | ref 只在本次 snapshot 后的调用内有效 | 用 ref 前先 `await page.snapshot()`；跨调用一律重新 snapshot 或用 DOM 定位 |
| G3 | 文本点击匹配到多个元素报 ambiguity | 页面多处同名文本 | 用更精确 selector / CSS / DOM evaluate |
| G4 | `page.click` 超时"element has zero-sized bounding box" | 元素被 CSS 隐藏或浮层定位 | 改 DOM 事件触发或真实坐标点击（见 A6/B5） |
| G5 | 打开教师端页面偶尔 `net::ERR_NETWORK_CHANGED` | 网络瞬断 | 直接重试同一 goto |

**常用直连 URL（重建现场用）**
- 课程门户：`https://mooc2-ans.chaoxing.com/mooc2-ans-vue/fanyav3/tch?courseId=<cid>&clazzId=<clazz>&cpi=<cpi>&enc=<enc>&t=<ts>&v=6&perspectiveType=0&ut=t`
- 题库列表：`https://mooc2-ans.chaoxing.com/mooc2-ans/qbank/questionlist?courseid=<cid>&clazzid=<clazz>&cpi=<cpi>&...&ut=t`
- 章节编辑器：`https://mooc1.chaoxing.com/edit/chapters/<cid>/<chapterId>?classId=<clazz>&cpi=<cpi>&newMooc=true&mooc2=1&openc=<token>`
- 作业编辑器：`https://mooc2-ans.chaoxing.com/mooc2-ans/work/goToWorkEditor?courseid=<cid>&clazzid=<clazz>&mooc=1&workid=<workid>&cpi=<cpi>&built=1&from=`
- 发放设置：`https://mooc2-ans.chaoxing.com/mooc2-ans/work/library/setting?courseid=<cid>&cpi=<cpi>&workLibraryId=<workid>&fromCreate=1&from=`
- 作业列表（验证）：`https://mooc2-ans.chaoxing.com/mooc2-ans/work/list?courseid=<cid>&selectClassid=<clazz>&cpi=<cpi>&v=0&topicid=0&from=`
- 题库选题页（作业内）：`https://mooc2-ans.chaoxing.com/mooc2-ans/work/qtbank?built=1&courseid=<cid>&clazzid=<clazz>&workid=<wid>&cpi=<cpi>&mooc=1&...`

---

## 任务 A：题库

### A1 下载官方导入模板确认列结构
- **前提/界面**：题库 → 批量导入 → 模板导入弹窗，有"Excel模板下载"。
- **触发**：`page.waitForEvent('download')` + 点击下载链接 → `dl.saveAs(...)`。
- **失败原因**：无。用 xlrd 读取老式 .xls（环境需先装 `xlrd xlwt`，且 pip 前设 `CODEBUDDY_SAFE_DELETE_ENABLED=0` 并清空 http(s)_proxy）。
- **成功方法**：模板 20 列 = 目录/题目类型/自定义题型/大题题干/小题题型/小题题干/正确答案/答案解析/难易度/知识点/标签/选项数/选项A~H。单选：选项数=4，答案 A~D；判断：选项数=2，选项A=正确、B=错误，答案 A(对)/B(错)。
- **目的**：生成与官方完全兼容的导入文件，避免列错位导致导入失败。

### A2 批量导入题库文件
- **前提/界面**：题库列表，顶部"批量导入"anchor。
- **触发**：
  1. `await page.snapshot()` → 点"批量导入"（ref 需当次快照）→ 点"模板导入"。
  2. `const chooserP = page.waitForFileChooser()` → 点"Choose File" → `chooser.setFiles(绝对路径)`。
  3. 等待解析 → 弹窗显示"共N条数据，成功导入N条" → 点"确定"。
- **失败原因**：
  - `page.setInputFiles("input[type=file]")` 失败：有两个隐藏 file input，无法确定目标。
  - `page.click("text=Choose File")` 超时：该文本在 button 内，需解析快照里 `button [ref=N] text "Choose File"` 拿 ref 再点。
- **成功方法**：用 `waitForFileChooser` + 点击按钮 ref，再 `chooser.setFiles`。正则从快照提取：
  `snap.match(/button \[ref=(\d+)\][\s\S]{0,40}text "Choose File"/)`。
- **目的**：把题目批量写入题库，并自动按模板"目录"列建文件夹。

### A3 生成题库 xls
- **触发**：运行 `scripts/gen_qbank.py`（改题库内容/目录名后）。
- **目的**：复用官方列结构，输出 `.xls` 到工作区 outputs。

---

## 任务 B：章节编辑器（ExtJS，踩坑最多）

### B1 打开章节编辑器并取直连 URL
- **前提/界面**：课程门户 → 章节应用 → 显示目录树，顶部"编辑章节"anchor。
- **触发**：`waitForEvent('popup')` + 点"编辑章节" → 新标签 p2 即编辑器，读取其 url 备用。
- **失败原因**：后续调用若不 goto 该 URL，页面会重置（G1）。
- **成功方法**：把 url 记下，之后用 `p.goto(编辑器URL)` 直接重建。
- **目的**：获得稳定可重入的编辑器现场。

### B2 新建子目录（在指定父目录下）
- **前提/界面**：编辑器目录树；底部有"同级目录"/"子目录"两个 anchor。
- **触发**：点击父目录行（如 `text=第一序列`）选中 → 点"子目录" → 生成"1.x 新建课程目录"。
- **失败原因**：**跨多次调用重复执行会累积多个空"新建课程目录"**（因为每次建完没重命名/保存就重置，但目录已写入）。本次累积了 1.2~1.5 四个，最后不得不逐个删。
- **成功方法**：建目录 + 重命名 + 删除多余，尽量在一次调用内连做；若已累积见 B5 删除。
- **目的**：建立目标章节位置。

### B3 重命名目录
- **前提/界面**：目录行选中后，DOM 出现浮层 `span.EidtIco`，内含 `a.list_rename` / `a.popMoveBnt` / `a.list_delete`。
- **触发**：
  1. **必须用真实鼠标选中行**：`page.click('tr#treeview-...-record-<id>')`（见下方失败原因，DOM click 会导致重命名框不出）。
  2. `page.evaluate(() => document.querySelector('a.list_rename').click())` → 出现输入框 `input.x-form-text`（值为旧名）。
  3. `page.fill('input.x-form-text', '第二章')` → `page.press('input.x-form-text','Enter')`。
- **失败原因**：
  - ⚠️ **关键（2026-11-17 补）**：若用 `page.evaluate(() => tr.click())` 这种 DOM click 选中行，`a.list_rename` 虽存在但点击后**不出输入框**（`input.x-form-text` 匹配 0），实测卡住多轮。改用 `page.click(行selector)` 真实鼠标点击后，同样流程立即成功。根因：ExtJS 的 EidtIco 浮层依赖真实鼠标事件定位/激活。
  - 双击 `tr ... .x-tree-node-text` 不好使，报"zero-sized bounding box"或不出输入框。
  - 原生 `element.click()` 对 `a.list_rename` 有效（前提是行已用真实鼠标选中），但对 `a.list_delete` 无效（见 B5）。
- **成功方法**：`page.click(行)` 真实选中 → `a.list_rename` DOM `.click()` → fill `input.x-form-text` → Enter。**重命名即时持久化，无需点保存**。
- **批量建章正确姿势（2026-11-17 补）**：在单次调用内循环「真实点父目录 → DOM click `a.addchild` 建子目录 → 立即读新建行的 recordid（筛 `data-qtip` 含"新建课程目录"的最后一行）→ 真实点该新行 → 重命名」，避免跨调用重置累积空目录。本次一次建成 1.3~1.6 四个章节零残留。
- **目的**：把"新建课程目录"改为目标章节名。

### B4 读取目录树结构（精确定位）
- **触发**：
  ```js
  page.evaluate(() => [...document.querySelectorAll('tr.x-grid-data-row')]
    .map(tr => ({id:tr.id, idx:tr.querySelector('td')?.textContent.trim(), name:tr.getAttribute('data-qtip')})))
  ```
- **返回示例**：`{id:"treeview-1094-record-1286641501", idx:"1.2", name:"新建课程目录"}`。
- **目的**：拿到 recordid 供 B3 重命名 / B5 删除精确使用；确认清理结果。

### B5 删除目录（本次最大踩坑，反复不生效）
- **前提/界面**：选中目录行后出现 `a.list_delete`（在 `span.EidtIco` 浮层内）。
- **触发链**：`a.list_delete` → **ExtJS 自定义确认框** `.x-window`（文本"删除若该目录下存在子目录将一并删除，是否确定删除？"，含"确定/取消"按钮）→ 点确定。
- **失败原因（逐条排除，务必记住）**：
  1. `page.click('a.list_delete')` → 超时"zero-sized bounding box"：浮层图标 rect 恒为 (0,0)，真实鼠标点不到。
  2. `a.click()`（原生 DOM click）→ **无确认框弹出**：ExtJS 用自定义事件系统，原生 click 不触发其 handler。
  3. `jQuery(a).trigger('click')` → **能触发确认框**（前半段有效）。
  4. `window.confirm = () => true` 覆盖 → 无效：确认框是 ExtJS 自定义 `.x-window`，不是原生 confirm。
  5. `page.acceptDialog()` → 无效：同上，不是原生 dialog。
  6. `jQuery(确定按钮).trigger('click')` / `确定按钮.click()` → **无效**：ExtJS 按钮同样不吃原生/jQuery click。
- **成功方法（唯一验证有效）**：
  1. `window.jQuery('a.list_delete').trigger('click')` 触发确认框。
  2. 读取 `.x-window` 内确定按钮真实坐标：
     ```js
     const win = [...document.querySelectorAll('.x-window')].find(w=>w.offsetWidth>0 && w.textContent.includes('是否确定删除'));
     const b = [...win.querySelectorAll('a.x-btn-button')].find(x=>x.textContent.trim()==='确定' && x.offsetWidth>0);
     const r = b.getBoundingClientRect(); return {x:r.x+r.width/2, y:r.y+r.height/2};
     ```
  3. `await page.mouse.click(box.x, box.y)` —— **真实鼠标点击确定按钮**才生效。
  4. 删除即时持久化（无需保存）。
- **目的**：清理累积的空目录。核心教训：**ExtJS 删除 = jQuery trigger 触发框 + 真实鼠标点确定，两步缺一不可**。

---

## 任务 C：章节测验任务点

### C1 创建测验并挂载
- **前提/界面**：编辑器选中目标章节，右侧内容区工具栏有"测验"。
- **触发**：点"测验" → 弹层选"创建新测验" → 填标题 → 确定 → 新标签打开"新建章节测验"编辑器。
- **失败原因**：无特别坑，但注意新标签又是一次调用，需重新 goto 或抓 popup。
- **目的**：在章节下建立测验载体。

### C2 从题库选题
- **前提/界面**：章节测验编辑器有"选题" → "从题库选题"。
- **触发**：进入题库选题页 → 展开文件夹 → 勾选题目 → "完成选题"。
- **失败原因**：全选 checkbox 常是禁用态（`checkbox [ref=..]` disabled），点不动。
- **成功方法**：展开文件夹后逐个勾题目 checkbox（本次 ref=34~53），或 DOM 批量勾。
- **目的**：把题库题目放进测验。

### C3 任务点与开放
- **界面**：测验卡片有"任务点"复选框；章节列表有"开放状态"。
- **注意**：任务点默认已勾选；点击它会弹"取消任务点将删除学习记录"——若非本意用 `dismissDialog()` 取消该操作。
- **发布机制**：学习通章节测验**无独立发布按钮**；章节状态"开放" + 测验为任务点 = 对该班级学生生效。
- **目的**：理解"发布"的正确含义，避免找不存在的发布按钮。

---

## 任务 D：作业发布（用户说"发到作业里"时的正解）

### D1 新建手动作业
- **触发**：门户 → 作业 → 新建作业 → 手动创建 → 新标签 p2 作业编辑器。
- **界面**：标题 `input[name=title]`；"保存并发布" anchor；题量/总分显示区。
- **目的**：区别于章节测验，创建独立作业。

### D2 作业内从题库选题（与 C2 不同实现）
- **前提/界面**：作业编辑器点"选题" → "从题库选题" → 题库选题页。
- **触发**：展开文件夹 → 勾选题目 → 完成选题。
- **失败原因**：
  - 逐个 `page.click('@ref')` 中途报 `Unknown ref` —— 勾选后列表重排导致 ref 失效。
  - 全选 checkbox 禁用。
- **成功方法（关键）**：用 DOM 批量勾选，绕开 ref：
  ```js
  const cbs = [...document.querySelectorAll('input[type=checkbox].item')];
  cbs.forEach(c => { if(!c.checked) c.click(); });
  ```
  题目 checkbox 特征是 `input[type=checkbox].item`，父 li class 含 `list questions questionBank`。完成后"已选 20"。
- **目的**：稳定选中全部题目。

### D3 保存并发布 → 发放设置
- **触发**：编辑器点"保存并发布" → 跳到 `/work/library/setting?...&workLibraryId=<workid>`。
- **界面**：发放对象（anchor）、有效时段、高级设置；底部"发放"按钮。
- **注意**：用户要求"不设置其他项"时，保持默认即可（学习通允许无截止时间）。
- **目的**：进入发放环节。

### D4 选择发放班级（易错）
- **前提/界面**：点"发放对象" anchor → 弹窗列出班级（如"智能2401，02，03"、"默认班级"）。
- **触发**：
  1. 打开发放对象：DOM 找 `a` 文本==='发放对象' 且 offsetWidth>0 的元素点它（文本点击有 3 处匹配会 ambiguity）。
  2. 勾选班级：`page.evaluate` 找 `a.classData[data="<clazzId>"]` → `closest('li').querySelector('.class_check_one')` → 若未 `class_checked` 则 `.click()`。
  3. 点弹窗"确认" → 发放对象区显示班级名。
- **失败原因**：点班级名文本只是**展开学生列表**，并未勾选班级；班级复选框是 `span.class_check_one`，初始未勾选。
- **成功方法**：点 `.class_check_one` 直到其 class 含 `class_checked`（其下学生随之全选）。班级 clazzId 从 URL/课堂参数取。
- **目的**：确保作业发放给正确班级。

### D5 点击发放
- **触发**：确认对象后点"发放" anchor。
- **现象**：点击后页面 URL 加 `#` 或跳转/关闭，target 失效属正常，通常表示已提交。
- **失败原因**：不能仅凭"页面跳转"判定成功。
- **成功方法**：必须走 D6 验证。
- **目的**：提交发布。

### D6 验证发布结果
- **触发**：`goto(作业列表URL)` → 快照/截图。
- **关注**：作业名称、发放班级、作答时间、统计 `0待批 / X已交 / Y未交`（Y = 已收到作业的人数，即发放成功人数）。
- **失败原因**：直接 `newPage()` 后被重置（G1）；用 `task.page('p1')` goto 更稳。
- **目的**：以数据证明发布成功，而非推测。

---

## 任务 G：课程资料库上传（2026-11-17 新增）

### G1 上传资料到"资料库"
- **入口**：课程门户 → 左侧"资源中心" → 卡片"资料库" → "添加资料" → "本地上传"。
- **界面**：本地上传是拖拽区 + "选择本地文件"anchor + "选择本地文件夹" + 一个隐藏 file input（button "Choose Files"）。
- **失败原因（逐条排除）**：
  1. 点"本地上传"后 `waitForFileChooser` 超时：本地上传只是**展开上传面板**，不直接弹 chooser。
  2. `page.click('text=选择本地文件')` 报 ambiguity：同时匹配到"选择本地文件夹"。
  3. `page.setInputFiles('input[type=file]')` 报"3 elements matched, all hidden"：页面有 3 个隐藏 file input，无法定位。
  4. 从资源中心点"资料库"偶尔跳到"章节"页：iframe 未加载完就点，或文本匹配错位——延长等待到 1.7s 并在快照确认含"课件库/共建设"。
- **成功方法（唯一验证有效）**：从快照正则解析"选择本地文件"anchor 的 ref：
  `s.match(/anchor \[ref=(\d+)[^\n]*\]\s*\n\s*text "选择本地文件"/)`（注意文本独占下一行，不是同行）。
  然后 `const chooserP = page.waitForFileChooser(); page.click('@'+ref); const c = await chooserP; c.setFiles([绝对路径数组])`
  —— `setFiles` 支持一次多文件。上传后等 5-7s，资料库文件列表出现文件名即成功。
- **注意**：若资料库非空，"添加资料"文本点击可能偶发 matched 0，重试一次或延长等待即可。
- **目的**：把讲义 docx、题库 xls 等沉淀为课程资料。

### G2 教师端页面间切换的等待
- 门户 iframe 内点击（资源中心、资料库、作业等）后需等 1.5-1.8s 再快照/下一步，否则点到旧页面元素。

---

## 任务 E：复盘沉淀

每次操作结束，把新发现的原子操作按本文件格式追加。重点补：
- 新遇到的 ExtJS / 浮层 / 确认框触发方式；
- 任何"试了 N 次才成功"的操作及其失败原因清单；
- 新的直连 URL 模板。

不要补：一次性题号、学生姓名、单次时间戳（除非作为格式示例）。
