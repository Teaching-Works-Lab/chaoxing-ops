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

### D14 批量补发时列表统计延迟与权威判据（2026-11-24 新增）

- **场景**：从作业库批量补发 28 份作业到某班，每份页面都出现"发布成功"，`work/list` 条数也对（38/38）。
- **现象**：刚发布完的作业在 `work/list` 里显示 `作答时间：当天HH:MM（无截止）`、`0待批 0已交 0未交`，看起来像没发给学生。
- **判定**：`reload()` 后仍是 0——这不是发放失败，是统计刷新延迟（发放侧的 `pubstatus` 已立即变 `'0'`）。
- **权威判据**：逐份 `goto` 发放设置页，读 `a.classData[data="<clazzId>"]` 的 `pubstatus`——`'0'` 即已发放。批量验证以它为准，不要只看 `work/list` 的已交/未交。
- **注意**：由于发放设置页默认起始时间是当前时刻、结束时间留空，新发作业在列表里显示"当天时刻、无截止"，这是保持默认设置的结果（D3）。
- **目的**：避免把"统计延迟"误判为发放失败而重发，造成重复副本（P4 回滚代价高）。

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

### G5 大文件 docx 上传静默失败 + 瘦身方案（2026-11-18）
- **现象**：按 G1 流程上传 5MB 级 docx，列表短暂出现「等待上传...」行，随后行消失，**刷新后文件从未入库**（「当前页共 N 个」不增加）。36KB 测试 docx 与 1.5MB html 均正常入库 → 体积阈值大约在 2–5MB 之间，且**无任何报错提示**。
- **误判风险**：面板内的文件名 chip 会一直显示，轮询"列表含文件名"会误判成功；只有 **reload 后按「当前页共 N 个」计数**才是权威判据。
- **成功方法**：把 docx 里的 `word/media/*.png` 用 PIL 压成 JPEG（maxw=1400、q=85），同步改 `[Content_Types].xml` 加 jpg Default、`word/_rels/document.xml.rels` 的扩展名；5.3MB→0.83MB 后一次成功。LibreOffice 转 PDF 目检确认画质可接受（A4 下约 240dpi）。
- **目的**：避免"上传成功"假象与无限重试。
- **首次记录日期**：2026-11-18。

### G6 引用相对路径图片的 HTML 资料必须先内嵌（2026-11-18）
- **现象**：html 里 `src="./figures/png/*.png"` 单独上传后，学生打开全是裂图。
- **成功方法**：预处理把图片转 JPEG data URI 内嵌，产出「单文件版」再上传（8 张 5.3MB png 压缩后 html 约 1.5MB，直接可开）。上传面板接受 .html 类型。
- **目的**：资料库单文件即用，不依赖 zip 解压。
- **首次记录日期**：2026-11-18。

### G7 资料页 iframe 同源可直接 contentDocument 操作（2026-11-18）
- **现象**：勾选文件行 checkbox 用 `@ref` 点击被行内 `<img>` 拦截（intercepts pointer events）。
- **成功方法**：资料 iframe 与父页同为 `mooc2-ans.chaoxing.com` 同源，`page.evaluate` 里经 `document.querySelector("iframe").contentDocument` 直接 DOM 操作：`cb.checked=true` + `dispatchEvent(new Event("change",{bubbles:true}))`，工具栏「删除」随即出现；确认弹层是普通 anchor（`删除文件？` → 弹层内 `删除`/`取消`），用 ref 点击即可。
- **附带**：`coursedata` 直连 URL 的 `openc` token 离开页面后失效（刷新报"长时间没有操作或无权限"），必须从课程入口 `isNewCourse?courseId=...` 进门户后点「资料」重建，每次 enc 会变。
- **目的**：批量选中/删除/重命名等列表行操作不再受遮挡层影响。
- **首次记录日期**：2026-11-18。

