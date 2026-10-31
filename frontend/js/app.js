const $ = s => document.querySelector(s);
const esc = v => String(v ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const M = (a, f) => a.map(f).join('');
const cap = s => s[0].toUpperCase() + s.slice(1);
const PAGES = [['Overview','Overview','⌂'],['Upload','Upload data','↥'],['Cleaning','Data cleaning','✳'],['Explorer','Data explorer','▤'],
  ['EDA','EDA studio','◒'],['Quality','Data quality','◇'],['Analytics','Insights','✧'],['Reports','Reports & exports','⇩']];
const PAGECOPY = {Overview:['Your data, at a glance','A clear snapshot of the dataset you’re working with.'],Upload:['Bring your data into focus','Upload a CSV and get a clean, analysis-ready starting point.'],Cleaning:['Make your data analysis-ready','Preview changes, apply them with confidence, and undo any step.'],Explorer:['Get closer to the details','Search, sort, and inspect every row in your dataset.'],EDA:['Explore what your data is saying','Build a chart, review distributions, and spot relationships.'],Quality:['Know what you can trust','See completeness, consistency, and issues across your columns.'],Analytics:['Insights, made understandable','Useful patterns calculated directly from your current dataset.'],Reports:['Take your work with you','Export cleaned data and a record of your transformations.']};
let SID = localStorage.getItem('sid'), PROF = null, META = {}, CH = null;
const R = {};

function toast(m, bad) { const t = $('#toast'); t.textContent = m; t.className = bad ? 'bad show' : 'show';
  clearTimeout(toast.t); toast.t = setTimeout(() => t.className = '', 3500); }
async function api(p, o = {}) {
  const h = {'X-SID': SID || ''}; let body;
  if (o.json) { h['Content-Type'] = 'application/json'; body = JSON.stringify(o.json); }
  const r = await fetch('/api/' + p, {method: o.json ? 'POST' : 'GET', headers: h, body});
  if (!r.ok) { const e = await r.json().catch(() => ({}));
    throw new Error(typeof e.detail === 'string' ? e.detail : 'Request failed. Check your input.'); }
  return o.blob ? r.blob() : r.json();
}
async function download(path, name) {
  try { const b = await api(path, {blob: 1}); const a = document.createElement('a');
    a.href = URL.createObjectURL(b); a.download = name; a.click(); URL.revokeObjectURL(a.href); }
  catch (e) { toast(e.message, 1); }
}
async function refresh() {
  try { META = await api('profile'); PROF = META.profile; $('#ds').textContent = META.name;
    $('#status').innerHTML = '<i></i> Dataset ready'; $('#status').className = 'pill ok'; }
  catch { PROF = null; $('#ds').textContent = 'No dataset'; $('#status').innerHTML = '<i></i> Waiting for upload'; $('#status').className = 'pill'; }
}
const view = h => $('#view').innerHTML = h;
const card = (l, v) => `<div class="card"><small>${l}</small><b>${v}</b></div>`;
const tbl = (head, rows) => `<div class="scroll"><table><thead><tr>${M(head, h => `<th>${h}</th>`)}</tr></thead><tbody>${
  M(rows, r => `<tr>${M(r, c => `<td>${c}</td>`)}</tr>`)}</tbody></table></div>`;
const rowsTable = d => `<div class="scroll"><table><thead><tr>${M(d.columns, c => `<th data-c="${esc(c)}">${esc(c)}</th>`)}</tr></thead><tbody>${
  M(d.rows, r => `<tr>${M(d.columns, c => `<td>${esc(r[c])}</td>`)}</tr>`)}</tbody></table></div>`;
const size = n => n > 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.ceil(n / 1024) + ' KB';

function go(p) { location.hash === '#' + p ? render() : location.hash = p; }
async function render() {
  const p = location.hash.slice(1) || (PROF ? 'Overview' : 'Upload');
  document.querySelectorAll('#nav a').forEach(a => a.classList.toggle('on', a.dataset.p === p));
  const copy = PAGECOPY[p] || PAGECOPY.Overview;
  $('#pagehead').innerHTML = `<div class="page-heading"><div><p class="eyebrow">DATAPILOT WORKSPACE</p><h1>${copy[0]}</h1><p>${copy[1]}</p></div>${PROF ? `<span class="heading-action">Working with <b>${esc(META.name)}</b></span>` : ''}</div>`;
  if (!R[p]) return;
  if (!PROF && p !== 'Upload') return view(`<section><h2>No dataset yet</h2><p class="muted">Upload a CSV file to get started.</p><button class="primary" onclick="go('Upload')">Upload dataset</button></section>`);
  try { await R[p](); } catch (e) { toast(e.message, 1); }
}

R.Overview = async () => {
  const q = await api('quality'), p = PROF, o = META.original;
  view(`<div class="grid">${card('Rows', p.rows)}${card('Columns', p.cols)}${card('Duplicate rows', p.duplicates)}${card('Missing cells', q.missing)}${card('Quality score', q.score + '/100')}</div>
  <section><h2>Columns</h2><p class="muted">Original file: ${o.rows} rows, ${o.cols} columns. Current data: ${p.rows} rows, ${p.cols} columns. To correct a wrong type, use Data cleaning, Data type.</p>
  ${tbl(['Column','Type','Stored as','Missing','Unique','Notes'], p.columns.map(c => [esc(c.name), c.kind, esc(c.dtype), `${c.missing} (${c.missing_pct}%)`, c.unique,
    [c.constant && 'constant', c.id_like && 'possible ID'].filter(Boolean).join(', ')]))}</section>`);
};

R.Upload = () => {
  view(`<section><h2>Start with your data</h2><p class="muted">Drop in a CSV and DataPilot will profile it instantly, so you can move straight into analysis.</p><label class="drop" id="drop"><strong>Drop your CSV file here</strong><span>or <u>browse files</u> from your device</span><input id="file" type="file" accept=".csv" hidden></label>
  <div class="bar" id="bar" hidden><i></i></div><div class="upload-foot"><p class="muted">CSV format · Up to 20 MB</p><p class="muted">⌑&nbsp; Your file stays private to this session</p></div></section><div id="prev"></div>`);
  const d = $('#drop');
  ['dragover', 'dragenter'].forEach(e => d.addEventListener(e, x => { x.preventDefault(); d.classList.add('on'); }));
  ['dragleave', 'drop'].forEach(e => d.addEventListener(e, x => { x.preventDefault(); d.classList.remove('on'); }));
  d.addEventListener('drop', x => send(x.dataTransfer.files[0]));
  $('#file').onchange = e => send(e.target.files[0]);
  if (PROF) showPrev();
};
function send(f) {
  if (!f) return;
  if (!f.name.toLowerCase().endsWith('.csv')) return toast('Only .csv files are accepted.', 1);
  if (f.size > 20 * 1048576) return toast('The file is larger than 20 MB.', 1);
  const fd = new FormData(); fd.append('file', f); const x = new XMLHttpRequest(), b = $('#bar');
  x.open('POST', '/api/upload'); b.hidden = false;
  x.upload.onprogress = e => b.firstChild.style.width = (e.loaded / e.total * 100) + '%';
  x.onload = async () => { let r = {}; try { r = JSON.parse(x.responseText); } catch {}
    if (x.status !== 200) { b.hidden = true; return toast(typeof r.detail === 'string' ? r.detail : 'Upload failed.', 1); }
    SID = r.sid; localStorage.setItem('sid', SID); await refresh(); toast('Uploaded and profiled.'); showPrev(); };
  x.onerror = () => toast('Could not reach the server.', 1);
  x.send(fd);
}
async function showPrev() {
  const d = await api('rows?size=15');
  $('#prev').innerHTML = `<section><h2>${esc(META.name)}</h2><p class="muted">${size(META.size)}, ${PROF.rows} rows, ${PROF.cols} columns. First 15 rows:</p>${rowsTable(d)}</section>`;
}

const OPS = [
  ['missing', 'Missing values', 'Fill or drop empty cells in one column.', [['column','col'],['strategy',['mean','median','mode','custom','drop_rows','drop_column']],['value','text','Custom value']]],
  ['duplicates', 'Duplicate rows', 'Remove exact duplicate rows. The first copy is kept.', []],
  ['empty', 'Empty rows and columns', 'Remove rows and columns that have no values.', []],
  ['text', 'Text cleaning', 'Trim spaces and standardize capitalization.', [['column','col*'],['case',['none','lower','upper','title']]]],
  ['dtype', 'Data type', 'Fix a wrong type. Values that cannot convert become missing.', [['column','col'],['type',['numeric','integer','date','text']]]],
  ['outliers', 'Outliers', 'Preview the count first, then remove or cap them.', [['column','num'],['method',['iqr','zscore','iforest']],['action',['remove','cap']]]]];
R.Cleaning = async () => {
  const names = PROF.columns.map(c => c.name), nums = PROF.columns.filter(c => c.kind === 'numeric').map(c => c.name);
  const opt = a => M(a, c => `<option>${esc(c)}</option>`);
  const field = ([n, k, ph]) => k === 'text' ? `<label>${n}<input name="${n}" placeholder="${ph}"></label>`
    : `<label>${n}<select name="${n}">${k === 'col' ? opt(names) : k === 'col*' ? '<option value="*">All text columns</option>' + opt(names) : k === 'num' ? opt(nums) : opt(k)}</select></label>`;
  view(`<div class="row"><button id="undo">Undo last step</button><button id="reset" class="danger">Reset to original</button></div>
  <div class="forms">${M(OPS, ([op, t, h, fs]) => `<form data-op="${op}"><h3>${t}</h3><p class="muted">${h}</p>${M(fs, field)}
  <div class="row"><button type="button" data-p="1">Preview</button><button class="primary">Apply</button></div><output></output></form>`)}</div>
  <section><h2>Cleaning log</h2><div id="log"></div></section>`);
  document.querySelectorAll('form[data-op]').forEach(f => {
    const out = f.querySelector('output');
    const run = async prev => {
      const body = Object.fromEntries(new FormData(f)); body.preview = prev;
      try { const r = await api('clean/' + f.dataset.op, {json: body});
        if (prev) out.textContent = `${r.affected} records would be affected. Nothing has been changed yet.`;
        else { await refresh(); toast(`Applied: ${r.affected} records affected.`); R.Cleaning(); } }
      catch (e) { out.textContent = e.message; toast(e.message, 1); }
    };
    f.onsubmit = e => { e.preventDefault(); run(false); };
    f.querySelector('[data-p]').onclick = () => run(true);
  });
  const act = async (a, m) => { try { await api(a, {json: {}}); await refresh(); toast(m); R.Cleaning(); } catch (e) { toast(e.message, 1); } };
  $('#undo').onclick = () => act('undo', 'Undid the last step.');
  $('#reset').onclick = () => confirm('Discard all cleaning and restore the original file?') && act('reset', 'Restored the original data.');
  const log = await api('log');
  $('#log').innerHTML = log.length ? tbl(['Operation','Column','Records','Time','Status'], log.map(l => [l.operation, esc(l.column), l.affected, l.time, l.status]))
    : '<p class="muted">No cleaning steps yet.</p>';
};

R.Explorer = () => {
  const st = {page: 1, q: '', sort: '', desc: false, pages: 1};
  view(`<section><div class="row"><label>Search<input id="q" placeholder="Search all columns"></label><button id="pv">Previous</button><button id="nx">Next</button>
  <button id="dlf">Download filtered CSV</button><span id="info" class="muted"></span></div><div id="tb"></div></section>`);
  const load = async () => {
    const d = await api('rows?' + new URLSearchParams({page: st.page, size: 25, q: st.q, sort: st.sort, desc: st.desc}));
    st.pages = Math.max(1, Math.ceil(d.total / 25));
    $('#info').textContent = `${d.total} rows, page ${st.page} of ${st.pages}. Click a column header to sort.`;
    $('#tb').innerHTML = rowsTable(d);
    document.querySelectorAll('#tb th').forEach(th => th.onclick = () => {
      st.desc = st.sort === th.dataset.c ? !st.desc : false; st.sort = th.dataset.c; st.page = 1; load(); });
  };
  let t; $('#q').oninput = e => { clearTimeout(t); t = setTimeout(() => { st.q = e.target.value; st.page = 1; load().catch(e => toast(e.message, 1)); }, 300); };
  $('#pv').onclick = () => { if (st.page > 1) { st.page--; load(); } };
  $('#nx').onclick = () => { if (st.page < st.pages) { st.page++; load(); } };
  $('#dlf').onclick = () => download('export/csv?' + new URLSearchParams({q: st.q, sort: st.sort, desc: st.desc}), 'filtered_data.csv');
  return load();
};

R.EDA = async () => {
  const d = await api('eda'), names = PROF.columns.map(c => c.name), nums = PROF.columns.filter(c => c.kind === 'numeric').map(c => c.name);
  const opt = a => M(a, c => `<option>${esc(c)}</option>`), S = ['mean','median','mode','std','var','min','q1','q3','p90','max','skew','kurt'];
  const cm = d.correlation;
  view(`<section><h2>Chart builder</h2><div class="row">
    <label>Chart<select id="ct">${opt(['histogram','bar','line','pie','doughnut','scatter'])}</select></label>
    <label>X column<select id="cx">${opt(names)}</select></label>
    <label>Y column<select id="cy"><option value="">(count rows)</option>${opt(nums)}</select></label>
    <label>Aggregate<select id="ca">${opt(['mean','sum','count','median','max','min'])}</select></label>
    <button class="primary" id="draw">Draw chart</button><button id="png">Download PNG</button></div>
    <div class="chartbox"><canvas id="cv"></canvas></div></section>
  <section><h2>Numeric summary</h2>${Object.keys(d.stats).length ? tbl(['Column', ...S], Object.entries(d.stats).map(([c, s]) => [esc(c), ...S.map(k => s[k] ?? '-')])) : '<p class="muted">No numeric columns.</p>'}</section>
  <section><h2>Correlation matrix</h2>${cm ? tbl(['', ...cm.cols.map(esc)], cm.cols.map((c, i) => [esc(c), ...cm.matrix[i].map(v =>
    `<span style="display:block;padding:2px 6px;border-radius:4px;background:rgba(79,70,229,${Math.abs(v ?? 0) * .8});color:${Math.abs(v ?? 0) > .55 ? '#fff' : 'inherit'}">${v ?? '-'}</span>`)])) : '<p class="muted">At least two numeric columns are needed.</p>'}</section>
  <section><h2>Categorical columns</h2>${Object.keys(d.categories).length ? M(Object.entries(d.categories), ([c, v]) =>
    `<h3>${esc(c)}</h3><p class="muted">${v.unique} unique values. Most frequent: ${esc(v.most)}. Least frequent: ${esc(v.least)}.</p>${tbl(['Value','Count','Share'], v.top.map(t => [esc(t[0]), t[1], t[2] + '%']))}`) : '<p class="muted">No categorical columns.</p>'}</section>`);
  const draw = async () => {
    const t = $('#ct').value, x = $('#cx').value, y = $('#cy').value, a = $('#ca').value;
    const mode = t === 'histogram' ? 'hist' : t === 'scatter' ? 'scatter' : 'group';
    try {
      const r = await api('chart?' + new URLSearchParams({mode, x, y, agg: a}));
      CH?.destroy(); const circ = ['pie', 'doughnut'].includes(t), pal = ['#4F46E5','#0EA5E9','#16A34A','#D97706','#DC2626','#7C3AED','#64748B'];
      CH = new Chart($('#cv'), {type: t === 'histogram' ? 'bar' : t,
        data: mode === 'scatter' ? {datasets: [{label: `${y} vs ${x}`, data: r.points, backgroundColor: '#4F46E5'}]}
          : {labels: r.labels, datasets: [{label: y && a !== 'count' ? `${a} of ${y}` : 'count', data: r.values,
            backgroundColor: circ ? r.labels.map((_, i) => pal[i % pal.length]) : '#4F46E5', borderColor: '#4F46E5'}]},
        options: {responsive: true, maintainAspectRatio: false},
        plugins: [{id: 'bg', beforeDraw: c => { c.ctx.save(); c.ctx.globalCompositeOperation = 'destroy-over'; c.ctx.fillStyle = '#fff'; c.ctx.fillRect(0, 0, c.width, c.height); c.ctx.restore(); }}]});
    } catch (e) { toast(e.message, 1); }
  };
  $('#draw').onclick = draw;
  $('#png').onclick = () => { if (!CH) return toast('Draw a chart first.', 1); const a = document.createElement('a'); a.href = CH.toBase64Image(); a.download = 'chart.png'; a.click(); };
  if (nums.length) { $('#cx').value = nums[0]; draw(); } else { $('#ct').value = 'bar'; draw(); }
};

R.Quality = async () => {
  const q = await api('quality');
  view(`<div class="grid">${card('Overall score', q.score + '/100')}${M(Object.entries(q.metrics), ([k, v]) => card(cap(k), v + '%'))}
  ${card('Missing', q.missing_pct + '%')}${card('Duplicates', q.dup_pct + '%')}${card('Invalid values', q.invalid)}</div>
  <section><h2>Recommendations</h2><ul>${M(q.recommendations, r => `<li>${esc(r)}</li>`)}</ul></section>
  <section><h2>Completeness by column</h2>${M(q.columns, c => `<div class="crow"><span>${esc(c.name)}</span><div class="meter"><i style="width:${c.completeness}%"></i></div><span>${c.completeness}%</span></div>`)}</section>
  <section><h2>How the score is calculated</h2><p>The overall score is the average of four metrics, each from 0 to 100.</p><ul>
  <li>Completeness: share of cells that are not empty.</li><li>Uniqueness: share of rows that are not exact duplicates.</li>
  <li>Validity: share of cells that are not blank text or infinity.</li>
  <li>Consistency: share of text values that do not differ from another value only by spaces or capitalization.</li></ul></section>`);
};

R.Analytics = async () => {
  const l = await api('insights');
  view(`<section><h2>Insights from your data</h2><p class="muted">Every statement below is calculated from the current dataset.</p><ul>${M(l, i => `<li>${esc(i)}</li>`)}</ul></section>`);
};

R.Reports = () => {
  view(`<section><h2>Downloads</h2><p class="muted">Exports use the current cleaned data. Text that could run as a spreadsheet formula is made safe.</p>
  <div class="row"><button class="primary" data-d="export/csv|cleaned_data.csv">Cleaned CSV</button><button data-d="export/excel|cleaned_data.xlsx">Cleaned Excel (with log)</button>
  <button data-d="export/log|cleaning_log.csv">Cleaning history</button></div></section>`);
  document.querySelectorAll('[data-d]').forEach(b => b.onclick = () => download(...b.dataset.d.split('|')));
};

$('#nav').innerHTML = M(PAGES, ([k, l, icon]) => `<a href="#${k}" data-p="${k}"><span class="nav-icon" aria-hidden="true">${icon}</span><span>${l}</span>${k === 'Overview' ? '<span class="nav-arrow">›</span>' : ''}</a>`);
window.onhashchange = render;
refresh().then(render);
