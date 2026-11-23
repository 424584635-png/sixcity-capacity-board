// 风神会话保活探针：每 15 分钟探一次
// 只探测、不做重登（重登交给主流水线，避免频繁登录触发风控/验证码）
import fs from 'fs';
import path from 'path';
import { connect, probeFs } from './fs_guard.mjs';

const ROOT = 'C:/Users/luansha/WorkBuddy/2026-11-07-23-44-13/agg_board_1122';
const STATE = path.join(ROOT, 'pipeline', '.fs_state.json');
const { b, ctx } = await connect();
const R = ctx.request;
const alive = await probeFs(R);
let prev = {};
try { prev = JSON.parse(fs.readFileSync(STATE, 'utf-8')); } catch (e) {}
const wasAlive = prev.alive;
fs.writeFileSync(STATE, JSON.stringify({ alive, checkedAt: new Date().toISOString() }, null, 2));
console.log(`fs keepalive: ${alive ? 'ALIVE' : 'DOWN'}${wasAlive === alive ? '' : ' (状态变化)'}`);
if (!alive) console.log('  登录态失效，主流水线会尝试恢复；如遇图形验证码需人工登录');
await b.close();
process.exit(0);
