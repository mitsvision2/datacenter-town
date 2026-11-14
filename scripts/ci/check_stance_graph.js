// Exercise the actual graph functions without browser or API dependencies.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync("environment/frontend_server/templates/dashboard/dashboard.html", "utf8");
const script = html.slice(html.indexOf("const STANCE_COLORS"), html.indexOf("let logTimer"));
const elements = new Map();
const element = (id) => {
  if (!elements.has(id)) elements.set(id, {id, clientWidth: 800, innerHTML: "",
    textContent: "", hidden: false, addEventListener() {},
    querySelector: () => ({setAttribute() {}})});
  return elements.get(id);
};
const drawn = {};
const context = vm.createContext({
  data: null, view: null, selected: null, drawn, $: element,
  document: {getElementById: () => null, addEventListener() {}},
  esc: (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])),
  paint: (el, value) => { el.innerHTML = value; drawn[el.id] = value; },
  ResizeObserver: class { observe() {} },
  parseGameTime: () => new Date("2023-02-13T00:00:00"),
  spanLabel: () => "1h", showConvo() {}, selectAgent() {},
  // Defined outside the slice under test.
  focus: {whisper: null, step: null}, onFocus() {}, setFocus() {}, chartTipMove() {}, trailSent: () => [],
  sprite: (name) => `/static/${name}.png`, emptyMsg: (t) => t, openConvo: null,
});
vm.runInContext(script, context);
const run = (code) => vm.runInContext(code, context);
// A saved run with no readings doesn't promise future ones.
context.data = {sim: {}, opinions: [], settings: {opinion_steps: 360}};
context.view = "mock-ui";
run("renderStance()");
assert.match(element("stance").innerHTML, /No stance readings in this run\./);
context.view = null;
context.data = null;
assert.equal(run('stanceY({score:0,scale:100,scoring_version:"rubric_v1"})'), 250);
assert.equal(run('stanceY({score:100,scale:100,scoring_version:"rubric_v1"})'), 12);
assert.equal(run('stanceY({score:50,scale:100,scoring_version:"rubric_v1"})'), 131);
assert.equal(run('stanceY({score:1,scale:100})'), 250);
assert.equal(run('stanceY({score:10,scale:10})'), 12);
assert.equal(run('stanceY({score:null,scale:100})'), null);
const nodes = ["Maya", "Rachel", "Elena"].map((name) => ({name, color: "#9299A4", score: null}));
context.data = {sim: {persona_order: nodes.map((n) => n.name)}, network: {nodes, edges: []}};
run("renderNetwork()");
// Stance is the number beside each name, not a colored dot.
assert.equal((element("social-network").innerHTML.match(/<tspan class="social-score">–<\/tspan>/g) || []).length, 3);
const originalPositions = run("JSON.stringify(socialPositions(data.network.nodes,800))");
context.data.network.nodes.reverse();
context.data.network.edges = [{source: "Maya", target: "Rachel", count: 301, time: "now"}];
run("renderNetwork()");
assert.equal(run("JSON.stringify(socialPositions(data.network.nodes,800))"), originalPositions);
// Both unrated, so the line is dashed "unknown" rather than across or same side.
assert.equal((element("social-network").innerHTML.match(/class="social-edge unknown"/g) || []).length, 1);
assert.match(element("social-network").innerHTML, /301 conversations/);
assert(run("socialEdgeWidth(2) > socialEdgeWidth(1)"));
assert(run("socialEdgeWidth(1000000) <= 8"));
// Placed by stance, against on the left; a pair on opposite sides of the midpoint is "across", one side "same".
const rated = [["Maya", 10], ["Rachel", 90], ["Elena", 30]].map(([name, score]) => ({name, score, scale: 100, scoring_version: "rubric_v1"}));
context.data.network = {nodes: rated, edges: [{source: "Maya", target: "Rachel", count: 2}, {source: "Elena", target: "Maya", count: 1}]};
run("renderNetwork()");
const at = Object.fromEntries(JSON.parse(run("JSON.stringify(socialPositions(data.network.nodes,800,300))")).map((p) => [p.name, p.x]));
assert(at.Maya < at.Elena && at.Elena < at.Rachel);
assert.match(element("social-network").innerHTML, /class="social-edge across"[^>]*data-a="Maya" data-b="Rachel"/);
assert.match(element("social-network").innerHTML, /class="social-edge same"[^>]*data-a="Elena" data-b="Maya"/);
context.data.network = {nodes, edges: [{source: "Maya", target: "Rachel", count: 301, time: "now"}]};
context.data.network.nodes[0].name = '<img src=x onerror="alert(1)">';
run("renderNetwork()");
assert(!element("social-network").innerHTML.includes("<img"));
context.data.opinions = [
  {name: "Maya", score: 1, step: 1, scale: 100},
  {name: "Maya", score: 0, step: 2, scale: 100, scoring_version: "rubric_v1"},
  {name: "Maya", score: null, step: 3, scale: 100, scoring_version: "rubric_v1"},
  {name: "Maya", score: 100, step: 4, scale: 100, scoring_version: "rubric_v1"},
];
run("renderStance()");
assert.match(element("stance").innerHTML, /opposed<\/tspan> 0/);
assert.match(element("stance-note").textContent, /not directly comparable/);
const path = element("stance").innerHTML.match(/class="line[^"]*"[^>]*d="([^"]+)"/)[1];
assert.equal((path.match(/M/g) || []).length, 3); // Break at method change and null.
assert.equal((path.match(/L/g) || []).length, 0);
// Gaps are counted by why each reading has no score, under the probe's own reason names.
context.data.opinions = [
  {name: "Maya", score: 40, step: 1, scale: 100, scoring_version: "rubric_v1"},
  {name: "Maya", score: null, step: 2, scale: 100, scoring_version: "rubric_v1", withheld: "asleep_night"},
  {name: "Maya", score: null, step: 3, scale: 100, scoring_version: "rubric_v1", withheld: "asleep_daytime"},
  {name: "Maya", score: null, step: 4, scale: 100, scoring_version: "rubric_v1", withheld: "no_relevant_memory", relevance: {best: 0.39}},
  {name: "Maya", score: 60, step: 5, scale: 100, scoring_version: "rubric_v1"},
];
run("renderStance()");
assert.match(element("stance-note").textContent, /3 without a score \(2 asleep, 1 nothing relevant\)/);
assert.equal(run("stanceGaps.find((g) => g.kind !== 'solid').skipped.length"), 3);
assert.equal(run("stanceWhy(data.opinions[3])"), "Nothing in memory close enough to the datacenter (closest 0.39, needs 0.45)");
assert.equal(run("stanceWhy({withheld: 'asleep_daytime'})"), "Asleep during the day");
// Sides are taken as the pair stood when they last talked: both against then, though one is for now.
context.data.opinions = [
  {name: "Maya", step: 10, score: 20, scale: 100, scoring_version: "rubric_v1"}, {name: "Rachel", step: 10, score: 30, scale: 100, scoring_version: "rubric_v1"},
  {name: "Maya", step: 90, score: 80, scale: 100, scoring_version: "rubric_v1"}];
context.data.conversations = [{step: 50, speakers: ["Maya", "Rachel"], time: "t"}];
context.data.network = {nodes: [{name: "Maya", score: 80, scale: 100, scoring_version: "rubric_v1"}, {name: "Rachel", score: 30, scale: 100, scoring_version: "rubric_v1"}],
  edges: [{source: "Maya", target: "Rachel", count: 1}]};
run("renderNetwork()");
assert.match(element("social-network").innerHTML, /class="social-edge same"[^>]*data-a="Maya" data-b="Rachel"/);
console.log("Stance plotting, historical versions, gap reasons, network rendering, layout, escaping: passed");