### G8 「添加资料」是切换式弹层：必须可信点击 + 可见性判定（2026-11-18 晚）
- **现象**：`page.evaluate` 里 `a.click()` 合成点击**能打开下拉**，但点「选择本地文件」时 `waitForFileChooser` 必然 25s 超时——非用户手势不触发原生文件框。
- **更隐蔽的坑**：`.addData a`（添加资料）是**toggle**。若用「点一次 → 立刻读 `offsetParent`」判断，弹层动画还没结束就判负，再点一次又把它关掉，形成来回抖动，表现为「有时能开有时不能」。实测 5 次里只成 2 次。
- **成功方法**（每步都要可信点击，且每步都按**可见性**而非 `offsetParent` 判定）：
  ```js
  const visible = (txt) => page.evaluate((t) => {
    const d = document.querySelector("iframe").contentDocument;
    const vis = [...d.querySelectorAll("a,li,span,div")]
      .filter(e => e.innerText && e.innerText.trim() === t)
      .filter(e => { const r = e.getBoundingClientRect(); return r.width > 20 && r.height > 10; });
    if (vis.length) { vis[0].id = "visTarget"; return true; }   // 打临时 id 绕开多元素歧义
    return false;
  }, txt);
  // 打开弹层：先查已开，未开才点，最多 4 次，每次等 3.2s
  // 再 page.click("loc=css:#visTarget") 依次点「本地上传」→「选择本地文件」
  const chooserP = page.waitForFileChooser({ timeout: 25000 });
  await page.click("loc=css:#visTarget", { label: "选择本地文件" });
  const ch = await chooserP; await ch.setFiles([absPath]);
  ```
  给可见元素打 `id` 再 `page.click("loc=css:#id")`，比 `a.jb_btn_168` 这类 class 选择器稳（同类元素在 DOM 里有多份，第一份常是 0×0 隐藏副本）。
- **附带**：面板未展开时 `input[type=file]` **根本不在 DOM 里**（webuploader 容器随面板创建），所以"直接给隐藏 input 塞文件"这条路走不通。
- **首次记录日期**：2026-11-18。

### G9 资料页 iframe 就绪判定要 null-safe 且要等脚本初始化（2026-11-18 晚）
- **现象**：`goto` 后 `document.querySelector("iframe").contentDocument.body` 可能为 `null`（about:blank 阶段），直接 `contentDocument.body.innerText` 抛 TypeError；而 `.addData a` 已存在时脚本可能还没绑事件，立刻点击无反应。
- **成功方法**：轮询时用 `try/catch` + 逐级判空，并以 `/.addData a/` 存在作为 ready 信号；**ready 之后再固定等 3s** 让 iframe 内脚本绑定完成，再点「添加资料」。
- **附带**：`mycourse/tch?...` 直连偶发 `PageNavigationTimeoutError`（45s 未 commit），改 60s 超时 + 最多 3 次重试即可；URL 里的 `t=` 参数不能省，去掉后 iframe 不加载。
- **首次记录日期**：2026-11-18。

### D13 只给课程名时定位课程并一次读出全部作业列表（2026-11-24 新增）

- **场景**：用户只说课程名（如「智能制造装备」），要查该课程已布置的作业，没有 courseId/clazzId。
- **入口链路**：个人空间 `https://i.chaoxing.com/base?ws=1` → 左侧菜单「课程」项的 `div[role=menuitem]` 上有 `dataurl`（形如 `https://mooc2-ans.chaoxing.com/visit/interaction?s=...`），**直接 goto 这个 URL** 最稳；DOM click 菜单项不跳转，`page.click` 还会被浮层拦截报 "div intercepts pointer events"。
- **课程搜索**：课程列表搜索框 `input[placeholder="搜索"]` → `fill(课程名)` 后**必须 `press('Enter')` 才过滤**；只 fill 不回车列表不变。
- **取参数**：搜索结果的课程链接是 `mooc1.chaoxing.com/course/isNewCourse?courseId=<cid>&...&cpi=<cpi>`；goto 后跳到 `mooc2-ans/mycourse/tch?...&clazzid=<clazz>&enc=<token>&t=<ts>`，此处拿全 courseId / clazzId / cpi / enc。
- **进作业列表**：门户左侧「作业」点击后，`iframe` 里才是 `work/list?...&openc=<token>&ut=t`；直接读取该 iframe 的 `contentDocument.location.href` 并 `goto`，比跨调用点菜单稳（G1）。
- **一次读全**：在 `work/list` URL 追加 `&pages=1&size=100`，实测单次最多返回 **50 条**（超过也不分页），50 条以内一页拿全，不必翻页。
- **结构化提取**：`li[id^="work"]` 为一行；标题取 `h2.list_li_tit`，班级取 `.list_class` 的 `title` 属性，`innerText` 用 `/作答时间：(.+?)\s+0待批\s*(\d+)\s*已交\s*(\d+)\s*未交/` 取时间/已交/未交。
- **注意**：列表默认「全部班级」，不要按 `clazzid` 猜班级；跨年时当年日期会省略年份（如 `10-21`），与上一年带 `2025-` 的记录混排，按班级分组时别按年份切。
- **目的**：把「按课程名查已布置作业」从反复试错变成固定链路，且能一页拿全所有记录。

