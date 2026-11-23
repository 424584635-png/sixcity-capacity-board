// 会话保活 + 令牌同步：每 15 分钟
//  1) 从浏览器「只读」导出 cookie 到 .cookies.json（不导航、不点击、不登录）
//     —— 人工登录一次后，采集端自动接管新令牌，我们自己永不执行登录
//  2) 用纯 HTTP 探一次风神/轩辕令牌（滑动 TTL 的话能续命；不续命也只是记录状态）
import fs from 'fs';
import path from 'path';
import { probeFs, probeXy } from './pipeline/http_client.mjs';

const ROOT = 'C:/Users/luansha/WorkBuddy/2026-11-07-23-44-13/agg_board_1122';
const STATE = path.join(ROOT, 'pipeline', '.fs_state.json');

// 1) 同步 cookie（浏览器不可用时跳过，不影响已有 cookie 继续取数）
try {
  const { execFileSync } = await import('child_process');
  const out = execFileSync('C:/Users/luansha/.workbuddy/binaries/node/versions/22.22.2-6/node.exe',
    [path.join(ROOT, 'pipeline', 'sync_cookies.mjs')], { encoding: 'utf-8', timeout: 60000 });
  console.log((out || '').trim());
} catch (e) {
  console.log('cookie 同步跳过（浏览器不可用）:', String(e.message || e).slice(0, 80));
}

// 2) 探测
let fsAlive = false, xyAlive = false;
try { fsAlive = await probeFs(); xyAlive = await probeXy(); } catch (e) { /* cookie 不可用 */ }
let prev = {};
try { prev = JSON.parse(fs.readFileSync(STATE, 'utf-8')); } catch (e) {}
fs.writeFileSync(STATE, JSON.stringify({
  alive: fsAlive, xyAlive, checkedAt: new Date().toISOString(),
  tokenChanged: prev.token !== undefined ? prev.token !== undefined : undefined,
}, null, 2));
console.log(`keepalive: fs=${fsAlive ? 'ALIVE' : 'DOWN'} xy=${xyAlive ? 'ALIVE' : 'DOWN'}`);
if (!fsAlive) console.log('  风神令牌失效 -> 流水线会降级使用上一轮数据，需人工在浏览器登录一次（我们不会自动登录）');
process.exit(0);
