# -*- coding: utf-8 -*-
"""流水线失败告警：推送一条 markdown 到钉钉群，便于当天发现登录态/接口异常。
与正文推送共用双通道逻辑：主机器人不可用时自动改投备用机器人。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from push_dingtalk import deliver  # noqa: E402

REASONS = {
    'cdp': 'Edge 调试端口 9223 不可用（浏览器未启动或未登录）',
    'xy': '轩辕登录态失效，需要人工重新登录',
    'fs': '风神登录态自动恢复失败，需要人工重新登录',
    'crawl_all': '盯站点（城市/站点）采集失败',
    'crawl_bd': '盯商圈（运力线）采集失败',
    'collect': '风神 / 轩辕考勤采集失败',
    'period': '当前时段骑手明细采集失败',
    'build': '看板 HTML 生成失败',
    'shot': '看板截图失败',
    'upload': '截图上传 GitHub 失败',
    'push': '钉钉消息推送失败',
    'guard': '采集数据校验失败且无可用快照',
}
HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, 'pipeline.log')


def read_tail(n=1200):
    try:
        with open(LOG, 'rb') as f:
            f.seek(max(0, os.path.getsize(LOG) - 4000))
            raw = f.read()
    except Exception:
        return ''
    for enc in ('utf-8', 'gbk', 'utf-8'):
        try:
            txt = raw.decode(enc)
            break
        except Exception:
            txt = raw.decode('utf-8', 'replace')
    lines = [ln for ln in txt.splitlines() if ln.strip()]
    return '\n'.join(lines[-14:])[-n:]


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else 'unknown'
    reason = REASONS.get(key, key)
    text = (f'### ⚠️ 运力看板推送失败\n\n'
            f'**环节：**{reason}\n\n'
            f'**时间：**{time.strftime("%Y-%m-%d %H:%M", time.localtime())} CST\n\n'
            f'本轮已跳过，等下一轮 30 分钟后重试。\n\n'
            f'```\n{read_tail()}\n```')
    ok, msg = deliver({'msgtype': 'markdown',
                       'markdown': {'title': '运力看板推送失败', 'text': text}}, 'alert')
    print('alert result:', msg)


if __name__ == '__main__':
    main()
