// ── State ─────────────────────────────────────────────────────────────────────
let dashboardData = null;
let charts = {};
let currentPage = 'intro';
let currentProduct = null;
let wcModes = { overview: 'pos', product: 'pos' };
let activeReviewTab = 'neg';

// AI analysis: backend proxy (server.py) for live Compare-page generation.
const COMPARE_API = 'http://localhost:5001/api/compare';
// Cache compare results per product-pair so re-viewing the same pair is free.
const compareCache = {};

const APP_COLORS = {
    'ChatGPT':           '#10a37f',
    'Microsoft_Copilot': '#0078d4',
    'Google_Gemini':     '#4285f4',
    'Perplexity':        '#22d3ee',
    'Claude':            '#d97757'
};

const THEME_COLORS = ['#3b82f6','#10b981','#f59f00','#f43f5e'];

Chart.defaults.color = '#6b7280';
Chart.defaults.font.family = "'DM Sans', sans-serif";
Chart.defaults.font.size = 12;

// ── Init ──────────────────────────────────────────────────────────────────────
async function init() {
    try {
        const res = await fetch('insights_data.json');
        dashboardData = await res.json();
        populateDropdowns();
        setupListeners();
        renderIntro();
        renderOverview();
        navigate('intro');
    } catch(e) {
        console.error('Failed to load:', e);
    }
}

function populateDropdowns() {
    const apps = dashboardData.apps;
    const cmp1 = document.getElementById('cmp-app1');
    const cmp2 = document.getElementById('cmp-app2');
    const rvf  = document.getElementById('reviews-app-filter');
    apps.forEach(app => {
        const label = app.replace('_',' ');
        cmp1.innerHTML += `<option value="${app}">${label}</option>`;
        cmp2.innerHTML += `<option value="${app}">${label}</option>`;
        rvf.innerHTML  += `<option value="${app}">${label}</option>`;
    });
    if (apps.length >= 2) cmp2.value = apps[1];
}

function setupListeners() {
    document.getElementById('cmp-app1').addEventListener('change', renderCompare);
    document.getElementById('cmp-app2').addEventListener('change', renderCompare);
    document.getElementById('search-input').addEventListener('input', handleSearch);
    document.getElementById('reviews-app-filter').addEventListener('change', () => renderReviews());
    document.querySelectorAll('.tab-btn[data-tab]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tab-btn[data-tab]').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeReviewTab = btn.dataset.tab;
            renderReviews();
        });
    });
}

// ── Navigation ────────────────────────────────────────────────────────────────
function navigate(page) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const PRODUCTS = ['ChatGPT','Claude','Google_Gemini','Microsoft_Copilot','Perplexity'];
    if (PRODUCTS.includes(page)) {
        document.getElementById('page-product').classList.add('active');
        currentProduct = page;
        renderProduct(page);
    } else {
        const el = document.getElementById(`page-${page}`);
        if (el) el.classList.add('active');
        if (page === 'compare') renderCompare();
        if (page === 'reviews') renderReviews();
    }
    const navItem = document.querySelector(`.nav-item[data-page="${page}"]`);
    if (navItem) navItem.classList.add('active');
    currentPage = page;
    window.scrollTo(0, 0);
}

// ── Intro Page ────────────────────────────────────────────────────────────────
function renderIntro() {
    if (!dashboardData) return;

    // Video date
    const dateEl = document.getElementById('video-date');
    if (dateEl) dateEl.textContent = new Date().toLocaleDateString('en-US', {month:'long', day:'numeric', year:'numeric'});

    const total = dashboardData.overview.reduce((s,i) => s + i.Total_Reviews, 0);
    const heroEl = document.getElementById('hero-total');
    if (heroEl) heroEl.textContent = total.toLocaleString();
    const list = document.getElementById('intro-product-list');
    if (list) {
        list.innerHTML = dashboardData.overview.map(item => {
            const color = APP_COLORS[item.App] || '#4f8ef7';
            return `
            <div class="product-pill" onclick="navigate('${item.App}')">
                <span style="width:8px;height:8px;border-radius:50%;background:${color};display:inline-block;flex-shrink:0"></span>
                ${item.App.replace('_',' ')}
                <span class="product-pill-stat">${item.Avg_Star.toFixed(2)}★</span>
            </div>`;
        }).join('');
    }
}

