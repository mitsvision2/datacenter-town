// Exercise the whisper pane's logic without a browser or a simulation.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync("environment/frontend_server/templates/dashboard/dashboard.html", "utf8");
const script = html.slice(html.indexOf("/* ---------------- whispers ---------------- */"),
                          html.indexOf("/* ---------------- stance graph ---------------- */"));
// Defined elsewhere on the page and used as they are.
const convoKeySource = /function convoKey\(c\) \{[\s\S]*?\n\}/.exec(html)[0];
const elements = new Map();
const element = (id) => {
  if (!elements.has(id)) elements.set(id, {id, innerHTML: "", textContent: "", value: "", hidden: false,
    clientWidth: 800, style: {}, addEventListener() {}, querySelector: () => null,
    getBoundingClientRect: () => ({left: 0, top: 0, width: 800})});
  return elements.get(id);
};
const context = vm.createContext({
  data: null, view: null, $: element,
  esc: (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c])),
  paint: (el, value) => { el.innerHTML = value; },
  sprite: (name) => `/static/${name}.png`,
  inheritedToggle: () => "", showInherited: false, Set, Map, Date, isNaN, String,
  drawn: {}, showConvo() {}, ResizeObserver: class { observe() {} },
  stanceTickFormat: () => (d) => `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`,
  parseGameTime: (s) => {
    const m = /^(\w+) (\d+), (\d+), (\d+):(\d+)/.exec(s || "");
    return m ? new Date(`${m[1]} ${m[2]}, ${m[3]} ${m[4]}:${m[5]}:00`) : null;
  },
  spanLabel: (steps, sps) => {
    const secs = steps * (sps || 10);
    if (secs < 60) return `${secs}s`;
    const mins = Math.round(secs / 60);
    return mins >= 60 ? `${Math.floor(mins / 60)}h ${mins % 60}m` : `${mins}m`;
  },
});
vm.runInContext(convoKeySource, context);
vm.runInContext(script, context);
const run = (code) => vm.runInContext(code, context);
const cast = ["Maya Okonkwo", "Luis Hernandez", "Denise Brooks", "Tom Whitaker"];
const state = (status, extra) => {
  context.data = {status, sim: {persona_order: cast, curr_time: "February 13, 2023, 12:00:00",
    sec_per_step: 10, run_left: 0, ...extra}};
};
const hint = (at) => run(`whisperHint(${JSON.stringify(at)})`);

// What the send button promises matches what the drafts ask for.
const label = (...ats) => run(`whisperGoLabel(${JSON.stringify(ats.map((at) => ({at})))})`);
assert.equal(label(null), "Send whisper");
assert.equal(label(null, null), "Send 2 whispers");
assert.equal(label("2023-02-13T14:00"), "Schedule whisper");
assert.equal(label("2023-02-13T14:00", "2023-02-13T15:00"), "Schedule 2 whispers");
assert.equal(label(null, "2023-02-13T14:00"), "Send and schedule 2 whispers");

// The hint says when a draft will really go out.
state("idle");
assert.equal(hint(null), "Goes out straight away.");
assert.match(hint("2023-02-13T14:30"), /2h 30m of game time from now\. It waits for a run/);
assert.match(hint("2023-02-13T11:00"), /That time has passed/);
assert.equal(hint(""), "Pick a date and time.");
state("running", {run_left: 360});
assert.equal(hint(null), "Goes out at the next step.");
assert.doesNotMatch(hint("2023-02-13T12:30"), /waits for the next/);
assert.match(hint("2023-02-13T14:00"), /This run ends at .* 13:00, so it waits for the next one/);

// "Everyone" only when it really is everyone.
state("idle");
assert.equal(run(`whisperAudience(${JSON.stringify(cast)})`), "Everyone");
assert.equal(run(`whisperAudience(${JSON.stringify(cast.slice(0, 3))})`), "Maya, Luis, Denise");

// One whisper to several people reads as one row; a repeat at another step doesn't merge.
const row = (agent, step, text) => ({event_type: "midrun_whisper", agent, step, text, time: "t"});
const groups = run(`groupWhispers(${JSON.stringify([row("Maya", 5, "a"), row("Luis", 5, "a"), row("Tom", 5, "b"), row("Maya", 9, "a")])})`);
assert.equal(groups.length, 3);
assert.deepEqual([...groups[0].agents], ["Maya", "Luis"]);

