#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把三张维度截图压缩后上传到 GitHub 公开仓库，生成图片直链写入 shots/urls.json。

要点：
1. 钉钉 markdown 图片只认基础 URL 且会缓存 -> 每轮用带时间戳的唯一文件名；
2. 原图 2100px@2x 太大（~500KB），上传前转 JPEG 并限宽 1800，钉钉拉取更快、不易超时；
3. 实测钉钉服务端拉不动 cdn.jsdelivr.net（报 -1 系统繁忙），raw.githubusercontent 一次成功，
   所以默认用 raw。

用法: python publish_shots.py [仓库名，默认 sixcity-capacity-board]
"""
import base64
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from PIL import Image

API = 'https://api.github.com'
HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.dirname(HERE)            # agg_board_1122
SHOT_DIR = os.path.join(BOARD, 'shots')  # shot_sections.mjs 输出目录
URLS = os.path.join(SHOT_DIR, 'urls.json')
REPO_DEFAULT = 'sixcity-capacity-board'
FILES = [('city', '1_city.png'), ('team', '2_team.png'), ('squad', '3_squad.png')]
MAX_W = 1800
QUALITY = 88
# 实测：钉钉服务端拉 cdn.jsdelivr.net 的图会返回 -1「系统繁忙」，
# 换 raw.githubusercontent.com 一次成功。因此默认用 raw。
CDN = 'raw'  # raw | jsdelivr


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


def shrink(src):
    """PNG -> JPEG bytes，限宽 MAX_W，白底（截图本身不透明，保险起见）"""
    im = Image.open(src)
    if im.mode in ('RGBA', 'LA', 'P'):
        bg = Image.new('RGB', im.size, (255, 255, 255))
        im = im.convert('RGBA')
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert('RGB')
    if im.width > MAX_W:
        h = round(im.height * MAX_W / im.width)
        im = im.resize((MAX_W, h), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, 'JPEG', quality=QUALITY, optimize=True, progressive=True)
    return buf.getvalue(), im.size


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
        data, size = shrink(fp)
        name = f'{key}_{stamp}.jpg'
        path = f'/repos/{owner}/{repo}/contents/shots/{name}'
        st, res = api(token, 'PUT', path, {
            'message': f'add {name}',
            'content': base64.b64encode(data).decode('ascii'),
            'branch': branch})
        if st not in (200, 201):
            print('  上传失败', name, st, res)
            continue
        if CDN == 'jsdelivr':
            url = f'https://cdn.jsdelivr.net/gh/{owner}/{repo}@{branch}/shots/{name}'
        else:
            url = f'https://raw.githubusercontent.com/{owner}/{repo}/{branch}/shots/{name}'
        urls[key] = url
        uploaded.append(name)
        print(f'  已上传 {name} {size[0]}x{size[1]} {len(data)//1024}KB')

    # 清理旧图：保留最近 2 轮（钉钉可能延迟加载上一条消息里的图，删太早会 404）
    st, listing = api(token, 'GET', f'/repos/{owner}/{repo}/contents/shots')
    if st == 200:
        olds = [it['name'] for it in listing
                if re.match(r'(city|team|squad|1_city|2_team|3_squad)_\d{14}\.(jpg|png)$', it['name'])
                and it['name'] not in uploaded]
        stamps = sorted({re.search(r'_(\d{14})\.', n).group(1) for n in olds})
        keep = set(stamps[-1:])          # 上一轮保留
        for nm in olds:
            stm = re.search(r'_(\d{14})\.', nm).group(1)
            if stm in keep:
                continue
            item = next(i for i in listing if i['name'] == nm)
            d_st, _ = api(token, 'DELETE', f'/repos/{owner}/{repo}/contents/shots/{nm}',
                          {'message': f'cleanup {nm}', 'sha': item['sha'], 'branch': branch})
            if d_st in (200, 201):
                print('  清理旧图', nm)

    json.dump({'stamp': stamp, 'urls': urls},
              open(URLS, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print('urls.json 已写入 | 共', len(urls), '张')
    if len(urls) != 3:
        sys.exit(3)


if __name__ == '__main__':
    main()
