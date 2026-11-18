# -*- coding: utf-8 -*-
"""学习通官方题库导入 xls 生成器（20列模板）。
用法：修改 TOPIC/DIR/TAG/single/judge 后运行，输出到工作区 outputs。
依赖：pip install xlrd xlwt（装前设 CODEBUDDY_SAFE_DELETE_ENABLED=0，并清空 http(s)_proxy）。
"""
import os
import xlwt

HEADER = ['目录', '题目类型', '自定义题型', '大题题干', '小题题型', '小题题干',
          '正确答案', '答案解析', '难易度', '知识点', '标签', '选项数',
          '选项A', '选项B', '选项C', '选项D', '选项E', '选项F', '选项G', '选项H']

OUT_NAME = '示例课程_题库导入.xls'
DIR = '/示例章节'
TAG = '示例课程；示例章节'

# (题干, [选项A-D], 正确答案, 解析, 知识点)
single = [
    ('示例单选题题干？', ['选项A', '选项B', '选项C', '选项D'], 'B', '解析文本。', '知识点'),
]
# (题干, 正确A/错误B, 解析, 知识点)
judge = [
    ('示例判断题题干。', 'A', '解析文本。', '知识点'),
]

rows = []
for stem, opts, ans, exp, kp in single:
    rows.append([DIR, '单选题', '', stem, '', '', ans, exp, '易', kp, TAG,
                 '4', opts[0], opts[1], opts[2], opts[3], '', '', '', ''])
for stem, ans, exp, kp in judge:
    rows.append([DIR, '判断题', '', stem, '', '', ans, exp, '易', kp, TAG,
                 '2', '正确', '错误', '', '', '', '', '', ''])

wb = xlwt.Workbook(encoding='utf-8')
ws = wb.add_sheet('课程题库')
for c, v in enumerate(HEADER):
    ws.write(0, c, v)
for r, row in enumerate(rows, start=1):
    for c, v in enumerate(row):
        ws.write(r, c, v)

outdir = os.environ.get('CHAOXING_OUTDIR') or os.path.join(os.getcwd(), 'outputs')
os.makedirs(outdir, exist_ok=True)
out = os.path.join(outdir, OUT_NAME)
wb.save(out)
print('SAVED:', out)
print('TOTAL:', len(rows), 'questions (single=%d, judge=%d)' % (len(single), len(judge)))