// Rows: what's offered depends on the status, and nothing is unescaped.
const whisper = (extra) => ({id: "w1", text: "<b>hi</b>", targets: cast.slice(0, 2), at: null,
  sent: [], failed: {}, left: cast.slice(0, 2), status: "scheduled", ...extra});
const rendered = (w) => run(`whisperRow(${JSON.stringify(w)})`);
state("idle");
assert(!rendered(whisper()).includes("<b>hi</b>"));
// A "now" whisper is already on its way: nothing to edit, only stop.
assert.match(rendered(whisper()), /Sending/);
assert.doesNotMatch(rendered(whisper()), /data-w-action="edit"/);
const later = rendered(whisper({at: "February 13, 2023, 14:00:00"}));
assert.match(later, /in 2h 0m/);
assert.match(later, /data-w-action="edit"/);
const sending = rendered(whisper({status: "sending", sent: [cast[0]]}));
assert.match(sending, /1 of 2 done/);
assert.doesNotMatch(sending, /data-w-action="edit"/);
const failed = rendered(whisper({status: "failed", sent: [cast[0]], failed: {[cast[1]]: "<boom>"}}));
assert.match(failed, /reached 1 of 2/);
assert.match(failed, /Didn't reach Luis: &lt;boom&gt;/);
assert.match(failed, /data-w-action="retry"/);
context.view = "saved-run";
assert.doesNotMatch(rendered(whisper()), /data-w-action/);
context.view = null;

// Past the spending cap the page says why nothing is going out.
state("idle", {settings: {budget_usd: 1}, run_cost: 2});
assert.match(rendered(whisper()), /spending cap reached/);
assert.match(hint(null), /spending cap/);
state("idle", {settings: {budget_usd: 5}, run_cost: 2});
assert.doesNotMatch(rendered(whisper()), /spending cap/);
assert.equal(hint(null), "Goes out straight away.");
state("idle", {settings: {budget_usd: null}, run_cost: 2});
assert.doesNotMatch(rendered(whisper()), /spending cap/);

// The pane puts waiting whispers first and hides cancelled ones.
state("idle");
context.data.whispers = [
  whisper({id: "late", at: "February 13, 2023, 18:00:00"}),
  whisper({id: "soon", at: "February 13, 2023, 13:00:00"}),
  whisper({id: "gone", status: "cancelled", left: []}),
  whisper({id: "done", status: "sent", left: []}),
];
context.data.events = [];
run("renderEvents()");
const pane = element("p-events").innerHTML;
assert(pane.indexOf('data-w-id="soon"') < pane.indexOf('data-w-id="late"'));
assert(!pane.includes('data-w-id="gone"') && !pane.includes('data-w-id="done"'));
assert.equal(element("n-events").textContent, "2 scheduled");
assert.match(pane, /data-w-new/);
assert.match(pane, /Game time only moves during a run/);

// Sent whispers read newest first, with names in the order they were sent.
context.data.whispers = [];
context.data.events = [row("Maya Okonkwo", 5, "first"), row("Luis Hernandez", 5, "first"), row("Tom Whitaker", 9, "second")];
run("renderEvents()");
const sent = element("p-events").innerHTML;
assert(sent.indexOf("second") < sent.indexOf("first"));
assert.match(sent, /Maya, Luis/);
assert.doesNotMatch(sent, /Game time only moves/);

// No run loaded: says what to do instead of offering a button that can't work.
context.data = {status: "stopped", sim: null};
run("renderEvents()");
assert.match(element("p-events").innerHTML, /Start one first/);
assert.doesNotMatch(element("p-events").innerHTML, /data-w-new/);

// ---- the whisper chart
const told = (extra) => ({id: "w", text: "<b>The vote moved</b>", targets: cast.slice(0, 2),
  received: {[cast[0]]: {step: 100, time: "February 13, 2023, 12:00:00"},
             [cast[1]]: {step: 100, time: "February 13, 2023, 12:00:00"}},
  sent: cast.slice(0, 2), failed: {}, left: [], status: "sent", at: null, ...extra});
const speakers = [cast[0], cast[2]];
const mentionRow = (step, ppl, id, extra) => ({step, time: "February 13, 2023, 12:30:00", speakers: ppl,
  checked: [id], failed: [], mentions: [{whisper_id: id, speaker: ppl[0], quote: "the <i>vote</i> is Friday",
    how: "Maya raises it and Denise agrees.", new_hearers: [ppl[1]], ...extra}]});
const quietRow = (step, ppl, id) => ({step, time: "t", speakers: ppl, checked: [id], failed: [], mentions: []});
const story = (w, mentions, conversations) => run(
  `JSON.parse(JSON.stringify(whisperStory(${JSON.stringify(w)}, ${JSON.stringify(mentions)}, ${JSON.stringify(conversations)})))`);
const asJson = (x) => JSON.parse(JSON.stringify(x));

// Told directly, and heard second-hand, and passed along again.
let s = story(told(), [mentionRow(200, speakers, "w"), mentionRow(300, [cast[2], cast[3]], "w")], []);
assert.deepEqual(asJson(s.told), cast.slice(0, 2));
assert.deepEqual(asJson(s.passedOn), [cast[2], cast[3]]);
assert.equal(s.heard[cast[2]].from, cast[0]);
assert.equal(s.heard[cast[2]].step, 200);
assert.equal(s.ups.length, 2);
assert.equal(run(`whisperSummary(${JSON.stringify(s)})`),
  "Told to 2 people. 2 more heard it in conversation. It came up in 2 of the 2 conversations they've had since.");
// One told directly keeps that, even if a conversation also carried it later.
s = story(told(), [mentionRow(200, [cast[0], cast[1]], "w", {new_hearers: []})], []);
assert.equal(s.heard[cast[1]].told, true);
assert.deepEqual(asJson(s.passedOn), []);
// Another whisper's mention is someone else's story.
s = story(told(), [mentionRow(200, speakers, "other")], []);
assert.equal(s.ups.length, 0);
assert.equal(run(`whisperSummary(${JSON.stringify(s)})`), "Told to 2 people. They haven't had a conversation since.");

// A grey conversation only claims what was actually established.
const talk = (step, ppl) => ({step, time: "t", speakers: ppl, utterances: []});
const said = (w, mentions, c) => story(w, mentions, [c]).talks[0].said;
assert.equal(said(told(), [quietRow(200, speakers, "w")], talk(200, speakers)), "It didn't come up.");
assert.equal(said(told(), [], talk(50, speakers)), "Neither of them had heard it yet.");
assert.equal(said(told(), [], talk(200, [cast[2], cast[3]])), "Neither of them had heard it yet.");
assert.equal(said(told(), [], talk(200, speakers)), "This one wasn't checked.");
assert.equal(said(told(), [{step: 200, time: "t", speakers, checked: [], failed: ["w"], mentions: []}], talk(200, speakers)),
  "This one wasn't checked.");
// The conversation a whisper came up in isn't also drawn grey.
assert.equal(story(told(), [mentionRow(200, speakers, "w")], [talk(200, speakers)]).talks.length, 0);

// Words in time order, with one row for everyone told at once.
const ev = asJson(run(`whisperEvents(whisperStory(${JSON.stringify(told())}, ${JSON.stringify([mentionRow(200, speakers, "w")])}, []))`));
assert.deepEqual(ev.map((e) => e.kind), ["told", "up"]);
assert.deepEqual(ev[0].names, cast.slice(0, 2));

// The whole panel, with hostile text in every field.
state("idle", {step: 400, roster: []});
context.data.whispers = [told(), told({id: "scheduled-only", received: {}, sent: [], status: "scheduled", left: cast})];
context.data.mentions = [mentionRow(200, speakers, "w")];
context.data.conversations = [talk(200, speakers), talk(150, [cast[1], cast[3]])];
run("renderTrail()");
const chart = element("trail-chart").innerHTML;
assert.match(chart, /<svg/);
assert.equal((chart.match(/class="trail-lane"/g) || []).length, 4);
assert.equal((chart.match(/class="trail-knows"/g) || []).length, 3); // Told two, one second-hand.
assert.equal((chart.match(/trail-link up/g) || []).length, 1);
assert.equal((chart.match(/class="trail-link"/g) || []).length, 1);
assert.doesNotMatch(chart, /<b>|<i>/);
const words = element("trail-story").innerHTML;
assert.doesNotMatch(words, /<b>The vote|<i>vote/);
assert.match(words, /&lt;i&gt;vote/);
assert.match(words, /data-trail-convo/);
assert.match(words, /Denise hadn't heard it before\./);
// Times come from the rows themselves, to the minute they happened.
assert.match(words, /Mon 12:00[\s\S]*Mon 12:30/);
assert.match(element("trail-summary").textContent, /Told to 2 people\. 1 more heard it/);
// A scheduled whisper nobody has heard isn't offered yet.
assert.doesNotMatch(element("trail-select").innerHTML, /scheduled-only/);
// Tooltips say what hover promised, and escape it.
const pts = asJson(run("trailPts"));
const tip = (kind) => run(`trailTip(trailPts.find((p) => p.kind === ${JSON.stringify(kind)}))`);
assert(pts.some((p) => p.kind === "told") && pts.some((p) => p.kind === "up") && pts.some((p) => p.kind === "talk"));
assert.match(tip("told"), /heard this from you/);
assert.match(tip("told"), /&lt;b&gt;The vote moved/);
assert.match(tip("up"), /&lt;i&gt;vote/);
assert.match(tip("up"), /Maya raises it/);
assert.match(tip("talk"), /Luis and Tom talked/);
assert.match(run(`trailText(trailPts.find((p) => p.kind === "told"))`), /heard this from you/);

// Other whispers stay on the chart in grey, and clicking one follows it.
context.data.whispers = [told(), told({id: "second", text: "A second one", received: {[cast[3]]: {step: 350, time: "February 13, 2023, 13:00:00"}}})];
run("trailWhisper = 'w'; renderTrail()");
assert.match(element("trail-chart").innerHTML, /class="trail-other"/);
assert.match(run(`trailTip(trailPts.find((p) => p.kind === "other"))`), /A second one/);
run(`trailAct(trailPts.find((p) => p.kind === "other"))`);
assert.equal(run("trailWhisper"), "second");
assert.match(element("trail-summary").textContent, /Told to 1 person/);
// The axis doesn't move when another whisper is picked.
const first = /viewBox="[^"]+"/.exec(element("trail-chart").innerHTML)[0];
const lanes = /x1="(\d+)" y1="\d+" x2="(\d+)"/.exec(element("trail-chart").innerHTML).slice(1);
run("trailWhisper = 'w'; renderTrail()");
assert.equal(/viewBox="[^"]+"/.exec(element("trail-chart").innerHTML)[0], first);
assert.deepEqual(/x1="(\d+)" y1="\d+" x2="(\d+)"/.exec(element("trail-chart").innerHTML).slice(1), lanes);

// A run in progress mustn't redraw the chart at every step, or a tooltip can't be
// read while the run is going. The axis moves in jumps, and always covers now.
const end = (step) => run(`trailAxisEnd(1000, ${step}, 10)`);
assert.equal(end(1000), 1360);
assert.equal(end(1300), 1360);
for (const step of [1361, 1400, 5000, 50000]) assert(end(step) >= step, `axis must reach step ${step}`);
assert.equal(end(5001), end(5002));
const distinct = new Set(Array.from({length: 1000}, (_, i) => end(5000 + i)));
assert(distinct.size <= 3, `the axis moved ${distinct.size} times in 1000 steps`);
assert(run("trailAxisEnd(0, 86400, 10)") < 86400 * 1.3, "the axis shouldn't run far past now");

// Ticks land on round clock times, whatever time the axis starts.
const ticks = (from, steps) => asJson(run(`(() => {
  const start = new Date("2023-02-13T${from}");
  return trailTicks(0, ${steps}, 10, (s) => new Date(start.getTime() + s * 10000))
    .map((s) => new Date(start.getTime() + s * 10000).toTimeString().slice(0, 5));
})()`));
assert.deepEqual(ticks("09:00:00", 1080), ["09:00", "09:30", "10:00", "10:30", "11:00", "11:30", "12:00"]);
assert.deepEqual(ticks("09:00:00", 2160), ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00"]);
assert.deepEqual(ticks("09:13:20", 360), ["09:20", "09:30", "09:40", "09:50", "10:00", "10:10"]);
assert.equal(ticks("00:00:00", 8640).length, 5);
assert.equal(run("trailTicks(0, 100, 10, () => null).length"), 0);

// Empty states say what to do.
state("idle");
context.data.whispers = [];
run("renderTrail()");
assert.match(element("trail-chart").innerHTML, /Once a whisper has gone out/);
assert.equal(element("trail-select").hidden, true);
context.data = {status: "stopped", sim: null};
run("renderTrail()");
assert.match(element("trail-chart").innerHTML, /Start a run/);

console.log("Whisper labels, hints, grouping, row actions, ordering, chart, tooltips, escaping: passed");
