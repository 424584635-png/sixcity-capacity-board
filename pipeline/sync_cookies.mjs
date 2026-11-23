// 从浏览器只读导出 Cookie 到 .cookies.json（不登录、不点击、不导航）
// 用途：人工登录一次后，让采集脚本完全脱离浏览器取数，避免自动登录顶掉同账号的其他人。
import fs from 'fs';
import { createRequire } from 'module';
const require = createRequire('C:/Users/luansha/Documents/deepseek-harness/default-workspace/package.json');
const { chromium } = require('playwright-core');

const ROOT = 'C:/Users/luansha/WorkBuddy/2026-11-07-23-44-13/agg_board_1122';
const OUT = ROOT + '/pipeline/.cookies.json';

let b = null;
try {
  b = await chromium.connectOverCDP('http://127.0.0.1:9223');
} catch (e) {
  console.log('浏览器 CDP 不可用，无法同步 cookie（不影响已有 cookie 继续取数）');
  process.exit(0);
}
const ctx = b.contexts()[0];
const ck = await ctx.cookies('https://ele.me');
const want = ['cna', 'uvUserId', 'uvUserWorkCode', 'rolename', 'uvUserName', 'saleRole',
  'xyShellUnitLine', 'xyShellUnitId', 'xyShellVersion', 'tfstk', 'family', 'XY_TOKEN',
  'PASSPORT_TOKEN', 'PASSPORT_AGENTS_TOKEN', 'AEOLUS_MOZI_TOKEN', 'isg'];
const keep = ck.filter(c => want.includes(c.name));
const token = (keep.find(c => c.name === 'AEOLUS_MOZI_TOKEN') || {}).value || '';

// 与现有文件比较，变化才写
let changed = true;
try {
  const old = JSON.parse(fs.readFileSync(OUT, 'utf-8'));
  const oldTok = (old.find(c => c.name === 'AEOLUS_MOZI_TOKEN') || {}).value || '';
  changed = oldTok !== token || old.length !== keep.length;
} catch (e) {}

if (changed) {
  fs.writeFileSync(OUT, JSON.stringify(keep, null, 2), 'utf-8');
  console.log('cookie 已更新 ->', OUT, '| 数量', keep.length, '| 令牌尾', token.slice(-10));
} else {
  console.log('cookie 无变化，保留现文件');
}
await b.close();
