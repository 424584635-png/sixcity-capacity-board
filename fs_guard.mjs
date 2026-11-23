// 风神(aeolus/fs) 会话守卫 —— 仅供诊断/排障使用
// 注意：主流水线已改为「纯 HTTP 取数」（pipeline/http_client.mjs），**不再执行任何自动登录**，
// 因此不会再把使用同一账号的其他人顶下线。本文件保留用于手动排查登录页问题。
import { createRequire } from 'module';
const require = createRequire('C:/Users/luansha/Documents/deepseek-harness/default-workspace/package.json');
const { chromium } = require('playwright-core');

export const AEOLUS_URL = 'https://aeolus.ele.me/?targetId=7715#/group/schedule/work-check';
export const FS_STAT = 'xtop.fs.special.realtimeattendance.queryAttendanceStatistics';
export const TEAM_MAIN = 17424603; // 逸海-思茅站

const sleep = ms => new Promise(r => setTimeout(r, ms));

export async function connect() {
  const b = await chromium.connectOverCDP('http://127.0.0.1:9223');
  return { b, ctx: b.contexts()[0] };
}

export async function post(R, api, request, timeout = 60000) {
  const r = await R.post('https://httpizza.ele.me/xtop/' + api + '/1.0', {
    data: { params: { request } },
    headers: { 'Content-Type': 'application/json' },
    timeout,
  });
  const t = await r.text();
  let j = null;
  try { j = JSON.parse(t); } catch (e) {}
  return { code: String(j?.result?.code ?? j?.code ?? ''), data: j?.result?.data, err: j?.error?.message, text: t };
}

export async function probeFs(R) {
  const r = await post(R, FS_STAT, { teamId: TEAM_MAIN }, 30000);
  return r.code === '200';
}

/** 策略1：访问风神工作台页（刷新会话），若落到统一登录页则点登录 */
async function reloginViaWorkbench(ctx) {
  const page = await ctx.newPage();
  try {
    await page.goto(AEOLUS_URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(5000);
    const block = await detectLoginBlock(page);
    if (block.captcha || (block.password && block.sms)) {
      console.log('  登录页需要图形/短信验证码，自动登录不可行');
      return block.captcha ? 'captcha' : 'password';
    }
    if (await clickLogin(page)) await page.waitForTimeout(18000);
    return true;
  } catch (e) {
    console.log('  relogin(workbench) err', e.message);
    return true;
  } finally {
    await page.close().catch(() => {});
  }
}

/** 策略2：强制走统一登录中心，靠 SSO 静默续期 */
async function reloginViaSso(ctx) {
  const back = encodeURIComponent('https://aeolus.ele.me/?targetId=7715&moziAppType=LOGISTICS_COMPANY');
  const url = `https://mozi-login.alibaba-inc.com/?APP_NAME=LOGISTICS_COMPANY&BACK_URL=${back}`;
  const page = await ctx.newPage();
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(4000);
    const block = await detectLoginBlock(page);
    if (block.captcha || (block.password && block.sms)) {
      console.log('  SSO 页需要图形/短信验证码，自动登录不可行');
      return block.captcha ? 'captcha' : 'password';
    }
    if (await clickLogin(page)) {
      await page.waitForTimeout(18000);
      // 等回跳到 aeolus（最多再等 15s）
      for (let i = 0; i < 15; i++) {
        if ((page.url() || '').includes('aeolus.ele.me')) break;
        await page.waitForTimeout(1000);
      }
      console.log('  sso final url:', page.url());
    }
    return true;
  } catch (e) {
    console.log('  relogin(sso) err', e.message);
    return true;
  } finally {
    await page.close().catch(() => {});
  }
}

async function clickLogin(page) {
  try {
    const btn = page.getByRole('button', { name: /^登\s*录$/ });
    if (await btn.count()) {
      await btn.first().click({ timeout: 10000 });
      console.log('  LOGIN clicked');
      return true;
    }
  } catch (e) { console.log('  login click err', e.message); }
  return false;
}

