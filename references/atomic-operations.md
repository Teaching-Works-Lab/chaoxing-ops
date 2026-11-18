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
- ⚠️ **关键（2026-11-18 补）：`input.x-form-text` 零尺寸（rect 0,0,0,0）的真正根因是目标行在视口外**。ExtJS 把单元格编辑器定位到屏幕外，导致 `page.fill` 报"zero-sized bounding box"。
  - **成功方法**：重命名前先 `document.getElementById(rid).scrollIntoView({block:'center'})` 让行进入视口，再走"真实 click 行 → hover → a.list_rename DOM click → 探测 input 宽>0 → fill → Enter"。本次 W1–W12 用此法一次成功，零残留。
  - **无效尝试（勿重复）**：DOM 设 value + dispatchEvent(input/change)、CDP `Input.dispatchKeyEvent` 发 Enter、`Ext.getCmp(editorId).completeEdit()`、`field.setValue()+completeEdit()`——这些能让输入框值变化，但**树不更新**，因为绕过了 ExtJS 与 tree cell 的绑定。根因是定位不是事件，回视口才是正解。
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
- **前提/界面**：点"发放对象" anchor → 弹窗列出班级（如"教学班A"、"默认班级"）。
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

### D7 题库选题必须等"题目层"再勾选（2026-11-18 新增，最关键坑）
- **前提/界面**：作业编辑器 → 选题 → 从题库选题，进入题库页后是一列 `li.list-folder` 文件夹。
- **触发**：`page.evaluate(f => searchDirec(f, courseid), folderId)` 进入某周文件夹，然后勾选题目。
- **失败原因（血泪）**：`searchDirec` 是异步的。若调用后立刻勾选 `input[type=checkbox].item`，
  此时 DOM 里还是**文件夹层**的 12 个 checkbox（文件夹本身也带 `.item`），会勾中 12 个文件夹；
  点"完成选题"弹出 JS alert **"请选择题目"**，整个作业创建失败且不留草稿（作业库/列表均无痕迹）。
  固定 `waitForTimeout` 也不可靠——页面切换时长抖动。
- **成功方法（唯一验证有效）**：`searchDirec` 后用 `waitForFunction` 等**题目层三标志同时成立**：
  ```js
  await E.waitForFunction(() =>
    /已选\s*\d+\s*题/.test(document.body?.innerText||'') &&   // 底部"已选N题"按钮出现
    document.querySelectorAll('input[type=checkbox].item').length === 4, // 恰好4题（文件夹层是12）
    undefined, {timeout:15000});
  ```
  再读 DOM 校验三标志：`li.list-folder` 数量=0、`.item` 数=4、含"已选N题"。
  勾选后验证"已选 4 题"（`body.innerText.match(/已选\s*(\d+)\s*题/)`），
  完成选题后验证编辑器 URL 回到 `goToWorkEditor` 且含"题量 4"。任一不符立即停止，绝不带病往下走。
- **注意**：alert 弹出时下一次 evaluate 会抛 `PageDialogOpenedError`，需先 `acceptDialog()` 清理。
- **目的**：根除"批量发作业产生半成品/静默失败"——实测一批 12 个作业中曾有 2 份因此失败，改用本方法后 100% 成功。

### D8 新建作业的可靠打开方式（2026-11-18 新增）
- **触发**：作业列表 → 新建作业 → 手动创建 → 编辑器 popup。
- **失败原因**：① "手动创建"下拉项需**先 hover「新建作业」**才出现（坐标约 112,68），直接 click 不展开；
  ② 找 ref 的循环若不在首次命中处 return，会把相邻行的多个数字拼成 `@[ref=184,184` 非法选择器；
  ③ 编辑器标签每次递增，跨调用硬编码 `task.page('p4')` 必失败（标签已被回收）。
- **成功方法**：
  1. `await p1.mouse.move(112,68); await p1.waitForTimeout(800);`
  2. `const s = await p1.snapshot();`
  3. 严格正则取**紧邻单个 ref**：`s.match(/anchor \[ref=(\d+)[^\]]*\]\s*\n\s*text "手动创建"/)`
  4. `const before=(await task.tabs()).map(t=>t.label); const pp=p1.waitForEvent('popup',{timeout:10000}).catch(()=>null);`
     `await p1.click('@'+m[1]); const ed=await pp;`
  5. 编辑器标签 = `(await task.tabs()).map(t=>t.label).find(l=>!before.includes(l))`，用差集动态取，勿硬编码。