### D14 把整份 Word 试卷智能导入到「试卷库」形成试卷（2026-11-25 新增）

- **场景**：用户说「把期末考试 A 卷上传到考试/形成试卷」。这是**试卷库**导入，不是作业发布（任务 D）、也不是题库导入（任务 A）。试卷库与题库共用 `qbank/smartimport` 页面，靠 URL 里的 `paperLibraryId` 区分。
- **入口**：试卷库 `/mooc2-ans/exam/paperlist?courseid=<cid>&cpi=<cpi>` → 「新建考试」→ 编辑页 `/mooc2-ans/exam/create-exampaper?courseid=..&paperid=<pid>&cpi=..&ut=t` → 「智能导入」跳到 `/mooc2-ans/qbank/smartimport?...&paperLibraryId=<pid>`。用户若已打开该页，直接 goto 其 URL 重建现场即可。
- **必须先把 Word 转成学习通格式**（可直接上传学生卷会识别错）：下载模板 `/mooc1.chaoxing.com/import-export-ans/template/recommendedFormat.docx`（页面「推荐格式」→ `downTemplate()`），格式要点：
  - 题干前加 `【单选题】`/`【多选题】`/`【判断题】`/`【简答题】`，自定义题型（如 `【综合应用题】`）会被识别为新题型并弹确认框；
  - 每题另起一行 `答案：B` / `答案：ABC`；判断题答案写 `答案：对/错`（页面会转成 A 对 B 错）；
  - 可附 `知识点：`、`难易程度：`、`答案解析：`；简答题正文写进 `答案：`，评分细则写进 `答案解析：`。
  - 本项目生成脚本：`gen_chaoxing_import.py`（从 exam-spec + objective.json + 答案 md 同源生成），注意答案 md 用章节内题号（简答 1-4 / 综合 1-2），spec 主观题题干也在 heading 之后按出现顺序取，两者按下标对应，别按题号 key 匹配。
- **上传**：`<input type="file" id="file" accept=".docx,.md,...">` 用 `page.setInputFiles("#file", [绝对路径])`，`onchange` 自动触发 `app.upload()` 与识别；轮询页面文本「共识别 N 题，识别有误 M 题」，M 必须为 0。
- **分值**：每题分值框是 `input.score_input`（24 题 24 个，按题序），用原生 value setter + `input`/`change` 事件填入；填完核对总和=试卷满分（本项目 100）。
- **加入试卷**：点「加入试卷」→ 若含自定义题型弹「检测到新题型，是否继续」→ 点「确定」→ 弹「共 N 条数据，成功导入 N 条」→ 点确定。**此后编辑页会关闭、p2 被销毁（连接报 `page closed`/`No target with given id` 是正常完成信号，不是失败）**。
- **改标题并保存**：重新 goto `create-exampaper`，改 `input[name="examPaperTitle"]`，点「完成」→ 弹「试卷共创建 N 道题，总分 X 分，确认完成创建？」→ 确定。
- **验证断言**：试卷库 `/exam/paperlist` 列表出现该试卷行，题量=N、总分=X、创建者、时间正确。注意试卷库 URL 是 `paperlist`（小写无连字符），`examPaperList`/`paper-list` 均 404。
- **目的**：把「整卷上传成考试试卷」从试错变成固定链路，并与任务 D（发作业）区分开。

---

