let activityChart, riskChart;
const $ = (id) => document.getElementById(id);
const filterIds = ["q","direction","status","risk","start","end"];
let debounceTimer;

function params() {
  const p = new URLSearchParams();
  filterIds.forEach(id => { if ($(id).value && $(id).value !== "All") p.set(id, $(id).value); });
  return p;
}
function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
function pill(value, kind) {
  const cls = String(value || "").toLowerCase().replace(/[^a-z]/g,"");
  return `<span class="pill ${kind || cls}">${esc(value || "Unknown")}</span>`;
}
function renderRows(rows) {
  const tbody = $("emailRows");
  if (!rows.length) {
    tbody.innerHTML = '<tr><td colspan="7" class="empty">No records match these filters.</td></tr>';
    return;
  }
  tbody.innerHTML = rows.map(r => `<tr>
    <td>${esc(r.Timestamp)}</td>
    <td><div class="email">${esc(r.Sender)}</div><div class="muted">${esc(r.SenderDomain)}</div></td>
    <td>${esc(r.Recipient)}</td>
    <td class="subject" title="${esc(r.Subject)}">${esc(r.Subject)}</td>
    <td>${pill(r.Direction, r.Direction.toLowerCase())}</td>
    <td>${pill(r.Status, r.Status.toLowerCase())}</td>
    <td title="${esc(r.RiskReasons)}">${pill(r.RiskLevel, r.RiskLevel.toLowerCase())}</td>
  </tr>`).join("");
}
function renderSecurity(rows) {
  const flagged = rows.filter(r => r.RiskLevel === "High" || r.RiskLevel === "Review").slice(0,6);
  $("securityList").innerHTML = flagged.length ? flagged.map(r => `
    <div class="security-item"><i class="security-dot ${r.RiskLevel === "High" ? "high" : ""}"></i>
      <div><strong>${esc(r.Subject || "(no subject)")}</strong><p>${esc(r.RiskReasons)}</p>
      <small>${esc(r.Sender)} → ${esc(r.Recipient)} · ${esc(r.Timestamp)} · Risk score ${esc(r.RiskScore)}</small></div>
    </div>`).join("") : '<div class="empty">No flagged messages in the current filtered view.</div>';
}
function renderCharts(data) {
  const labels = data.daily.map(x => x.day);
  if (activityChart) activityChart.destroy();
  activityChart = new Chart($("activityChart"), {
    type: "line",
    data: {labels, datasets:[
      {label:"Sent", data:data.daily.map(x=>x.sent), borderColor:"#4e7cf6", backgroundColor:"#4e7cf61b", fill:true, tension:.35, pointRadius:2},
      {label:"Received", data:data.daily.map(x=>x.received), borderColor:"#8975e8", backgroundColor:"#8975e81b", fill:true, tension:.35, pointRadius:2}
    ]},
    options:{responsive:true, maintainAspectRatio:false, interaction:{mode:"index",intersect:false},
      plugins:{legend:{position:"bottom",labels:{usePointStyle:true,boxWidth:7,padding:18,font:{size:10}}}},
      scales:{x:{grid:{display:false},ticks:{font:{size:9},maxRotation:0}},y:{beginAtZero:true,grid:{color:"#eef1f6"},ticks:{precision:0,font:{size:9}}}}}
  });
  const riskLabels = ["Low","Review","High"];
  const riskValues = riskLabels.map(k=>data.risk[k] || 0);
  if (riskChart) riskChart.destroy();
  riskChart = new Chart($("riskChart"), {
    type:"doughnut",
    data:{labels:riskLabels,datasets:[{data:riskValues,backgroundColor:["#54a78d","#e0b052","#d66a72"],borderWidth:0,hoverOffset:4}]},
    options:{responsive:true,maintainAspectRatio:false,cutout:"72%",plugins:{legend:{display:false}}}
  });
  $("riskLegend").innerHTML = riskLabels.map((label,i)=>`<span><i style="background:${["#54a78d","#e0b052","#d66a72"][i]}"></i>${label} (${riskValues[i]})</span>`).join("");
}
async function refresh() {
  const response = await fetch("/api/emails?" + params().toString());
  const data = await response.json();
  $("total").textContent = data.summary.total;
  $("sent").textContent = data.summary.sent;
  $("received").textContent = data.summary.received;
  $("flagged").textContent = data.summary.flagged;
  $("high").textContent = data.summary.high;
  $("recordCount").textContent = `${data.rows.length} records`;
  $("tableFoot").textContent = `Showing ${data.rows.length} matching records`;
  renderRows(data.rows);
  renderSecurity(data.rows);
  renderCharts(data);
  const pdf = document.querySelector('a[href^="/report.pdf"]');
  pdf.href = "/report.pdf?" + params().toString();
}
filterIds.forEach(id => $(id).addEventListener("input", () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => refresh().catch(console.error), 180);
}));
$("clearFilters").addEventListener("click", () => {
  filterIds.forEach(id => $(id).value = "");
  $("direction").value = "All"; $("status").value = "All"; $("risk").value = "All";
  refresh().catch(console.error);
});
refresh().catch(err => { $("emailRows").innerHTML = '<tr><td colspan="7" class="empty">Could not load records. Check that the Flask server is running.</td></tr>'; console.error(err); });
