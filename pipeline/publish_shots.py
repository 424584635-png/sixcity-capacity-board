#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把三张维度截图上传到 GitHub 公开仓库，生成 raw 直链写入 shots/urls.json。

钉钉 markdown 图片只认基础 URL，会缓存；因此每次用带时间戳的唯一文件名强制刷新，
并清理上一轮的旧文件，避免仓库无限增长。
用法: python publish_shots.py [仓库名，默认 sixcity-capacity-board]
"""
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = 'https://api.github.com'
HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.dirname(HERE)          # agg_board_1122
SHOT_DIR = os.path.join(BOARD, 'shots')  # shot_sections.mjs 输出目录
URLS = os.path.join(SHOT_DIR, 'urls.json')
REPO_DEFAULT = 'sixcity-capacity-board'
FILES = [('city', '1_city.png'), ('team', '2_team.png'), ('squad', '3_squad.png')]


def api(token, method, path, data=None):
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'wbbot',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    body = json.dumps(data).encode('utf-8') if data is not None else None
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(API + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8', 'ignore'))
        except Exception:
            return e.code, {'message': e.reason}
    except Exception as e:
        return 0, {'message': str(e)}


def read_pat():
    for p in (os.path.join(HERE, 'github_pat.txt'),
              os.path.join(os.path.dirname(HERE), 'monitor', 'github_pat.txt')):
        if os.path.exists(p):
            with open(p, encoding='utf-8-sig') as f:
                t = f.read().strip()
            if t:
                return t
    return os.environ.get('GITHUB_PAT')


def main():
    token = read_pat()
    if not token:
        print('缺少 GitHub PAT：请在 agg_board_1122/pipeline/github_pat.txt 写入')
        sys.exit(2)
    repo = sys.argv[1] if len(sys.argv) > 1 else REPO_DEFAULT

    st, me = api(token, 'GET', '/user')
    if st != 200:
        print('获取 GitHub 账号失败:', st, me)
        sys.exit(1)
    owner = me['login']
    print('GitHub 账号:', owner)

    st, r = api(token, 'GET', f'/repos/{owner}/{repo}')
    if st == 404:
        st, r = api(token, 'POST', '/user/repos', {
            'name': repo, 'private': False, 'auto_init': True,
            'description': '六城运力在线看板 自动推送截图托管',
        })
        if st not in (200, 201):
            print('创建仓库失败:', st, r)
            sys.exit(1)
        print('已创建仓库:', r.get('full_name'), r.get('html_url'))
        time.sleep(4)
        branch = 'main'
    elif st == 200:
        branch = r.get('default_branch', 'main')
        print('仓库已存在:', f'{owner}/{repo}  分支={branch}')
    else:
        print('查询仓库失败:', st, r)
        sys.exit(1)

    stamp = time.strftime('%Y%m%d%H%M%S')
    urls, uploaded = {}, []
    for key, fn in FILES:
        fp = os.path.join(SHOT_DIR, fn)
        if not os.path.exists(fp):
            print('  缺图跳过:', fn)
            continue
        name = f'{os.path.splitext(fn)[0]}_{stamp}.png'
        path = f'/repos/{owner}/{repo}/contents/shots/{name}'
        with open(fp, 'rb') as f:
            content = base64.b64encode(f.read()).decode('ascii')
        st, res = api(token, 'PUT', path,
                      {'message': f'add {name}', 'content': content, 'branch': branch})
        if st not in (200, 201):
            print('  上传失败', name, st, res)
            continue
        raw = f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/shots/{name}'
        urls[key] = raw
        uploaded.append(name)
        print('  已上传', name, '->', raw)

    # 清理上一轮旧图（保留本轮）
    st, listing = api(token, 'GET', f'/repos/{owner}/{repo}/contents/shots')
    if st == 200:
        for item in listing:
            nm = item['name']
            if re.match(r'(1_city|2_team|3_squad)_\d{14}\.png$', nm) and nm not in uploaded:
                d_st, _ = api(token, 'DELETE', f'/repos/{owner}/{repo}/contents/shots/{nm}',
                              {'message': f'cleanup {nm}', 'sha': item['sha'], 'branch': branch})
                if d_st in (200, 201):
                    print('  清理旧图', nm)

    json.dump({'stamp': stamp, 'urls': urls},
              open(URLS, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('urls.json 已写入:', URLS, '| 共', len(urls), '张')
    if len(urls) != 3:
        sys.exit(3)


if __name__ == '__main__':
    main()
