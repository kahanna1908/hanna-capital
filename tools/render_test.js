// Runs each built page's JavaScript in a headless DOM and fails on any script error.
// Used only by the "Code test" workflow.
const fs = require("fs");
const { JSDOM, VirtualConsole } = require("jsdom");

let failed = false;
for (const file of ["site/index.html", "site/v3/index.html"]) {
  const errors = [];
  const vc = new VirtualConsole();
  vc.on("jsdomError", e => errors.push(String(e.detail || e.message || e)));
  const html = fs.readFileSync(file, "utf8").replace(/<script src=[^>]*><\/script>/g, "<script>window.Chart=function(){return{destroy(){}}};window.matchMedia=()=>({matches:false,addEventListener(){}});</script>");
  const dom = new JSDOM(html, { runScripts: "dangerously", virtualConsole: vc, pretendToBeVisual: true });
  const doc = dom.window.document;
  const cards = doc.querySelectorAll("#journalBox details").length;
  const rows = doc.querySelectorAll("#journalBox td.why").length;
  console.log(`${file}: ${cards} journal cards, ${rows} trade reasons, status "${doc.getElementById("status").textContent.trim()}"`);
  if (errors.length || !cards) { failed = true; console.error(errors.join("\n") || "no journal cards rendered"); }
}
process.exit(failed ? 1 : 0);