## 任务 H：考试模块（发布状态 / 线上判定，2026-11-25 新增）

> 考试模块和作业模块（任务 D）是**两套东西**：作业用 `work/*`，考试用 `exam/*`。用户说「考试」「监考」「批卷」走本组，说「发作业」走 D 组。整卷上传成试卷见 D14（试卷库导入），本组负责其后的发布与判定。

### H1 三个易混概念与各自入口（先分清再动手）

| 概念 | 含义 | 入口 URL |
|---|---|---|
| 试卷库 | 「卷子模板」，可反复发放；不产生学生任务 | `/mooc2-ans/exam/paperlist?clazzid=0&courseid=<cid>&ut=t&cpi=<cpi>&topicid=0&perspectiveType=0&from=` |
| 考试 | 试卷发放到班级后生成的**学生任务**，有状态（未开始/进行中/已结束） | `/mooc2-ans/exam/test?clazzid=0&courseid=<cid>&ut=t&cpi=<cpi>&topicid=0&perspectiveType=0&from=` |
| 监考 | 考试进行中的监控台 | `/mooc2-ans/exam/test/exam-monitor?courseid=<cid>&clazzid=0&firstIn=true&cpi=<cpi>&openc=` |

- **判据**：试卷库行有「发放次数」列（0 = 从未发放）；考试列表「暂无考试」= 没有任何已发布考试。两者同时成立 → 卷子备好了但没发。
- **注意**：考试列表默认「全部班级」，不要按 `clazzid` 猜班级；回收站 URL 参数是 `recyle=1`（平台拼写如此，不是 recycle）。
- 另外两个可 goto 的直连：查看试卷 `/exam/lookpaper?courseid=<cid>&clazzid=0&cpi=<cpi>&ut=&paperid=<pid>`；编辑试卷 `/exam/create-exampaper?courseid=<cid>&clazzid=0&cpi=<cpi>&paperid=<pid>&ut=t`。

### H2 发放设置页（topublish）：线上考试的判据来源

- **入口 URL（可直接 goto，最稳）**：
  `https://mooc2-ans.chaoxing.com/mooc2-ans/exam/test/topublish?taskid=0&clazzid=0&courseid=<cid>&ut=&cpi=<cpi>&paperid=<pid>&score=<满分>`
- **界面结构**：上半区 = 发放对象 / 开始与截止时间 / 考试限时 / 限时提交 / 限时进入 / 防作弊设置 / PC 与移动端考试须知 / 作答要求；「高级设置」是一个 `div.settingBtn`（默认折叠），点开后展开题目设置、交卷设置、及格标准、重做设置、试卷设置、督促设置、评分设置、生生互评；底部「取消 / 发放」。
- **线上/线下判定（实测，2026-11-25）**：
  - 该页**没有**「考试方式 / 考试类型 / 考核方式」切换开关，全文关键词扫描 `线上`=0、`考试码/考场/纸质`=0，`线下` 仅 1 次且出现在「使用超星课堂进行第二设备直播」的说明里（"教师需提前创建超星课堂线下组织直播，学生现场进入课堂开启第二设备直播"）——这是**线上线下混合监考的附加项**，不是切换考试类型。
  - 整套配置全是线上作答特征：在线监考（抓拍监控）、切屏控制、禁止多终端、只允许手机 APP 考试、考前网络环境检测/摄像头检测/截屏检测/人脸识别、允许指定 IP、生成考试码、微信端作答。
  - **结论判据**：走 `exam/test/topublish` 发放流程的考试 = **线上考试**；线下（纸质/现场）考试不走这套监考配置，不能以「第二设备直播」字样误判为线下。
- **失败原因（勿重复）**：只看页面某处出现「线下」二字就下结论；或翻遍页面找不存在的「考试方式」下拉后误判「查不到」。
- **成功方法**：以「平台把该试卷放进考试应用的发放流程 + 全套在线监考配置 + 无类型切换」三条同时成立作为线上判据，并把 `body.innerText` 的关键词命中数打印出来留证。
- **目的**：回答「这个考试是线上还是线下」时给出可复核的平台侧证据，不靠考试名称猜。