- **注意**：`goto` 后 `document.body` 可能为 null，须先 `waitForFunction(()=>!!document.body&&...)` 再 evaluate。
- **目的**：稳定打开作业编辑器，支撑批量发布。

### D9 批量发作业抗掉线策略（2026-11-18 新增）
- **现象**：连续快速发作业时，学习通会把**所有标签页**登录态一起踢到登录页（账号级失效），
  需用户重新扫码（Agent 无凭据）。
- **策略**：① 每个作业发布后 `goto` 作业列表验证标题出现再进下一个；
  ② 列表页判重——标题已存在则 SKIP（可从中断处安全续跑，不重复创建）；
  ③ 单个作业任一校验失败即 `throw` 停止，不连锁产生半成品；
  ④ 掉线后凭清单从缺失处续发。
- **注意**：一次 nodejs 调用串行发 6 个作业会超单次超时被 SIGTERM，但**已发的作业仍会保存成功**——
  被终止后先查作业列表确认实际进度，再补发缺的，切勿整体重跑。
- **目的**：把"掉线/超时"造成的损失降到最低，保证最终 12 个作业齐全。

### D10 从作业库直接"发布"到另一个班级（2026-11-18 新增，二次发放利器）
- **场景**：已发布的作业（作业库里已有）要再发给**另一个班级/教学班**。不要逐个新建，直接复用作业库那份发布。
- **入口 URL（可直接 goto）**：
  `https://mooc2-ans.xuexitong.com/mooc2-ans/work/library/setting?courseid=<cid>&cpi=<cpi>&workLibraryId=<作业库ID>&from=`
  作业库 ID = 作业库列表每行 `ul.dataBody_td[data="<id>"]` 的 data 值（`a.rename_title` 的标题可用于匹配编号）。
- **触发**：作业库列表 → hover 目标作业行 → 每行 `a.jb_btn`（文本"发布"）→ popup 发布设置页；
  或直接 goto 上面的 URL 最稳（popup 标签易在 navigate 时 target 失效，用主标签 goto 更可靠）。
- **发布设置页结构**：顶部"发放对象"anchor → 弹窗列出 `a.classData[data="<clazzId>"]`；
  底部"发放"anchor；成功标志 `body.innerText` 含"发布成功"。
- **班级是否已发布判定**：`a.classData[data="<clazzId>"]` 的 `pubstatus` 属性：`'0'` 已发布、`'-1'` 未发布。
  勾选用 `closest('li').querySelector('.class_check_one')`，若 class 不含 `class_checked` 则 click（同 D4）。
- **成功方法（批量稳健版）**：
  ```
  for each job:
    goto(SET_URL + workLibraryId)
    waitForFunction(/发放对象/.test(body))
    evaluate 点"发放对象"anchor → waitForFunction(classData 出现)
    evaluate: 若 pubstatus!=='0' 且未勾 → 点 .class_check_one 到 class_checked
    evaluate 点"确认"(a.jb_btn_92) → 校验 body 含班级名
    evaluate 点"发放"(a.jb_btn) → waitForFunction(/发布成功/)
    单个 try/catch，pubstatus==='0' 则 SKIP（天然可续跑、防重复）
  ```
- **失败原因**：① 用 popup 标签循环 goto 会 "No target with given id found" → 用主标签 p1；
  ② `waitForFunction` 的 arg 要作为第 2 参数传入，回调里用形参，别用 `arguments[0]`（箭头函数无 arguments）。
- **验证**：切到目标班 `work/list?...&selectClassid=<clazzId>`，看作业数、班级标签、未交人数（=该班学生数，证明真发放）。
- **目的**：把已建好的作业二次发放到新班级，零重建、可续跑。

### D11 新建"简答题/主观题"作业（UEditor 富文本 + AI 批阅，2026-11-18 新增）

