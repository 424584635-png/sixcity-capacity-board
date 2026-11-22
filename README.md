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

## 目录
- `pipeline/run_pipeline.cmd` 全流程：登录态体检 → 采集 → 建表 → 截图 → 上传 → 推送
- `pipeline/install_task.ps1` 注册 Windows 计划任务（08:00 起每 30 分钟，至 23:50）
- `pipeline/push_dingtalk.example.py` 推送脚本示例（填入自己的 webhook token / SEC）
- `shots/` 每轮截图（文件名带时间戳，避免钉钉图片缓存）

## 说明
采集依赖本机浏览器（Edge CDP 9223）的登录态，因此调度必须跑在本地；
GitHub 仓库只承担截图托管与代码留档，不作为运行环境。
