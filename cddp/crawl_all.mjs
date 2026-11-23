// cddp 盯大盘：全 26 个可选区县（含景谷/墨江/镇沅/景东）盯站点完整采集
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { post as httpPost } from '../agg_board_1122/pipeline/http_client.mjs';
const require = createRequire('C:/Users/luansha/Documents/deepseek-harness/default-workspace/package.json');
const ROOT = 'C:/Users/luansha/WorkBuddy/2026-11-07-23-44-13/cddp_1122';
const RAW = path.join(ROOT, 'raw_all'); fs.mkdirSync(RAW, { recursive: true });
const PORT = Number(process.argv[2] || 9223);
const CD = 'xtop.lgt.datacenter.project.dingpan.dashboard.cd.';
// 组织树（已登录会话返回的完整 26 个 proxy_district）
const orgResp = JSON.parse(fs.readFileSync(path.join(ROOT, 'probe', 'org.json'), 'utf-8'));
const AREAS = [];
const walk = n => { for (const c of n.children || []) {
  if (c.subjectType === 'proxy_district') AREAS.push({ id: String(c.subjectId), name: c.subjectName });
  else walk(c);
} };
for (const n of orgResp.result?.data?.familyRootSubject ? [orgResp.result.data.familyRootSubject] : []) walk(n);
if (AREAS.length < 20) { console.error('组织树区域数异常', AREAS.length); process.exit(1); }
const ids = AREAS.map(a => a.id);
const BASE = {
  directArea: ids.map(id => `${id}/proxy_district/family`), organizationSubjectId: ids[0],
  organizationSubjectType: 'proxy_district', organizationSubjectIds: ids,
  searchSubjectType: 'bd', bdIds: [], orderChannelList: [],
  businessLineList: [], tmsLineList: [], productCategoryList: [],
  timeSlotList: null, compareDsList: [], sortDirection: null, sortIndicatorCode: null,
  pageSize: 300, pageNo: 1,
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
const calls = []; let seq = 0;
async function post(api, request, tag) {
  const id = ++seq, t0 = Date.now();
  let text = '', status = 0, err = null;
  try {
    const r = await httpPost(api, request, 120000);
    status = r.status || 0; text = r.text || ''; err = r.err || null;
  } catch (e) { err = String(e.message || e); }
  const file = `${String(id).padStart(3,'0')}_${tag}.json`;
  fs.writeFileSync(path.join(RAW, file), text, 'utf-8');
  let j = null; try { j = JSON.parse(text); } catch (e) {}
  const data = j && j.result && j.result.data !== undefined ? j.result.data : (j && j.data);
  const ok = status === 200 && !!j && !/UNAUTHORIZED|未登录|token为空/.test(text);
  calls.push({ id, tag, api, request: { ...request, organizationSubjectIds: request.organizationSubjectIds?.length },
    status, ok, bytes: text.length, ms: Date.now() - t0, file, err });
  console.log(`  [${id}] ${tag}: ${status} / ${(text.length/1024).toFixed(0)}KB / ${Date.now()-t0}ms ${ok?'':'FAIL '+err}`);
  await sleep(180);
  return { ok, data };
}
console.log('START', new Date().toISOString(), 'areas', AREAS.length);
const out = { meta: {
  page: 'https://xy.ele.me/cddp', iframe: 'https://r.ele.me/dm-area-data-board/#/agency/data/monitor',
  tab: '盯大盘 / 盯站点', collectedAt: new Date().toISOString(),
  areas: AREAS, directArea: BASE.directArea, bdIds: [],
  filters: '区域架构=全部26个可选proxy_district（含景谷/墨江/镇沅/景东）；圈站全选；订单渠道/业务线/运力线/时段/品类=全选；时间对比=默认',
  note: '服务端每10分钟更新；本快照为采集时刻实时值。日环比=_compare_rate1，周同比=_compare_rate2（小数）。',
} };
out.enums = (await post(CD.replace('dashboard.cd.','helper.')+'listEnums', {}, 'enums')).data;
out.userConfig = (await post(CD+'getUserConfig', {}, 'user_config')).data;
out.organization = (await post(CD+'searchOrganization', {}, 'organization')).data;
out.siteTable = (await post(CD+'queryIndicatorTable', { ...BASE, observationSubjectType:'site' }, 'table_site_all26')).data;
out.card = (await post(CD+'queryIndicatorCard', { ...BASE }, 'card_all26')).data;
out.tmsLine = (await post(CD+'queryTmsLineOverall', { ...BASE }, 'tms_line_all26')).data;
out.weather = (await post(CD+'queryWeatherOverall', { ...BASE }, 'weather_all26')).data;
out.meta.finishedAt = new Date().toISOString();
fs.writeFileSync(path.join(ROOT,'data.json'), JSON.stringify(out), 'utf-8');
fs.writeFileSync(path.join(ROOT,'manifest.json'), JSON.stringify({ ...out.meta, calls }, null, 2), 'utf-8');
console.log('\nDONE', out.meta.finishedAt, '| calls', calls.length, '| fail', calls.filter(c=>!c.ok).length);
console.log('site rows', out.siteTable?.tableRecords?.length, '| cols', out.siteTable?.tableColumns?.length);
const target = (out.siteTable?.tableRecords||[]).filter(r=>/景谷|墨江|镇沅|景东/.test(r.subject_name||''));
console.log('四县站点:', target.map(r=>`${r.subject_name}=${r.push_order_count}`).join(' '));
