#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""纸考网评图片语义知识包 · 检索 CLI。

其他 skill / 工作流调用方式（在本目录下执行，或传绝对路径）：
  python3 query.py --domain D6                    # 列出某功能域全部节点
  python3 query.py --search 答题纸                # 语义关键词检索
  python3 query.py --search 双重密码 --domain D4  # 域内检索
  python3 query.py --node PE-D4-I033              # 按稳定节点ID取详情
  python3 query.py --image image33.png            # 按原图名取详情
  python3 query.py --list                         # 列出全部节点ID与界面
  python3 query.py --manifest                     # 打印调用契约

输出为 JSON（--list 为表格文本）。本脚本只读，不改动知识包。
"""
import json, os, sys, argparse

HERE = os.path.dirname(os.path.abspath(__file__))

def load():
    return json.load(open(os.path.join(HERE, 'nodes.json'), encoding='utf-8'))['nodes']

def brief(n):
    return {
        'node_id': n['node_id'], 'image': n['image'], 'domain': n['domain'],
        'screen_type': n['screen_type'], 'usage': n['usage'],
    }

def main():
    ap = argparse.ArgumentParser(description='纸考网评图片语义检索')
    ap.add_argument('--domain', help='功能域 ID，如 D6')
    ap.add_argument('--search', help='关键词，匹配 search_terms/ui_text/notes/action/usage')
    ap.add_argument('--node', help='稳定节点 ID，如 PE-D4-I033')
    ap.add_argument('--image', help='原图文件名，如 image33.png')
    ap.add_argument('--list', action='store_true', help='列出全部节点')
    ap.add_argument('--manifest', action='store_true', help='打印 manifest.json')
    ap.add_argument('--full', action='store_true', help='详情时输出全字段（默认仅摘要）')
    args = ap.parse_args()

    if args.manifest:
        print(json.dumps(json.load(open(os.path.join(HERE, 'manifest.json'), encoding='utf-8')),
                         ensure_ascii=False, indent=2))
        return
    nodes = load()
    if args.node:
        hit = [n for n in nodes if n['node_id'].lower() == args.node.lower()]
        print(json.dumps(hit[0] if (args.full and hit) else [brief(n) for n in hit], ensure_ascii=False, indent=2))
        return
    if args.image:
        hit = [n for n in nodes if n['image'].endswith(args.image)]
        print(json.dumps(hit[0] if (args.full and hit) else [brief(n) for n in hit], ensure_ascii=False, indent=2))
        return
    if args.list:
        for n in nodes:
            print(f"{n['node_id']} | {n['domain']} | {n['screen_type']} | {n['image']}")
        return
    res = nodes
    if args.domain:
        res = [n for n in res if n['domain'].lower() == args.domain.lower()]
    if args.search:
        kw = args.search.lower()
        def match(n):
            fields = [n['screen_type'], n['ui_text'], n['notes'], n['action'],
                      n['usage'], n['controls'], ' '.join(n['search_terms'])]
            return any(kw in str(f).lower() for f in fields)
        res = [n for n in res if match(n)]
    print(json.dumps([n if args.full else brief(n) for n in res], ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
