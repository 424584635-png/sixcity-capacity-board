// 登录态体检 + 自愈：
//   xy（轩辕）失效 -> exit 2（必须人工登录，无法自动恢复）
//   fs（风神）失效 -> 自动重建会话（工作台刷新 / 统一登录 SSO 两种策略），成功 exit 0，失败 exit 1
import { connect, ensureFs, post } from './fs_guard.mjs';

const { b, ctx } = await connect();
const R = ctx.request;

const xy = await post(R, 'xtop.xy.special.realTimeAttendance.listCustomTime',
  { objectType: 2, bdGroupIds: [100000447021] }, 30000);
const xyCode = xy.code;
console.log('auth xy', xyCode);
if (xyCode !== '200') {
  console.error('xy session invalid');
  await b.close();
  process.exit(2);
}

const fsOk = await ensureFs(ctx, R, { attempts: 2 });
console.log('auth fs', fsOk ? '200' : 'FAILED');
await b.close();
process.exit(fsOk ? 0 : 1);