### H3 考试是否已发布（与作业 D6 统计延迟区分）

- 判 1：试卷库该行「发放次数」= 0 → 未发放。
- 判 2：考试列表 `exam/test` 显示「暂无考试」→ 无任何已发布考试。
- 判 3（已发布时）：考试列表按状态筛选 未开始 / 进行中 / 已结束，能看到该考试行才算发布成功。
- **注意**：考试的发布成功判据是**考试列表出现记录**，不是「点了发放按钮后页面跳转」，也不是 `work/list`（那是作业）。
- **目的**：与 D14「试卷入库」衔接——入库成功 ≠ 考试已发布，两者常在同一任务里连续被问到。

### H4 「新建考试」的创建方式弹层

- **触发**：考试列表页点「新建考试」→ 弹层「选择创建方式」，四个选项：手动创建试卷（手动编辑创建新试卷）/ 自动随机组卷（系统从已有题库随机选题）/ 使用智能组卷助手 / 创建平行试卷；底部「下一步 / 取消」。
- **注意**：这里是**组卷方式**，不是线上/线下选择；要找考试类型别在这里找。
- **目的**：区分「新建试卷」和「发放已有试卷」两条入口；已有试卷发放走 H2，不必新建。

---

## 任务 I：线下纸考发布控件（2026-11-25 新增）

> 本组只沉淀**控件级「怎么点才生效」**。发布流程顺序、前馈清单、发布前终检单在独立 Skill `exam-publish`；界面语义在 `references/paper-exam/`。两者不互相复述。
> 线下纸考/网评系统在 `v10596.kaoshi.chaoxing.com`，与 `mooc2-ans` 的课程内在线考试（任务 H）是**两套系统**——最初常把线下考试误判为线上，浪费一轮。智能导入会跳到 `mooc2-ans .../qbank/smartimport` 再回跳线下 `zjSuccess`，这是正常链路。

### I1 线下考试开关与两步发布流程

- **界面特征**：发布表单顶部「考试方式」开关 `a.switch[data-id="examlx"]`；源码逻辑 `if(examlx==1){ nextStepExamlx1() } else { nextStepExamlx0() }`，`examlx=1` 即线下。
- **触发**：点线下开关 → 填表 → 点 `a.nextStep` 进入第二步发布确认页 → 点 `a#submitButton`（`.publishSubmitButton`，`onclick="pubishExam()"`）。
- **失败原因**：在**第一步**直接 `page.click('#submitButton')` 会报 `element has a zero-sized bounding box`——第一步它位于 `div.l_setbtn.twoStep` 内，`display:none`、零尺寸。
- **成功方法**：必须先点 `a.nextStep` 进第二步，按钮才可见可点；提交后 `pubishExam()` → `examlx==1` → `pubishExamlx1()`。
- **首次记录**：2026-11-25。

### I2 线下字段用 `_lx1` 后缀（本次最坑，误判直接卡住发布）

- **界面特征**：线下可见字段 **id 带 `_lx1`、name 不带**：
  - `input#startTime_lx1`（name=`startTime`）、`#endTime_lx1`（name=`endTime`）、`#limitTime_lx1`（name=`limitTime`）、`#passingStandard_lx1`（name=`passingStandard`）；
  - 勾选框 `#multiHalfScoreCheckbox_lx1`、`#anonymousReview_lx1`、`#reviewFastAllocationCheckbox_lx1` 等。
- **失败原因**：页面另有**隐藏的** `input[name=startTime]` / `limitTime=120`（线上遗留值）。填了隐藏线上字段 → 点下一步报「考试开始时间不可为空」。按 name 选会命中多个。
- **成功方法**：一律用 `document.getElementById('startTime_lx1')` 等 id 定位；填值用原生 setter + `input`/`change` 事件（同 A6）。发布前用 evaluate 回读 `getElementById` 的值确认，不看 name。
- **首次记录**：2026-11-25。

### I3 答题时限不能大于起止时间差

