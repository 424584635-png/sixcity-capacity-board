// 登录态体检（纯 HTTP，不经过浏览器、不执行任何登录动作）
// 目的：日常取数完全脱离浏览器，就不会因为自动登录把同账号的其他人顶下线。
// 令牌失效时也不自动登录，只降级并提示人工处理。
// 退出码：0 = 全通；2 = 轩辕令牌失效（致命，看板缺少小队维度）；3 = 风神令牌失效（可降级）
import { probeFs, probeXy } from './pipeline/http_client.mjs';

const fsOk = await probeFs();
const xyOk = await probeXy();
console.log('auth fs', fsOk ? '200' : 'FAIL', '| xy', xyOk ? '200' : 'FAIL');
process.exit(xyOk ? (fsOk ? 0 : 3) : 2);
