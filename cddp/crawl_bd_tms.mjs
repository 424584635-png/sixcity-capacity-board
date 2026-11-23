// cddp 盯商圈（observationSubjectType=bd）：全部运力线 + 7 条运力线逐条采集
import { createRequire } from 'module';
import fs from 'fs';
import path from 'path';
import { post as httpPost } from '../agg_board_1122/pipeline/http_client.mjs';
const require = createRequire('C:/Users/luansha/Documents/deepseek-harness/default-workspace/package.json');
const ROOT = 'C:/Users/luansha/WorkBuddy/2026-11-07-23-44-13/cddp_1122';
const RAW = path.join(ROOT, 'raw_bd_tms'); fs.mkdirSync(RAW, { recursive: true });
const CD = 'xtop.lgt.datacenter.project.dingpan.dashboard.cd.';
const prev = JSON.parse(fs.readFileSync(path.join(ROOT, 'data.json'), 'utf-8'));
const ids = prev.meta.areas.map(a => a.id);
const LINES = [
  { code: null, name: '全部运力线' },
  { code: 5,  name: '专送' }, { code: 60, name: '普众' }, { code: 61, name: '优选' },
  { code: 66, name: '蜂跑' }, { code: 68, name: '优远' }, { code: 16, name: '联盟' }, { code: 0, name: '未知' },
];
const BASE = {
  directArea: ids.map(i => `${i}/proxy_district/family`), organizationSubjectId: ids[0],
  organizationSubjectType: 'proxy_district', organizationSubjectIds: ids,
  searchSubjectType: 'bd', bdIds: [], orderChannelList: [], businessLineList: [], productCategoryList: [],
  timeSlotList: null, compareDsList: [], sortDirection: null, sortIndicatorCode: null,
  observationSubjectType: 'bd', pageSize: 300, pageNo: 1,
};
const sleep = ms => new Promise(r => setTimeout(r, ms));
let seq = 0; const calls = [];
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
  calls.push({ id, tag, status, ok, bytes: text.length, ms: Date.now() - t0, file, err });
  console.log(`  [${id}] ${tag}: ${status} / ${(text.length/1024).toFixed(0)}KB / rows ${data?.tableRecords?.length ?? 'n/a'} / ${Date.now()-t0}ms ${ok?'':'FAIL '+err}`);
  await sleep(200);
  return { ok, data };
}
console.log('START', new Date().toISOString(), 'areas', ids.length, 'lines', LINES.map(l=>l.name).join('/'));
const out = { meta: {
  page: 'https://xy.ele.me/cddp', tab: '盯商圈', observationSubjectType: 'bd',
  collectedAt: new Date().toISOString(), areasIds: ids,
  lines: LINES, filters: '区域架构=全部26区县；圈站全选；运力线=逐条；其余全选；时间对比默认',
  note: '服务端每10分钟更新；日环比=_compare_rate1，周同比=_compare_rate2（小数）。',
}, tables: {}, lineOverall: null };
for (const l of LINES) {
  const x = await post(CD + 'queryIndicatorTable', { ...BASE, tmsLineList: l.code === null ? [] : [l.code] }, 'bd_' + (l.code === null ? 'all' : l.code));
  out.tables[l.name] = { lineCode: l.code, columns: x.data?.tableColumns || [], records: x.data?.tableRecords || [], ok: x.ok };
}
out.lineOverall = (await post(CD + 'queryTmsLineOverall', { ...BASE, tmsLineList: [] }, 'tms_line_overall')).data;
out.meta.finishedAt = new Date().toISOString();
fs.writeFileSync(path.join(ROOT, 'data_bd_tms.json'), JSON.stringify(out), 'utf-8');
fs.writeFileSync(path.join(ROOT, 'manifest_bd_tms.json'), JSON.stringify({ ...out.meta, calls }, null, 2), 'utf-8');
console.log('\nDONE', out.meta.finishedAt, '| calls', calls.length, '| fail', calls.filter(c=>!c.ok).length);
for (const [n,t] of Object.entries(out.tables)) console.log(' ', n, t.records.length, 'rows');