// ── Subscribe (backend → Google Sheets, the same list the weekly mailer reads) ─
const SUBSCRIBE_API = 'http://localhost:5001/api/subscribe';

async function handleSubscribe() {
    const input = document.getElementById('subscribe-email');
    const msg   = document.getElementById('subscribe-msg');
    const email = input.value.trim();

    if (!email || !email.includes('@')) {
        msg.style.display = 'block';
        msg.style.color   = '#dc2626';
        msg.textContent   = 'Please enter a valid email address.';
        return;
    }

    msg.style.display = 'block';
    msg.style.color   = '#6b7280';
    msg.textContent   = 'Submitting…';

    try {
        const res = await fetch(SUBSCRIBE_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        if (res.ok) {
            msg.style.color = '#15803d';
            msg.textContent = `✓ ${data.message || "Subscribed!"}`;
            input.value = '';
        } else {
            msg.style.color = '#dc2626';
            msg.textContent = data.error || 'Something went wrong. Please try again.';
        }
    } catch (e) {
        msg.style.color = '#dc2626';
        msg.textContent = 'Could not reach the server. Is the backend running? (python server.py)';
    }
}

// ── Overview Page ─────────────────────────────────────────────────────────────
function renderOverview() {
    if (!dashboardData) return;
    renderBanner('overview', 'All');
    renderAnalysis('overview-analysis', dashboardData.analysis && dashboardData.analysis.overview);
    renderKPIBlock('overview-kpis', 'All');
    renderTimeSeriesChart('ov-timeSeriesChart', 'All');
    renderBarChart('ov-barChart', 'All');
    renderDoughnutChart('ov-doughnutChart', 'All');
    renderDistChart('ov-distChart', 'All');
    renderPolarChart('ov-polarChart');
    renderWordCloud('ov-wordcloud', 'All', 'pos');
}

// ── Product Page ──────────────────────────────────────────────────────────────
function renderProduct(app) {
    const item = getOverview(app);
    const color = APP_COLORS[app] || '#3b82f6';
    document.getElementById('product-title').textContent = app.replace('_',' ');
    document.getElementById('product-desc').textContent =
        `${item.Total_Reviews.toLocaleString()} reviews · Avg ${item.Avg_Star.toFixed(2)}★ · Sentiment ${item.Avg_Sentiment.toFixed(3)}`;
    document.getElementById('page-product').style.setProperty('--product-color', color);
    renderBanner('product', app);
    const productAnalysis = dashboardData.analysis && dashboardData.analysis.products
        ? dashboardData.analysis.products[app] : null;
    renderAnalysis('product-analysis', productAnalysis);
    renderKPIBlock('product-kpis', app);
    renderTimeSeriesChart('pr-timeSeriesChart', app);
    renderBarChart('pr-barChart', app);
    renderDoughnutChart('pr-doughnutChart', app);
    renderDistChart('pr-distChart', app);
    renderPolarChart('pr-polarChart');
    renderWordCloud('pr-wordcloud', app, 'pos');
    wcModes.product = 'pos';
    document.getElementById('pr-wc-pos').classList.add('active');
    document.getElementById('pr-wc-neg').classList.remove('active');
}

// ── Word Cloud Toggle ─────────────────────────────────────────────────────────
function switchWC(context, mode) {
    wcModes[context] = mode;
    const prefix = context === 'overview' ? 'ov' : 'pr';
    document.getElementById(`${prefix}-wc-pos`).classList.toggle('active', mode === 'pos');
    document.getElementById(`${prefix}-wc-neg`).classList.toggle('active', mode === 'neg');
    const app = context === 'overview' ? 'All' : currentProduct;
    const container = context === 'overview' ? 'ov-wordcloud' : 'pr-wordcloud';
    renderWordCloud(container, app, mode);
}

// ── AI Analysis (offline: overview + product pages) ───────────────────────────
function renderAnalysis(containerId, text) {
    const el = document.getElementById(containerId);
    if (!el) return;
    if (!text) {
        // No analysis in JSON yet (generate_insights.py not run) — hide the card.
        el.style.display = 'none';
        return;
    }
    el.style.display = '';
    const meta = dashboardData.analysis && dashboardData.analysis.generated_at
        ? `<div class="ai-analysis-meta">Generated ${new Date(dashboardData.analysis.generated_at).toLocaleDateString()}</div>`
        : '';
    el.innerHTML =
        `<div class="ai-analysis-label">✨ AI Analysis</div>
         <p class="ai-analysis-text">${escapeHTML(text)}</p>${meta}`;
}

function escapeHTML(s) {
    return String(s).replace(/[&<>"']/g, c =>
        ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

// ── AI Comparison (live: Compare page, via server.py backend) ─────────────────
function compareCacheKey(a, b) {
    return [a, b].sort().join('::');   // A vs B and B vs A share one cache entry
}

async function generateCompareAnalysis() {
    const app1 = document.getElementById('cmp-app1').value;
    const app2 = document.getElementById('cmp-app2').value;
    const body = document.getElementById('compare-analysis-body');
    const btn  = document.getElementById('cmp-generate-btn');

    if (!app1 || !app2 || app1 === app2) {
        body.innerHTML = `<p class="ai-analysis-error">Pick two different products first.</p>`;
        return;
    }

    const key = compareCacheKey(app1, app2);
    if (compareCache[key]) {
        body.innerHTML = `<p class="ai-analysis-text">${escapeHTML(compareCache[key])}</p>`;
        return;
    }

    btn.disabled = true;
    body.innerHTML = `<span class="ai-loading">Analysing&nbsp;</span>`;
    try {
        const res = await fetch(COMPARE_API, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ apps: [app1, app2] })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
        compareCache[key] = data.analysis;
        body.innerHTML = `<p class="ai-analysis-text">${escapeHTML(data.analysis)}</p>`;
    } catch (e) {
        const hint = e.message.includes('Failed to fetch')
            ? 'Is the backend running? Start it with: python server.py'
            : e.message;
        body.innerHTML = `<p class="ai-analysis-error">⚠ ${escapeHTML(hint)}</p>`;
    } finally {
        btn.disabled = false;
    }
}

// ── Compare Page ──────────────────────────────────────────────────────────────
function renderCompare() {
    if (!dashboardData) return;
    const app1 = document.getElementById('cmp-app1').value;
    const app2 = document.getElementById('cmp-app2').value;
    if (!app1 || !app2 || app1 === app2) return;

    // Reset the AI comparison area for this pair: show cached result if we have
    // one, otherwise prompt the user to generate.
    const cmpBody = document.getElementById('compare-analysis-body');
    if (cmpBody) {
        const cached = compareCache[compareCacheKey(app1, app2)];
        cmpBody.innerHTML = cached
            ? `<p class="ai-analysis-text">${escapeHTML(cached)}</p>`
            : `<p class="ai-analysis-hint">Generate an AI head-to-head for ${app1.replace('_',' ')} vs ${app2.replace('_',' ')}.</p>`;
    }
    const panels = document.getElementById('compare-panels');
    panels.innerHTML = [app1, app2].map(app => {
        const item = getOverview(app);
        const color = APP_COLORS[app] || '#3b82f6';
        const fivePct = ((item.Rating_Distribution['5']/item.Total_Reviews)*100).toFixed(1);
        const onePct  = ((item.Rating_Distribution['1']/item.Total_Reviews)*100).toFixed(1);
        const topPain = Object.entries(item.Theme_Counts).filter(([k])=>k!=='General').sort((a,b)=>b[1]-a[1])[0];
        return `
        <div class="card compare-panel">
            <div class="compare-panel-header">
                <div class="nav-dot" style="background:${color};width:12px;height:12px"></div>
                <div class="compare-panel-name">${app.replace('_',' ')}</div>
            </div>
            <div class="compare-panel-kpis">
                <div class="kpi-card" style="padding:0.75rem">
                    <div class="kpi-label">Avg Star</div>
                    <div class="kpi-val" style="font-size:1.3rem">${item.Avg_Star.toFixed(2)}<small>/5</small></div>
                </div>
                <div class="kpi-card" style="padding:0.75rem">
                    <div class="kpi-label">Sentiment</div>
                    <div class="kpi-val" style="font-size:1.3rem">${item.Avg_Sentiment.toFixed(3)}</div>
                </div>
                <div class="kpi-card" style="padding:0.75rem">
                    <div class="kpi-label">Std Dev</div>
                    <div class="kpi-val" style="font-size:1.3rem">${item.Std_Dev.toFixed(2)}</div>
                </div>
            </div>
            <div class="compare-pct-row">
                <span class="pct-badge pos">5★ ${fivePct}%</span>
                <span class="pct-badge neg">1★ ${onePct}%</span>
                ${topPain ? `<span class="pct-badge pain">🔥 ${topPain[0]}</span>` : ''}
            </div>
        </div>`;
    }).join('');

    destroyChart('cmp-timeChart');
    const ts = dashboardData.time_series_daily;
    charts['cmp-timeChart'] = new Chart(document.getElementById('cmp-timeChart').getContext('2d'), {
        type: 'line',
        data: { labels: ts[app1].dates, datasets: [app1,app2].map(app => ({
            label: app.replace('_',' '), data: ts[app].avg_sentiment,
            borderColor: APP_COLORS[app], backgroundColor:'transparent',
            tension:0.4, borderWidth:2.5, pointRadius:0
        }))},
        options: lineOptions()
    });

    destroyChart('cmp-distChart');
    charts['cmp-distChart'] = new Chart(document.getElementById('cmp-distChart').getContext('2d'), {
        type:'bar',
        data:{ labels:['1★','2★','3★','4★','5★'], datasets:[app1,app2].map(app => {
            const d=getOverview(app).Rating_Distribution;
            return { label:app.replace('_',' '), data:['1','2','3','4','5'].map(k=>d[k]||0), backgroundColor:APP_COLORS[app]+'cc', borderRadius:4 };
        })},
        options: barOptions()
    });

    destroyChart('cmp-themeChart');
    const themes = Object.keys(getOverview(app1).Theme_Counts);
    charts['cmp-themeChart'] = new Chart(document.getElementById('cmp-themeChart').getContext('2d'), {
        type:'bar',
        data:{ labels:themes, datasets:[app1,app2].map(app => ({
            label:app.replace('_',' '), data:themes.map(t=>getOverview(app).Theme_Counts[t]||0),
            backgroundColor:APP_COLORS[app]+'cc', borderRadius:4
        }))},
        options: barOptions()
    });
}

// ── Reviews Page ──────────────────────────────────────────────────────────────
function renderReviews() {
    const app  = document.getElementById('reviews-app-filter').value;
    const list = document.getElementById('reviews-list');
    let reviews = [];
    dashboardData.overview.forEach(item => {
        if (app !== 'All' && item.App !== app) return;
        const src = activeReviewTab === 'neg' ? item.Sample_Reviews_Neg : item.Sample_Reviews_Pos;
        src.forEach(r => reviews.push({ app: item.App, ...r }));
    });
    if (!reviews.length) { list.innerHTML = `<p style="color:var(--text3);font-size:0.85rem">No reviews found.</p>`; return; }
    list.innerHTML = reviews.map(r => `
        <div class="review-card">
            <div class="review-meta">
                <span class="stars">${'★'.repeat(r.star)}${'☆'.repeat(5-r.star)}</span>
                <span class="review-app-tag">${r.app.replace('_',' ')}</span>
            </div>
            <p class="review-text">${r.text}</p>
        </div>`).join('');
}

function handleSearch(e) {
    const q = e.target.value.trim().toLowerCase();
    if (!q) { renderReviews(); return; }
    const app = document.getElementById('reviews-app-filter').value;
    const results = [];
    dashboardData.overview.forEach(item => {
        if (app !== 'All' && item.App !== app) return;
        [...item.Sample_Reviews_Neg, ...item.Sample_Reviews_Pos].forEach(r => {
            if (r.text.toLowerCase().includes(q)) results.push({ app: item.App, ...r });
        });
    });
    const list = document.getElementById('reviews-list');
    if (!results.length) { list.innerHTML = `<p style="color:var(--text3);font-size:0.85rem">No reviews matching "${q}".</p>`; return; }
    list.innerHTML = results.map(r => {
        const hl = r.text.replace(new RegExp(q,'gi'), m => `<mark style="background:#dbeafe;color:#1d4ed8;border-radius:2px">${m}</mark>`);
        return `
        <div class="review-card">
            <div class="review-meta">
                <span class="stars">${'★'.repeat(r.star)}${'☆'.repeat(5-r.star)}</span>
                <span class="review-app-tag">${r.app.replace('_',' ')}</span>
            </div>
            <p class="review-text">${hl}</p>
        </div>`;
    }).join('');
}

// ── Shared Renderers ──────────────────────────────────────────────────────────
function renderBanner(context, app) {
    const el = document.getElementById(`${context}-banner`);
    const ov = dashboardData.overview;
    if (app === 'All') {
        const sorted = [...ov].sort((a,b)=>b.Avg_Star-a.Avg_Star);
        const best=sorted[0], worst=sorted[sorted.length-1];
        const highSent=[...ov].sort((a,b)=>b.Avg_Sentiment-a.Avg_Sentiment)[0];
        const mostPolar=[...ov].sort((a,b)=>b.Std_Dev-a.Std_Dev)[0];
        el.innerHTML=[
            {icon:'🏆',text:`<b>${best.App.replace('_',' ')}</b> highest rated — ${best.Avg_Star.toFixed(2)}★`},
            {icon:'📉',text:`<b>${worst.App.replace('_',' ')}</b> lowest rated — ${worst.Avg_Star.toFixed(2)}★`},
            {icon:'😊',text:`<b>${highSent.App.replace('_',' ')}</b> most positive sentiment (${highSent.Avg_Sentiment.toFixed(3)})`},
            {icon:'⚡',text:`<b>${mostPolar.App.replace('_',' ')}</b> most polarised (σ ${mostPolar.Std_Dev.toFixed(2)})`},
        ].map(c=>`<div class="insight-chip"><span class="chip-icon">${c.icon}</span><span>${c.text}</span></div>`).join('');
    } else {
        const item=getOverview(app);
        const starRank=[...ov].sort((a,b)=>b.Avg_Star-a.Avg_Star).findIndex(i=>i.App===app)+1;
        const topTheme=Object.entries(item.Theme_Counts).filter(([k])=>k!=='General').sort((a,b)=>b[1]-a[1])[0];
        const fivePct=((item.Rating_Distribution['5']/item.Total_Reviews)*100).toFixed(1);
        const onePct=((item.Rating_Distribution['1']/item.Total_Reviews)*100).toFixed(1);
        el.innerHTML=[
            {icon:'⭐',text:`Avg rating <b>${item.Avg_Star.toFixed(2)}</b> — ranked <b>#${starRank}</b> of 5`},
            {icon:'😊',text:`Sentiment score <b>${item.Avg_Sentiment.toFixed(3)}</b>`},
            {icon:'📊',text:`<b>${fivePct}%</b> five-star · <b>${onePct}%</b> one-star`},
            ...(topTheme?[{icon:'🔥',text:`Top pain point: <b>${topTheme[0]}</b>`}]:[]),
        ].map(c=>`<div class="insight-chip"><span class="chip-icon">${c.icon}</span><span>${c.text}</span></div>`).join('');
    }
}

function renderKPIBlock(containerId, app) {
    const container = document.getElementById(containerId);
    let total, avgStar, avgSent, stdDev;
    if (app==='All') {
        const ov=dashboardData.overview;
        total=ov.reduce((s,i)=>s+i.Total_Reviews,0);
        avgStar=ov.reduce((s,i)=>s+i.Avg_Star*i.Total_Reviews,0)/total;
        avgSent=ov.reduce((s,i)=>s+i.Avg_Sentiment*i.Total_Reviews,0)/total;
        stdDev=null;
    } else {
        const item=getOverview(app);
        total=item.Total_Reviews; avgStar=item.Avg_Star; avgSent=item.Avg_Sentiment; stdDev=item.Std_Dev;
    }
    const kpis=[
        {label:'Total Reviews',val:total.toLocaleString(),suffix:''},
        {label:'Avg Star Rating',val:avgStar.toFixed(2),suffix:'/ 5'},
        {label:'Avg Sentiment',val:avgSent.toFixed(3),suffix:''},
        ...(stdDev!==null?[{label:'Rating Std Dev',val:stdDev.toFixed(2),suffix:''}]:[])
    ];
    container.innerHTML=kpis.map(k=>`
        <div class="kpi-card">
            <div class="kpi-label">${k.label}</div>
            <div class="kpi-val">${k.val}<small>${k.suffix}</small></div>
        </div>`).join('');
}

function renderTimeSeriesChart(canvasId, app) {
    destroyChart(canvasId);
    const ts=dashboardData.time_series_daily;
    let labels, datasets=[];
    if (app==='All') {
        labels=ts[dashboardData.apps[0]].dates;
        dashboardData.apps.forEach(a=>{ datasets.push({label:a.replace('_',' '),data:ts[a].avg_sentiment,borderColor:APP_COLORS[a],backgroundColor:'transparent',tension:0.4,borderWidth:2,pointRadius:0}); });
    } else {
        labels=ts[app].dates;
        const color=APP_COLORS[app];
        datasets=[
            {label:'Sentiment',data:ts[app].avg_sentiment,borderColor:color,backgroundColor:color+'18',fill:true,tension:0.4,borderWidth:2.5,pointRadius:0},
            {label:'Avg Star (÷5)',data:ts[app].avg_star.map(v=>v/5),borderColor:'#f59f00',backgroundColor:'transparent',tension:0.4,borderWidth:1.5,borderDash:[4,4],pointRadius:0}
        ];
    }
    charts[canvasId]=new Chart(document.getElementById(canvasId).getContext('2d'),{type:'line',data:{labels,datasets},options:lineOptions()});
}

function renderBarChart(canvasId, app) {
    destroyChart(canvasId);
    const ov=dashboardData.overview;
    if(app==='All'){
        // Cross-product: one bar per product (meaningful comparison).
        charts[canvasId]=new Chart(document.getElementById(canvasId).getContext('2d'),{
            type:'bar',
            data:{labels:ov.map(i=>i.App.replace('_',' ')),datasets:[{label:'Avg Star',data:ov.map(i=>i.Avg_Star),backgroundColor:ov.map(i=>APP_COLORS[i.App]+'cc'),borderRadius:6,borderSkipped:false}]},
            options:{...barOptions(),scales:{x:{grid:{display:false}},y:{min:0,max:5,grid:{color:'rgba(0,0,0,0.04)'}}}}
        });
        return;
    }
    // Single product: a lone bar is meaningless, so compare THIS product against
    // the all-products average across three normalised metrics.
    const it=getOverview(app);
    const n=ov.length;
    const avgStar=ov.reduce((s,i)=>s+i.Avg_Star,0)/n;
    const avgSent=ov.reduce((s,i)=>s+i.Avg_Sentiment,0)/n;
    const avgStd =ov.reduce((s,i)=>s+i.Std_Dev,0)/n;
    // Normalise to 0-1 so they share an axis: star/5, sentiment shifted to 0-1, std/3.
    const norm=(v,kind)=> kind==='star'?v/5 : kind==='sent'?(v+1)/2 : v/3;
    const labels=['Avg Star','Sentiment','Polarisation'];
    const thisData=[norm(it.Avg_Star,'star'),norm(it.Avg_Sentiment,'sent'),norm(it.Std_Dev,'std')];
    const avgData =[norm(avgStar,'star'),norm(avgSent,'sent'),norm(avgStd,'std')];
    const color=APP_COLORS[app]||'#3b82f6';
    charts[canvasId]=new Chart(document.getElementById(canvasId).getContext('2d'),{
        type:'bar',
        data:{labels,datasets:[
            {label:app.replace('_',' '),data:thisData,backgroundColor:color+'cc',borderRadius:6,borderSkipped:false},
            {label:'All-product avg',data:avgData,backgroundColor:'#cbd5e1cc',borderRadius:6,borderSkipped:false}
        ]},
        options:{...barOptions(),plugins:{...barOptions().plugins,
            tooltip:{callbacks:{label:(ctx)=>{
                // Show the real (un-normalised) value in the tooltip.
                const i=ctx.dataIndex; const isThis=ctx.datasetIndex===0;
                const real=[ isThis?it.Avg_Star:avgStar, isThis?it.Avg_Sentiment:avgSent, isThis?it.Std_Dev:avgStd ][i];
                return `${ctx.dataset.label}: ${real.toFixed(2)}`;
            }}}},
            scales:{x:{grid:{display:false}},y:{min:0,max:1,ticks:{display:false},grid:{color:'rgba(0,0,0,0.04)'}}}}
    });
}

function renderDoughnutChart(canvasId, app) {
    destroyChart(canvasId);
    let totals={};
    if(app==='All'){
        // Cross-product view: full theme mix (General included, normal colour).
        dashboardData.overview.forEach(i=>Object.entries(i.Theme_Counts).forEach(([k,v])=>{totals[k]=(totals[k]||0)+v;}));
    } else {
        // Single product: themes from LOW-STAR reviews only (real complaints),
        // which shrinks the General bucket and surfaces actual pain points.
        const it=getOverview(app);
        totals = it.Theme_Counts_Neg || it.Theme_Counts;
    }
    const labels=Object.keys(totals);
    // Grey-out 'General' (uncategorised) so the eye goes to the specific themes,
    // without hiding it / distorting the real distribution.
    const themePalette={'General':'#d1d5db','Pricing/Subscription':'#10b981','Bugs/Performance':'#f59f00','Accuracy/Logic Issues':'#f43f5e'};
    const colors=labels.map((k,idx)=>themePalette[k]||THEME_COLORS[idx%THEME_COLORS.length]);
    charts[canvasId]=new Chart(document.getElementById(canvasId).getContext('2d'),{
        type:'doughnut',
        data:{labels,datasets:[{data:Object.values(totals),backgroundColor:colors,borderWidth:0,hoverOffset:6}]},
        options:{responsive:true,maintainAspectRatio:false,cutout:'68%',plugins:{legend:{position:'right',labels:{padding:14,usePointStyle:true,boxWidth:7}}}}
    });
}

function renderDistChart(canvasId, app) {
    destroyChart(canvasId);
    let dist={'1':0,'2':0,'3':0,'4':0,'5':0};
    if(app==='All'){dashboardData.overview.forEach(i=>{if(i.Rating_Distribution)Object.entries(i.Rating_Distribution).forEach(([k,v])=>{dist[k]=(dist[k]||0)+v;});});}
    else{const item=getOverview(app);if(item?.Rating_Distribution)dist=item.Rating_Distribution;}
    charts[canvasId]=new Chart(document.getElementById(canvasId).getContext('2d'),{
        type:'bar',
        data:{labels:['1★','2★','3★','4★','5★'],datasets:[{label:'Reviews',data:['1','2','3','4','5'].map(k=>dist[k]||0),backgroundColor:['#f43f5e','#f59f00','#94a3b8','#10b981','#3b82f6'],borderRadius:6,borderSkipped:false}]},
        options:{...barOptions(),plugins:{legend:{display:false}}}
    });
}

function renderPolarChart(canvasId) {
    destroyChart(canvasId);
    const items=[...dashboardData.overview].sort((a,b)=>b.Std_Dev-a.Std_Dev);
    charts[canvasId]=new Chart(document.getElementById(canvasId).getContext('2d'),{
        type:'bar',
        data:{labels:items.map(i=>i.App.replace('_',' ')),datasets:[{label:'Std Dev',data:items.map(i=>i.Std_Dev),backgroundColor:items.map(i=>APP_COLORS[i.App]+'cc'),borderRadius:6,borderSkipped:false}]},
        options:{indexAxis:'y',...barOptions(),scales:{x:{min:0,max:2.5,grid:{color:'rgba(0,0,0,0.04)'}},y:{grid:{display:false}}}}
    });
}

function renderWordCloud(containerId, app, mode) {
    const container=document.getElementById(containerId);
    let wordMap={};
    if(app==='All'){dashboardData.overview.forEach(item=>{const src=mode==='pos'?item.Keywords_Positive:item.Keywords_Negative;Object.entries(src).forEach(([w,c])=>{wordMap[w]=(wordMap[w]||0)+c;});});}
    else{const item=getOverview(app);wordMap=mode==='pos'?item.Keywords_Positive:item.Keywords_Negative;}
    const sorted=Object.entries(wordMap).sort((a,b)=>b[1]-a[1]).slice(0,40);
    const maxC=sorted[0][1],minC=sorted[sorted.length-1][1];
    const posColors=['#2563eb','#0891b2','#7c3aed','#059669','#0284c7','#6d28d9'];
    const negColors=['#dc2626','#d97706','#ea580c','#db2777','#b91c1c','#c2410c'];
    const palette=mode==='pos'?posColors:negColors;
    const shuffled=[...sorted].sort(()=>Math.random()-0.5);
    const scaleSize=c=>maxC===minC?1.4:0.8+((c-minC)/(maxC-minC))*1.6;
    container.innerHTML=shuffled.map(([word,count],i)=>{
        const size=scaleSize(count),color=palette[i%palette.length],opacity=0.55+0.45*((count-minC)/(maxC-minC||1));
        return `<span class="wc-word" style="font-size:${size}rem;color:${color};opacity:${opacity}" title="distinctiveness ${(+count).toFixed(1)}">${word}</span>`;
    }).join('');
}

// ── Chart Options ─────────────────────────────────────────────────────────────
function lineOptions() {
    return {
        responsive:true,maintainAspectRatio:false,
        interaction:{mode:'index',intersect:false},
        plugins:{legend:{position:'top',labels:{usePointStyle:true,boxWidth:6,padding:16}},tooltip:{backgroundColor:'#1f2937',padding:10,cornerRadius:8}},
        scales:{x:{grid:{color:'rgba(0,0,0,0.04)'},ticks:{maxTicksLimit:8}},y:{grid:{color:'rgba(0,0,0,0.04)'}}}
    };
}

function barOptions() {
    return {
        responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:true,position:'top',labels:{usePointStyle:true,boxWidth:6,padding:12}},tooltip:{backgroundColor:'#1f2937',padding:10,cornerRadius:8}},
        scales:{x:{grid:{display:false}},y:{grid:{color:'rgba(0,0,0,0.04)'}}}
    };
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function getOverview(app) { return dashboardData.overview.find(i=>i.App===app); }
function destroyChart(id) { if(charts[id]){ charts[id].destroy(); delete charts[id]; } }

init();
