// 纯 HTTP 取数客户端：只用 Cookie（令牌），不经过浏览器。
// 目的：日常取数完全脱离浏览器，避免任何自动登录把同账号的其他人踢下线。
// Cookie 来源：人工登录一次后由 sync_cookies.mjs 从浏览器导出到 .cookies.json；
// 保活任务每 15 分钟比对浏览器里的令牌，有变化就同步过来（只读，不登录）。
import fs from 'fs';
import path from 'path';

const HERE = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1'));
const COOKIE_FILE = path.join(HERE, '.cookies.json');
const BASE = 'https://httpizza.ele.me';

let COOKIE_HEADER = '';
let COOKIE_MTIME = 0;

export function cookieFile() { return COOKIE_FILE; }

export function loadCookies(force = false) {
  try {
    const st = fs.statSync(COOKIE_FILE);
    if (!force && st.mtimeMs === COOKIE_MTIME && COOKIE_HEADER) return COOKIE_HEADER;
    const ck = JSON.parse(fs.readFileSync(COOKIE_FILE, 'utf-8'));
    COOKIE_HEADER = ck.map(c => `${c.name}=${c.value}`).join('; ');
    COOKIE_MTIME = st.mtimeMs;
  } catch (e) {
    throw new Error('cookie 文件不可用：' + COOKIE_FILE + '（需要人工登录一次并执行 sync_cookies）');
  }
  return COOKIE_HEADER;
}

const HEADERS = () => ({
  'Content-Type': 'application/json',
  'Cookie': loadCookies(),
  'Origin': 'https://aeolus.ele.me',
  'Referer': 'https://aeolus.ele.me/',
  'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
});

/** 调 xtop 网关，返回 { ok, code, data, text, status } */
export async function post(api, request, timeout = 60000) {
  const t0 = Date.now();
  let text = '', status = 0, err = null;
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), timeout);
    const r = await fetch(BASE + '/xtop/' + api + '/1.0', {
      method: 'POST',
      headers: HEADERS(),
      body: JSON.stringify({ params: { request } }),
      signal: ctl.signal,
    });
    clearTimeout(timer);
    status = r.status;
    text = await r.text();
  } catch (e) {
    err = String(e.message || e);
  }
  let j = null;
  try { j = JSON.parse(text); } catch (e) {}
  const code = String(j?.result?.code ?? j?.code ?? '');
  const data = j && j.result && j.result.data !== undefined ? j.result.data : (j && j.data);
  const ok = status === 200 && code === '200';
  return { ok, code, data, text, status, err, ms: Date.now() - t0, j };
}

/** 调 lpd.meepo 等 GET 接口 */
export async function get(p, timeout = 60000) {
  const t0 = Date.now();
  let text = '', status = 0, err = null;
  try {
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), timeout);
    const r = await fetch(BASE + p, { headers: HEADERS(), signal: ctl.signal });
    clearTimeout(timer);
    status = r.status;
    text = await r.text();
  } catch (e) {
    err = String(e.message || e);
  }
  let j = null;
  try { j = JSON.parse(text); } catch (e) {}
  const code = String(j?.code ?? '');
  return { ok: status === 200 && code === '200', code, data: j?.data, text, status, err, ms: Date.now() - t0 };
}

/** 探测风神会话是否可用 */
export async function probeFs() {
  try {
    const r = await post('xtop.fs.special.realtimeattendance.queryAttendanceStatistics', { teamId: 17424603 }, 20000);
    return r.ok;
  } catch (e) {
    return false;
  }
}

/** 探测轩辕会话是否可用 */
export async function probeXy() {
  try {
    const r = await post('xtop.xy.special.realTimeAttendance.listCustomTime', { objectType: 2, bdGroupIds: [100000447021] }, 20000);
    return r.ok;
  } catch (e) {
    return false;
  }
}
