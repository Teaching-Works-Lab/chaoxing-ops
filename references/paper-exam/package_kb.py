#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把纸考网评语义节点封装成可被调用的知识包：
1) 每张图一个稳定节点 ID (PE-D<域>-I<序号>)
2) manifest.json 调用契约（对外唯一入口）
3) query.py 检索 CLI（按域/关键词/节点ID/图号查图与语义）
4) NODES.md 节点清单（人可读）
不移动原图、不复制语义数据，只增加调用层。
"""
import json, os, re

KB = '/Users/aa/.workbuddy/skills/chaoxing-ops/references/paper-exam'

DOMAIN_META = {
    'D1': '登录与身份绑定',
    'D2': '题库建设',
    'D3': '组卷',
    'D4': '试卷管理与保密',
    'D5': '发布考试与考生管理',
    'D6': '考试答题纸（纸考专用）',
    'D7': '批阅',
    'D8': '导出考试材料与归档',
}

def stable_id(domain, iname):
    n = int(re.search(r'\d+', iname).group())
    return f'PE-{domain}-I{n:03d}'

def main():
    data = json.load(open(os.path.join(KB, 'semantics_all.json'), encoding='utf-8'))
    data.sort(key=lambda r: int(re.search(r'\d+', r['id']).group()))

    nodes = []
    for r in data:
        d = r.get('domain', '?')
        nodes.append({
            'node_id': stable_id(d, r['id']),
            'image': f'images/{r["id"]}',
            'domain': d,
            'domain_name': DOMAIN_META.get(d, ''),
            'screen_type': r.get('screen_type', ''),
            'ui_text': r.get('ui_text', ''),
            'controls': r.get('controls', ''),
            'action': r.get('action', ''),
            'notes': r.get('notes', ''),
            'search_terms': r.get('search_terms', []),
            'usage': r.get('usage', ''),
            'source_chapter': r.get('chapter', ''),
            'source_section': r.get('section', ''),
            'source_context': r.get('context', ''),
        })

    manifest = {
        'package': 'chaoxing-paper-exam-visual-kb',
        'version': '1.0.0',
        'source': '沧州交通学院纸考网评操作手册（附件3）',
        'owner_skill': 'chaoxing-ops',
        'physical_path': KB,
        'description': '77 张纸考网评界面截图的原子化语义节点；供其他 skill 按节点ID/功能域/关键词调用，不复制副本。',
        'node_count': len(nodes),
        'domains': [
            {'id': d, 'name': name, 'node_file': f'domains/{d}.md',
             'count': sum(1 for n in nodes if n['domain'] == d)}
            for d, name in DOMAIN_META.items()
        ],
        'query_entry': 'query.py',
        'query_examples': [
            'python3 query.py --domain D6',
            'python3 query.py --search 答题纸 --domain D6',
            'python3 query.py --node PE-D4-I033',
            'python3 query.py --image image33.png',
            'python3 query.py --list',
        ],
        'increment_rule': '新增认识只改 semantics_all.json 对应 id 条目，再跑 build_kb.py 与 package_kb.py；节点ID由(域,图号)决定，保持稳定。',
        'cross_skill_links': {
            'chaoxing-ops/SKILL.md': '挂接本包 INDEX.md',
            'exam-word-skill/SKILL.md': '路径引用本包，试卷文档侧 vs 超星平台侧分工',
        },
    }
    json.dump(manifest, open(os.path.join(KB, 'manifest.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)
    json.dump({'nodes': nodes}, open(os.path.join(KB, 'nodes.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=2)

    # 人可读节点清单
    L = ['# 原子化节点清单（稳定 ID）', '',
         '> 节点 ID 格式 `PE-D<域>-I<图号>`，由「功能域 + 原图编号」决定，永不变更。',
         '> 调用入口：`manifest.json`（契约）、`query.py`（检索）、`nodes.json`（机器可读）。', '',
         '| 节点 ID | 域 | 界面 | 一句话用途 | 原图 |', '|---|---|---|---|---|']
    for n in nodes:
        L.append(f'| {n["node_id"]} | {n["domain"]} | {n["screen_type"]} | {n["usage"][:60]} | {n["image"]} |')
    open(os.path.join(KB, 'NODES.md'), 'w', encoding='utf-8').write('\n'.join(L) + '\n')
    print('封装完成：manifest.json / nodes.json / NODES.md，节点', len(nodes))

if __name__ == '__main__':
    main()