- **场景**：要出简答/论述/评析/改错类**主观题**（如提示词构造题、提示词评析改错题）。学习通作业编辑器可直接加简答题，不必走题库模板。
- **入口**：作业库 → hover「新建作业」→ 菜单点「手动创建」→ popup 打开 `work/goToWorkEditor?...workid=`（编辑器在新标签）。
- **题型**：编辑器"添加题目"区有 单选题/多选题/填空题/判断题/**简答题**/更多；点「简答题」即加一题。
- **题干/参考答案/解析都是 UEditor**（不是 textarea！）：
  - `textarea[name="content"]` 尺寸为 0，`fill()` 无效。
  - 正确写法：`UE.instants['ueditorInstant0']`=题干、`['ueditorInstant1']`=参考答案、`['ueditorInstant2']`=解析（0/1/2 顺序按页面字段出现顺序）。
  - **必须用已存在的实例对象**：`UE.instants['ueditorInstant0'].setContent(html, false)`。
  - ⚠️ 不要用 `UE.getEditor('ueditorInstant0')`——会触发重新渲染并报错，内容写不进去。
  - HTML 里避免裸 `<` `>`；要加粗用 `<strong>`，引用原文用 `<blockquote><p>…</p></blockquote>`（编辑器能正常渲染）。
- **分值**：`input#score` 默认 `5.0`，但评分机制默认"百分制"且 `input#questionScoreRatio=100`，单题时总分即 100。
  多题且要自定义分值 → 先选评分机制「自定义（自行设置每道题的分值）」，再逐题改 `input#score` 并 dispatch `input`/`change`。
- **开启 AI 批阅**：`a.useAi`（外层 `.kaiguan` 是容器，点容器无效）。
  - 开启前：`<i style="left: 2px">`；开启后：class 增加 `ai-Dgblue`、`<i style="left: 18px">` ← 以此判断成功。
  - 开启后 AI 会结合题干+答案+得分点给推荐分与批语；参考答案里写清"评分标准/区分点"效果最好。
- **保存与发布（关键坑）**：`document.querySelectorAll('a')` 里找到"保存并发布"再 `a.click()` **无效**（页面无反应、无提示）。
  必须：`snapshot` 取顶部锚点 `anchor [ref=3] text "保存并发布"` → `page.click("@3")` 真实点击。
  成功后**同一标签**跳到 `work/library/setting?…&workLibraryId=<新ID>&fromCreate=1`。
- **发放**：在发放设置页走 D10 的"发放对象 → 勾班级 → 确认 → 发放"，成功标志"发布成功"。
- **验证**：切各班 `work/list?...&selectClassid=<clazzId>`。
  ⚠️ **刚发布的作业首次进列表可能显示"0 未交"**（统计延迟），`reload()` 一次即变为正确人数（如 69 / 70）；不要据此判定发放失败。
- **目的**：把"考提示词/AI 编程能力"这类无法用客观题考的能力，落成可在学习通批阅（且能 AI 预批）的主观题。

### D12 多题型题库导入（5 种题型一次导入）+ 题干 HTML 转义（2026-11-18 新增）

- **场景**：一份作业要"题型齐全"（单选/多选/填空/判断/简答），走题库 xls 一次导入再"从题库选题"最省事。
- **官方模板 `importQuestionTemplateNew.xls` 各题型正确格式（实测）**：
  | 题型 | 正确答案列 | 选项数 | 选项A~ 列 |
  |---|---|---|---|
  | 单选题 | 字母，如 `C` | 4 | 选项内容 |
  | 多选题 | 连写字母，如 `BCD` / `ABC` | 4 | 选项内容 |
  | 判断题 | `A`(对) / `B`(错) | 2 | `正确` / `错误` |
  | **填空题** | **留空** | **空数**（单空=1） | **依次填每空答案**；一个空多答案用 `;` 隔开 |
  | **简答题** | **填 `A`** | **1** | **参考答案全文**（可很长） |
  - 常见错误：把填空/简答的答案写进"正确答案"列 → 导入后答案丢失或错位。
  - 说明行（第 2 行）必须删除，模板自带"导入前请删除此行"。
- **⚠️ 题干会被按 HTML 渲染，裸 `<` `>` `&` 会被吞/解析乱**：本次 C 代码题干中
  `#include <stdio.h>` 被吞成 `#include`、`n < MAXN` 变 `n`、`&&` 丢失。
  - **解法**：写 xls 前对题干/选项/答案解析统一转义：`& → &amp;`、`< → &lt;`、`> → &gt;`（顺序：先 & 再 < >）。
  - 验证方法：导入后进文件夹读 `document.body.innerText`，断言 `includes('#include <stdio.h>')`、`includes('n < MAXN')`、`includes('&&')` 且不含 `&lt;` 字面。
