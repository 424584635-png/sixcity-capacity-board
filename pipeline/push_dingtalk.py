# -*- coding: utf-8 -*-
"""推送聚合看板到钉钉群：markdown 文字（运力在线情况/当前时段/数据时间）+ 三个维度截图。

双通道投递：
  主机器人（新）失败且属于不可重试错误（停用/不在群/关键词不匹配）时，立刻改投备用机器人；
  可重试错误（-1 系统繁忙、130101 发送过快）先按退避重试，仍失败再改投备用。
"""
import base64
import datetime
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request

ROBOTS = [
    ('main', '4b5b41ba4e67126bf9200b4856b296561da578ce53d722a55f53fcd095a5a523',
     'SECcb2dc73800e01c3eecbe03ad47de9c58e2cd80d681a47ac039f5cff8d7bd9524'),
    ('backup', '2e74bf2f975848d1ea14897952b2b3472b234debf70b5862bc9c0189216c4947',
     'SECb14b7a089d02f28f09d7dbf3d7b1158ffa329165bb3d4059a7c67b0ba8d77b02'),
]
# 不可重试：同一机器人再试也没用，但可以换另一个机器人投
FATAL_CODES = {400102, 400013, 300001, 300005, 310000, 400008, 400035}
HERE = os.path.dirname(os.path.abspath(__file__))
BOARD = os.path.dirname(HERE)
URLS = os.path.join(BOARD, 'shots', 'urls.json')


def signed_url(token, secret):
    ts = str(round(time.time() * 1000))
    h = hmac.new(secret.encode(), f'{ts}\n{secret}'.encode(), digestmod=hashlib.sha256).digest()
    return (f'https://oapi.dingtalk.com/robot/send?access_token={token}'
            f'&timestamp={ts}&sign={urllib.parse.quote_plus(base64.b64encode(h))}')


def post_once(token, secret, payload):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(signed_url(token, secret), data=body,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode('utf-8'))


def deliver(payload, tag, robots=None):
    """按机器人顺序投递，返回 (成功?, 说明)"""
    robots = robots or ROBOTS
    for name, token, secret in robots:
        for i in range(3):
            try:
                res = post_once(token, secret, payload)
            except Exception as e:
                res = {'errcode': -99, 'errmsg': str(e)}
            code = res.get('errcode')
            print(f'{tag} [{name}] try{i + 1} errcode {code} errmsg {res.get("errmsg")}')
            if code == 0:
                return True, f'{name} 投递成功'
            if code in FATAL_CODES:
                print(f'{tag} [{name}] 不可重试错误 {code}，切换下一个机器人')
                break
            time.sleep(3 * (i + 1))
        else:
            print(f'{tag} [{name}] 重试 3 次仍失败，切换下一个机器人')
    return False, '全部机器人投递失败'


def cst(iso):
    d = datetime.datetime.fromisoformat(iso.replace('Z', '+00:00')) + datetime.timedelta(hours=8)
    return d.strftime('%Y-%m-%d %H:%M')


def main():
    data = json.load(open(os.path.join(BOARD, 'board_data.json'), encoding='utf-8'))
    m = data['meta']
    u = json.load(open(URLS, encoding='utf-8'))['urls']
    period = f"{m.get('periodName', '')}({m.get('periodCode', '')}) {m.get('periodRange', '')}".strip()
    stale = '（本轮为上一轮有效快照回退）' if m.get('revertedAt') else ''

    text = (f'### 运力在线情况\n\n'
            f'**当前时段：**{period}\n\n'
            f'**数据时间：**{cst(m["collectedAt"])} CST{stale}\n\n'
            f'---\n\n'
            f'**① 城市维度**\n\n![]({u["city"]})\n\n'
            f'**② 小队维度**\n\n![]({u["team"]})\n\n'
            f'**③ 小组维度**\n\n![]({u["squad"]})')
    payload = {'msgtype': 'markdown',
               'markdown': {'title': '运力在线情况', 'text': text}}
    ok, msg = deliver(payload, '推送')
    if ok:
        print('RESULT:', msg)
        sys.exit(0)

    # 兜底：图片消息整体失败时，改发纯文字（含图片直链），保证群里一定有消息
    plain = (f'运力在线情况\n'
             f'当前时段：{period}\n'
             f'数据时间：{cst(m["collectedAt"])} CST{stale}\n'
             f'图片消息投递失败，以下为直链：\n'
             f'① 城市维度 {u["city"]}\n'
             f'② 小队维度 {u["team"]}\n'
             f'③ 小组维度 {u["squad"]}')
    ok2, msg2 = deliver({'msgtype': 'text', 'text': {'content': plain}}, '兜底文字')
    print('RESULT:', msg2)
    sys.exit(0 if ok2 else 4)


if __name__ == '__main__':
    main()