- **界面特征**：开始/结束时间与「考试限时」同页。
- **触发**：填完点下一步。
- **失败原因**：报错「时限不能大于起始时间差」。如窗口 16:00–17:30=90 分钟，却填了 120 分钟。
- **成功方法**：时长 ≤ 窗口差；两者冲突时**问用户**改时长还是改窗口，不擅自定（属前馈决策，见 `exam-publish` Q4）。终检时由用户复核。
- **首次记录**：2026-11-25。

### I4 UEditor 须知：退回第一步会重置

- **界面特征**：PC 端与移动端须知各一个 UEditor 实例，`window.UE.instants[0]`=`examPCNotes`、`[1]`=`examNotes`。
- **失败原因**：从第二步返回第一步再进第二步，实例重新初始化，之前追加的「地点／主副监考」全部丢失，只剩默认文字。
- **成功方法**：在**第二步**用 `window.UE.instants[k].setContent(完整内容)` 重新写入，两端都写并回读核对。不要用 `UE.getEditor()`（会重渲染写不进去）。
- **首次记录**：2026-11-25。

### I5 「已添加考生 0 人」是显示假象

- **界面特征**：发布页显示「已添加考生0人」，隐藏字段 `input[name=classids]` 已是正确班级 ID（如 `155688692`）。
- **失败原因**：平台读不到 `data-studentcount` 之类属性导致的显示 bug。
- **成功方法**：**不要因此重新添加**（会重复考生）。以隐藏 `classids` + 发布后考试管理列表的实际人数为准（本次发布后显示 63 人）。
- **首次记录**：2026-11-25。

### I6 添加考生班级

- **触发**：`span[onclick="addClazzToExam(<班级id>)"]`（本次 `155688692`）。
- **验证**：添加后读隐藏 `classids` 确认含目标班级，不看页面那行「已添加考生N人」（见 I5）。
- **注意**：涉及哪些班级、各多少人属前馈（见 `exam-publish` Q5），发布后班级不可随意改。
- **首次记录**：2026-11-25。

### I7 发布后通知对话框：同名输入框歧义

- **界面特征**：发布成功弹「考试发布成功，是否发放考试通知？」→「是」→ 通知对话框。标题框 `input#notice_title`（name=`text`）、正文框 `textarea#notice_context`。
- **失败原因**：页面多处 `input[name=text]`（含考试等级名称「优秀」等），`querySelector('input[name="text"]')` 会选错元素，导致「改了标题」其实是改了隐藏等级字段，回读误判。
- **成功方法**：**一律用 id**（`notice_title` / `notice_context`）fill；回读时按 `tr` 里「通知标题」「通知内容」标签定位输入框取值，确认不含 A/B 卷（文案规则见 `exam-publish` Q6）。
- **首次记录**：2026-11-25。

### I8 课程名称/批次/场次为选填（先查 verify 标志）

- **界面特征**：隐藏字段 `verifyCourse` / `verifySemester` / `verifyBatch` 均为 0 → 不校验、选填。
- **失败原因**：用户说「把该填信息填成全的」就去硬填，但教务下拉无数据时根本填不了。
- **成功方法**：先 evaluate 读三个 verify 标志与下拉选项数；确认为 0 且下拉无数据 → 向用户说明后留空，不硬造。
- **首次记录**：2026-11-25。

### I9 考试答题纸：考生信息默认必勾「学号」「座位号」

- **界面特征**：考试管理列表该行「考试答题纸」入口进入编辑器（可能开新域 `ocr-zelda.chaoxing.com` 的新窗口，链接点击会超时，直接取 `a.href` 新开页面更稳）；右侧「考生信息」区是一组 checkbox，默认勾院系／专业／班级／姓名。
- **失败原因**：学号常只是页面底部独立的填涂区、不算信息栏字段，座位号默认不勾——按默认走就漏了这两项，阅卷识别与按考场排座缺字段。
- **成功方法**：进入编辑器先核对考生信息勾选，除院系／专业／班级／姓名外**补勾「学号」「座位号」**；字段出现顺序由鼠标点选先后决定，要调顺序按点选顺序处理。改完按「保存」再「下载」，答题纸与试卷一一对应、下载后连同试卷一起送印。
- **用户设定为默认**：以后每场考试都按此清单，不依赖系统默认。
- **首次记录**：2026-11-25。