/**
 * 判断登录页是否需要人工介入：
 *  - needsCaptcha: 出现图形/短信验证码输入框 -> 脚本无法自动登录
 *  - needsPassword: 需要账号密码（SSO 会话已失效）
 */
export async function detectLoginBlock(page) {
  try {
    return await page.evaluate(() => {
      const txt = (document.body.innerText || '');
      const inputs = [...document.querySelectorAll('input')].map(i => ({
        name: i.name || '', id: i.id || '', ph: i.placeholder || '', type: i.type || '',
      }));
      const captcha = inputs.some(i => /captcha|verify|code/i.test(i.name + i.id + i.ph))
        || /图形验证码|图片验证码|滑动验证|滑块/.test(txt);
      const pwd = inputs.some(i => i.type === 'password') || /密码登录/.test(txt);
      const sms = /短信登录|验证码登录/.test(txt);
      return { captcha, password: pwd, sms, snippet: txt.replace(/\s+/g, ' ').slice(0, 120) };
    });
  } catch (e) {
    return { captcha: false, password: false, sms: false, snippet: '' };
  }
}

/** 关闭我们打开的登录页，避免越积越多 */
async function closeLoginPages(ctx, keepPage) {
  for (const p of ctx.pages()) {
    if (p === keepPage) continue;
    const u = p.url() || '';
    if (u.includes('mozi-login') || u.includes('login.alibaba-inc')) {
      await p.close().catch(() => {});
    }
  }
}

/**
 * 确保风神接口可用。会话有效直接返回；否则尝试重建。
 * 若登录页出现验证码/密码（SSO 已失效），脚本无法自动恢复，立即停止重试并返回 false，
 * 避免频繁登录触发风控。
 */
export async function ensureFs(ctx, R, { attempts = 1, strategies = [reloginViaWorkbench, reloginViaSso] } = {}) {
  if (await probeFs(R)) return true;
  for (let round = 1; round <= attempts; round++) {
    for (const fn of strategies) {
      console.log(`  fs session invalid, relogin#${round} via ${fn.name}`);
      const blocked = await fn(ctx);
      if (blocked === 'captcha' || blocked === 'password') {
        console.log('  fs: 统一登录中心需要人工登录（验证码/密码），已停止自动重试');
        await closeLoginPages(ctx, null);
        return false;
      }
      await sleep(3000);
      if (await probeFs(R)) {
        console.log('  fs session restored');
        await closeLoginPages(ctx, null);
        return true;
      }
    }
  }
  console.log('  fs session NOT restored');
  return false;
}

/** 带重试的 fs 调用：遇 401 自动重建会话再试 */
export async function fsCall(ctx, R, api, request, { tries = 3 } = {}) {
  let last = null;
  for (let i = 0; i < tries; i++) {
    last = await post(R, api, request);
    if (last.code === '200') return last;
    if (last.code === '401' || last.code === '403') {
      await ensureFs(ctx, R, { attempts: 1 });
    } else {
      await sleep(1500);
    }
  }
  return last;
}

/** 带重试的 fs GET（骑手小组列表等 lpd.meepo 接口） */
export async function fsGet(ctx, R, path, { tries = 3 } = {}) {
  let last = null;
  for (let i = 0; i < tries; i++) {
    try {
      const r = await R.get('https://httpizza.ele.me' + path, {
        headers: { Origin: 'https://aeolus.ele.me', Referer: 'https://aeolus.ele.me/' },
        timeout: 60000,
      });
      const t = await r.text();
      let j = null;
      try { j = JSON.parse(t); } catch (e) {}
      const code = String(j?.code ?? '');
      last = { code, data: j?.data, text: t };
      if (code === '200' && j?.data) return last;
      if (code === '401') await ensureFs(ctx, R, { attempts: 1 });
      else await sleep(1500);
    } catch (e) {
      last = { code: 'ERR', data: null, text: String(e.message || e) };
      await sleep(1500);
    }
  }
  return last;
}
