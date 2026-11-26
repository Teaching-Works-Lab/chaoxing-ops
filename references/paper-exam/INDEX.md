# 纸考网评操作手册 · 图片语义节点库

> 来源：沧州交通学院纸考网评操作手册（附件3），77 张原图与逐图语义标注。
> 归属：物理上存放于超星 skill（`chaoxing-ops/references/paper-exam/`），保证随 skill 打包；
> 语义上由相关 skill 双链引用，不复制副本。

## 为什么按功能域而不是手册章节分类

手册是「按操作顺序」写的，但复用时是「按我要干什么」来找。同类操作（如考生管理）在手册里跨了发布考试前后两处，按章节会漏；按功能域归类后，一个场景一次看全，且便于未来把某个域单独抽成 skill。

## 功能域索引

| 域 | 名称 | 归属 / 调用方 | 图片数 | 节点文件 |
|---|---|---|---|---|
| D1 | 登录与身份绑定 | chaoxing-ops（超星通用） | 3 | [domains/D1.md](domains/D1.md) |
| D2 | 题库建设 | chaoxing-ops（题库操作，与 exam-word 出题/组卷语义相邻） | 14 | [domains/D2.md](domains/D2.md) |
| D3 | 组卷 | chaoxing-ops（组卷）＋ exam-word（试卷文档侧双链） | 14 | [domains/D3.md](domains/D3.md) |
| D4 | 试卷管理与保密 | chaoxing-ops（试卷管理） | 8 | [domains/D4.md](domains/D4.md) |
| D5 | 发布考试与考生管理 | chaoxing-ops（发布/考试管理） | 12 | [domains/D5.md](domains/D5.md) |
| D6 | 考试答题纸（纸考专用） | chaoxing-ops（纸考网评专用，本手册核心） | 4 | [domains/D6.md](domains/D6.md) |
| D7 | 批阅 | chaoxing-ops（批阅）— 可成长为独立批阅 skill 的种子域 | 15 | [domains/D7.md](domains/D7.md) |
| D8 | 导出考试材料与归档 | chaoxing-ops（导出） | 7 | [domains/D8.md](domains/D8.md) |

## 使用约定（增量完善）

- 每张图是一个最小语义节点，数据在 `semantics_all.json`，字段：`screen_type` / `ui_text` / `controls` / `action` / `notes` / `search_terms` / `usage`。
- 以后对某张图有新认识（补控件、纠正措辞、补充易错点），**只改该图对应的 JSON 条目并更新生成时间**，不要重读整张图、不要新建副本。
- 发现手册文字与实际界面不一致时，写进该图 `notes`（已有多处，如「创建新题库」实为「创建新的库」）。这是最有价值的沉淀。
- 语义检索用 `search_terms` 字段；执行具体操作时先读对应域节点文件的「操作要点」段。
- 原始图片在 `images/`，按 `imageN.png` 命名，与 JSON 的 `id` 一一对应。

## 与其他 skill 的双链关系

- `exam-word`（试卷文档 skill）：负责 Word 试卷排版/模板/答案卷；本库 D3 组卷、D4 导出与其「出题-组卷-排版」链路相邻，双方互引，不复制内容。
- 未来若出现独立「批阅 skill」：本库 D7 可直接作为种子域整体抽离，抽离时保留对本索引的回链。