### I10 考试答题纸：大题小题独立编号不能在当前编辑器直接改

- **界面特征**：答题纸编辑器右侧「题目结构」标题旁有静态文字「按题型编号」（带折叠箭头，点它是折叠/展开，不是编号方式下拉）；下方只有「题型序号显示为罗马数字／自定义标题居中显示／客观题合并显示在最前／客观题按序横向显示／判断题显示／显示题型说明／显示题型序号／显示题型分值」等复选框，**没有「连续编号／按题型编号／每大题重新编号」开关**。「题型清单」里每行的「题号」只是展示，题型名链接只改 URL hash，不打开可编辑题号的弹窗。
- **失败原因**：看到「按题型编号」误以为是编号方式切换入口；实际预览里题号仍是从试卷带过来的连续号（如单选 1-8、多选 9-12、判断 13-18、简答 19-22、综合 23-24）。前端新配置分支里确有 `连续编号 / 按题型编号` 单选与 `itemSerialNumberMode`（小题降级/同级编号）、`customNumberMode` + `customNumberList` 自定义题号字段，但这条导入卷走的是旧配置分支（`showNewPaperConfig=false`），这些控件没有暴露；直接改 Vue state 的 `itemSerialNumberMode` 也不改变预览。
- **成功方法**：先向用户说明「答题纸编辑器改不了题号，题号跟随试卷」。要实现每个大题独立编号（如多选 1-4、判断 1-6、简答 1-4、综合 1-2），必须在**试卷源头**处理：组卷时把「题目序号」设为「按题型编号」，或给各题型写自定义题号，再重新生成/下载答题纸。已发布考试不要为了题号直接改试卷，先与前馈清单核对影响范围。
- **首次记录**：2026-11-25。

### I11 题号独立编号的已验证落地路径：复制试卷 → 按题型编号 → 重新发布

- **触发**：用户要求每个大题独立编号（多选从 1 起、判断从 1 起……），而原卷已发布、编辑页被锁死（I10）。
- **入口**：个人空间 `i.chaoxing.com/base?ws=1` → 左侧「试卷管理」→ 找到目标卷 → 操作列「复制」。弹窗「确定要复制吗？」点「确定」；副本出现在列表首位，名称带「-副本1」，发布次数 0，试卷ID 改变（`paperid`、`kssjglid`、`sjid` 都是新的）。
- **编辑副本**：副本的「编辑」跳 `mooc2-ans.chaoxing.com/exam/create-exampaper?...&paperid=<新>&...`，**不带** `edit-grouppaper=true`，因此设置可改。改试卷名用 `input[name="examPaperTitle"]`；点 `.serialNumberMode[value="1"]`（题目序号 → 按题型编号），隐藏 `#serialNumberMode` 应从 `0` 变 `1`，预览各题型题号立即重置为 1 起。点「完成」→ 确认「试卷共创建 N 道题，总分 X 分，确认完成创建？」→「确定」。
- **发布后锁定判据**：已发布卷的编辑页会带 `edit-grouppaper=true`，顶部提示「该考试已发布，无法添加删除题目或修改分值」，两个 `serialNumberMode` 都有 `class_checked_disable`，`changeQuestionSerialNumber()` 开头直接 return。不要在这上面浪费时间。
- **重新发布**：用副本去「发布考试」，原考试保留（需要时改名为「（作废-请以新考试为准）」以免混淆）。新考试答题纸自动继承独立编号；考生信息仍按 I9 补勾「学号」「座位号」。
- **验证证据**：答题纸 DOM 中客观题各 `.txChoice` 的 `dt` 序列为 `1..8 / 1..4 / 1..6`；主观题为 `1.(10分) [四题1]` 等；下载 PDF 后 `pypdf` 也能读到分块 1 起编号。
- **首次记录**：2026-11-25。

---

## 任务 E：复盘沉淀

每次操作结束，把新发现的原子操作按本文件格式追加。重点补：
- 新遇到的 ExtJS / 浮层 / 确认框触发方式；
- 任何"试了 N 次才成功"的操作及其失败原因清单；
- 新的直连 URL 模板。

不要补：一次性题号、学生姓名、单次时间戳（除非作为格式示例）。
