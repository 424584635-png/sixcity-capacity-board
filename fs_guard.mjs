// 风神(aeolus/fs) 会话守卫：探测 -> 未登录则重新建立会话 -> 供采集脚本复用
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
    if (await clickLogin(page)) await page.waitForTimeout(18000);
    return true;
  } catch (e) {
    console.log('  relogin(workbench) err', e.message);
    return false;
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
    return false;
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
 * 确保风神接口可用。会话有效直接返回；否则最多尝试 strategies.length*attempts 次重建。
 * 返回 true 表示可用。
 */
export async function ensureFs(ctx, R, { attempts = 2, strategies = [reloginViaWorkbench, reloginViaSso] } = {}) {
  if (await probeFs(R)) return true;
  for (let round = 1; round <= attempts; round++) {
    for (const fn of strategies) {
      console.log(`  fs session invalid, relogin#${round} via ${fn.name}`);
      await fn(ctx);
      await sleep(3000);
      if (await probeFs(R)) {
        console.log('  fs session restored');
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
