# 六城运力在线看板

普洱思茅区 + 景谷 / 景东 / 墨江 / 镇沅 的运力在线聚合看板，每 30 分钟（08:00–23:50）自动刷新并推送钉钉。

## 数据来源
- 轩辕盯盘 `xtop.lgt.datacenter.project.dingpan.dashboard.cd.queryIndicatorTable`（城市 / 站点 / 运力线）
- 轩辕考勤 `xtop.xy.special.realTimeAttendance.*`（小队 / 小组、时段）
- 风神考勤 `xtop.fs.special.realtimeattendance.*`（思茅站 7 项指标 + 时段明细）

## 指标口径
| 指标 | 口径 |
| --- | --- |
| 在线率 | 在线骑手 ÷ 排班骑手 |
| 时段排班骑手数 | 当前时段排班人数（timeGrouped=true） |
| 时段排班且在线数 | 时段排班中时段在线时长>0 或 onlineStatus=true |
| 时段在线率 | 时段排班且在线 ÷ 时段排班 |
| 时段排班未在线 | 时段排班 − 时段排班且在线 |

## 架构：纯接口取数，不自动登录
本系统与账号共享同一套 Cookie 令牌，但**取数全过程不经过浏览器、也不会自动执行登录**，
因此不会把使用同一账号的其他人顶下线。

- `pipeline/http_client.mjs` —— 纯 HTTP 客户端（只带 Cookie 令牌），所有取数走这里
- `pipeline/sync_cookies.mjs` —— **只读**从浏览器导出 Cookie 到 `.cookies.json`（不导航/不点击/不登录）
- `keepalive_fs.mjs` + 计划任务 `CapacityBoard-FsKeepalive` —— 每 15 分钟同步一次 Cookie 并探测令牌
- `collect.mjs` / `collect_fs_period.mjs` / `cddp_1122/crawl_*.mjs` —— 全部改用纯 HTTP
- 令牌失效时**不自动登录**：降级沿用上一轮有效数据继续推送，并告警提示人工在浏览器登录一次；
  人工登录后由同步任务自动接管新令牌

> 人工登录本身仍会顶掉同账号的其他人（平台单会话限制），但频率从「掉线就自动重登」
> 降到「约 12 小时一次或对方登录时才需要」。

## 目录
- `pipeline/run_pipeline.cmd` 全流程：同步 Cookie → 令牌体检 → 采集 → 建表 → 截图 → 上传 → 推送
- `pipeline/install_task.ps1` 注册 Windows 计划任务（08:00 起每 30 分钟，至 23:50）
- `pipeline/install_keepalive_task.ps1` 注册令牌保活任务（每 15 分钟）
- `pipeline/guard_snapshot.py` 采集结果校验 + 异常时回退上一轮有效快照
- `pipeline/push_dingtalk.example.py` 推送脚本示例（填入自己的 webhook token / SEC）
- `shots/` 每轮截图（文件名带时间戳，避免钉钉图片缓存）


## 说明
采集依赖登录 Cookie（轩辕/风神），但**不依赖浏览器运行**；Cookie 由人工登录一次后自动同步。
GitHub 仓库承担截图托管与代码留档，不作为运行环境。