- **⚠️ Python 字符串里的 `%`**：未做 `%` 格式化时写 `%%s` 会原样输出成 `%%s`（学生看到两个百分号）。直接写 `%s`。
- **导入结果判定**：弹窗"共N条数据，成功导入N条"；大纲页总数 +N；**题型下拉计数需 `reload()` 后才刷新**（缓存），导入后不要用旧计数判断失败。
- **从题库选题的两个致命点**：
  1. **"选题 → 从题库选题 → 进文件夹 → 勾选 → 完成选题"必须在同一次 nodejs 调用内完成**。跨调用（或中途换标签）会让编辑器重建为空白：`workid=` 变空、题量 0、标题回默认"新建作业<时间戳>"，选题结果全部丢失。
  2. **"保存并发布"必须用 snapshot 锚点 `@ref` 真实点击**，DOM `a.click()` 无反应（见 D11）。
- **删除已发布作业的坑**：在**作业库**删除作业，**不会**撤销已发放到班级的副本 → 班级作业列表仍残留旧作业，学生会看到两条。
  - 彻底清理：作业库删除后，再到每个班的 `work/list` 里 hover 该行 → 点行内"删除" → 确认（"删除后可在回收站还原"）。按"作答时间"区分新旧两份。
- **目的**：一次作业覆盖全部题型与全部知识单元，且题干代码原样正确显示。

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

### G3 资料库新建文件夹：默认名与重命名（2026-11-18 新增）
- **现象**：点"新建文件夹"弹窗，里面有输入框（初始 value="新建文件夹"）、共享范围（公开/私密/部分可见）、确定按钮。
  用 DOM setter 改 input.value 后点确定，**文件名仍是"新建文件夹"**——框架不认合成事件的值。
- **成功方法（重命名）**：文件夹行的 HTML 里藏了 `div.rename_con`（display:none），内含
  `input#renameEnter`（value=原名）和 `a#renameFolderName`（确认）。直接 DOM 操作：
  ```js
  const ul=document.querySelector('ul[id="<folderId>"]');
  ul.querySelector('.rename_con').style.display='block';
  const inp=ul.querySelector('#renameEnter');
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(inp, 新名);
  inp.dispatchEvent(new Event('input',{bubbles:true}));
  ul.querySelector('#renameFolderName').click();  // 提交
  ```
  双击 `a.rename_title` 或 jQuery trigger dblclick 都**不触发**编辑框，必须显式显示 rename_con。
  文件夹 id 从 `ul[data-name][id]` 取，或从 `input[name=checkdelete]` 的 value 取。
- **进入文件夹**：点 `a.rename_title`（用 `getElementById` 取，靠 title 属性匹配会因空格失败）。

### G4 批量上传多文件 PDF（2026-11-18 新增）
- 上传面板一次最多 50 个文件、单个最大 1G；文件名不能含特殊字符 `~!@#$%^&*+<>?:"{},\;[]/`（中文和 `_` `-` 可以）。
- `chooser.setFiles([绝对路径数组])` 支持一次多选。但**30 个文件一次上传耗时 > 单次调用超时**，
  建议每批 10 个，分批后 `waitForTimeout(12-16s)`，再读 `a.rename_title[title$=".pdf"]` 的数量验证。
- 上传是异步的：setFiles 后立刻读列表可能只显示部分（"等待上传..."状态），需多等一会直到计数稳定。
- **md 转 PDF（Windows，2026-11-18）**：weasyprint 缺 GTK/Pango 系统库不可用；用 `markdown`+`reportlab` 可行。
  中文字体注册 `TTFont('CN','C:/Windows/Fonts/simsun.ttc',subfontIndex=0)` + `simhei.ttf` 作粗体。
  坑：simsun 不含 U+2212(−)/U+2013(–)，转前替换成 `-`；markdown 会把 `<stdio.h>`、`行<n` 当 HTML 标签，
  需先把 reportlab 标记（b/i/font/br/u）用占位符保护，再转义所有裸 `<`/`>`，最后还原占位符，否则 paraparser 报 "unclosed tags"。
  脚本见项目 `learning/教学设计/md2pdf.py`。

---

## 任务 E：复盘沉淀

每次操作结束，把新发现的原子操作按本文件格式追加。重点补：
- 新遇到的 ExtJS / 浮层 / 确认框触发方式；
- 任何"试了 N 次才成功"的操作及其失败原因清单；
- 新的直连 URL 模板。

不要补：一次性题号、学生姓名、单次时间戳（除非作为格式示例）。
