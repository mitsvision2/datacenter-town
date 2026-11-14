// Exercise the whisper pane's logic without a browser or a simulation.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

const html = fs.readFileSync("environment/frontend_server/templates/dashboard/dashboard.html", "utf8");
const script = html.slice(html.indexOf("/* ---------------- whispers ---------------- */"),
                          html.indexOf("/* ---------------- stance graph ---------------- */"));
// Defined elsewhere on the page and used as they are.
const convoKeySource = /function convoKey\(c\) \{[\s\S]*?\n\}/.exec(html)[0];
const timeAxisSource = /function stanceTimeAxis\([\s\S]*?\n\}/.exec(html)[0];
const netSpriteSource = /const netSprite = [^\n]*/.exec(html)[0];
const tipTableSource = /function tipTable\([\s\S]*?\n\}/.exec(html)[0];
const tipNameSource = /const tipName = [^\n]*/.exec(html)[0];
const netDaySource = /const netDay = [^\n]*/.exec(html)[0];
const nightSource = /const NIGHT_FROM = [^\n]*/.exec(html)[0];
const stanceChangeSource = /function stanceChangeHtml\([\s\S]*?\n\}/.exec(html)[0];
const stanceScoreSource = /const STANCE_OLD_SCALE = [^\n]*\n[\s\S]*?function stanceScore100\([\s\S]*?\n\}/.exec(html)[0];
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
  agentColor: () => "#2f7d52",
  showInherited: false, Set, Map, Date, isNaN, String, refl: null, mapLink: () => "",
  drawn: {}, showConvo() {}, selectAgent() {}, chartTipMove() {}, ResizeObserver: class { observe() {} },
  focus: {whisper: null, step: null}, onFocus() {},
  setFocus(patch) { Object.assign(context.focus, patch); },
  document: {addEventListener() {}, querySelector: () => null},
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
vm.runInContext(timeAxisSource, context);
vm.runInContext(netSpriteSource, context);
vm.runInContext(tipTableSource, context);
vm.runInContext(tipNameSource, context);
vm.runInContext(netDaySource, context);
vm.runInContext(nightSource, context);
vm.runInContext(stanceChangeSource, context);
vm.runInContext(stanceScoreSource, context);
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

// "All agents" only when it really is everyone.
state("idle");
assert.equal(run(`whisperAudience(${JSON.stringify(cast)})`), "All agents");
assert.equal(run(`whisperAudience(${JSON.stringify(cast.slice(0, 3))})`), "Maya, Luis, Denise");

// One whisper to several people reads as one row; a repeat at another step doesn't merge.
const row = (agent, step, text) => ({event_type: "midrun_whisper", agent, step, text, time: "t"});
const groups = run(`groupWhispers(${JSON.stringify([row("Maya", 5, "a"), row("Luis", 5, "a"), row("Tom", 5, "b"), row("Maya", 9, "a")])})`);
assert.equal(groups.length, 3);
assert.deepEqual([...groups[0].agents], ["Maya", "Luis"]);

// Rows show status; actions live in the reader and depend on status. Nothing is unescaped.
const whisper = (extra) => ({id: "w1", text: "<b>hi</b>", targets: cast.slice(0, 2), at: null,
  sent: [], failed: {}, left: cast.slice(0, 2), status: "scheduled", ...extra});
const rendered = (w) => run(`whisperRow(${JSON.stringify(w)})`);
const actions = (w) => run(`whisperActions(${JSON.stringify(w)})`);
state("idle");
assert(!rendered(whisper()).includes("<b>hi</b>"));
// A "now" whisper is already on its way: nothing to edit, only stop.
assert.match(rendered(whisper()), /Sending/);
assert.doesNotMatch(actions(whisper()), /data-w-action="edit"/);
assert.match(actions(whisper()), /data-w-action="cancel"[^>]*>Stop/);
const later = whisper({at: "February 13, 2023, 14:00:00"});
assert.match(rendered(later), /Scheduled/);
assert.doesNotMatch(rendered(later), /in 2h 0m/);  // times live in the reader
assert.match(actions(later), /data-w-action="edit"/);
const sending = whisper({status: "sending", sent: [cast[0]]});
assert.match(rendered(sending), /1 of 2 done/);
assert.doesNotMatch(actions(sending), /data-w-action="edit"/);
const failed = whisper({status: "failed", sent: [cast[0]], failed: {[cast[1]]: "<boom>"}});
assert.doesNotMatch(rendered(failed), /reached 1 of 2/);
// Failure details are in the reader, not the row.
assert.doesNotMatch(rendered(failed), /Didn't reach/);
assert.match(run(`whisperReader(${JSON.stringify(failed)})`), /Didn't reach Luis: &lt;boom&gt;/);
assert.match(actions(failed), /data-w-action="retry"/);
context.view = "saved-run";
assert.equal(actions(whisper()), "");
assert.equal(actions(later), "");
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

// Upcoming first (soonest first), then the rest; cancelled ones stay listed.
state("idle");
context.data.whispers = [
  whisper({id: "late", at: "February 13, 2023, 18:00:00"}),
  whisper({id: "soon", at: "February 13, 2023, 13:00:00"}),
  whisper({id: "gone", status: "cancelled", left: []}),
  whisper({id: "done", status: "sent", left: [], sent: cast.slice(0, 2),
    received: {[cast[0]]: {step: 5, time: "February 13, 2023, 09:00:00"}, [cast[1]]: {step: 5, time: "February 13, 2023, 09:00:00"}}}),
];
context.data.events = [];
run("renderEvents()");
const pane = element("w-list").innerHTML;
assert(pane.indexOf('data-w-id="soon"') < pane.indexOf('data-w-id="late"'));
assert(pane.indexOf('data-w-id="late"') < pane.indexOf('data-w-id="done"'));
assert.match(pane, /data-w-id="gone" data-status="cancelled"/);
assert.match(pane, /data-w-id="done" data-status="sent"/);
// Tab badge: scheduled count plus a clock icon.
assert.match(element("n-events").innerHTML, /^2<svg[^]*<\/svg>$/);
assert.equal(element("n-events").title, "0 sent, 2 scheduled");
assert.equal(element("w-new").hidden, false);
assert.match(pane, /Game time only moves during a run/);
// The status filter hides unchecked statuses.
run(`whisperShow.delete("cancelled"); renderEvents(); whisperShow.add("cancelled")`);
assert.doesNotMatch(element("w-list").innerHTML, /data-w-id="gone"/);

// Whispers known only from the event log (older runs) list newest first, names in send order.
context.data.whispers = [];
context.data.events = [row("Maya Okonkwo", 5, "first"), row("Luis Hernandez", 5, "first"), row("Tom Whitaker", 9, "second")];
run("renderEvents()");
const sent = element("w-list").innerHTML;
assert(sent.indexOf("second") < sent.indexOf("first"));
assert.match(sent, /Maya, Luis/);
assert.doesNotMatch(sent, /Game time only moves/);

// No run loaded: says what to do instead of offering a button that can't work.
context.data = {status: "stopped", sim: null};
run("renderEvents()");
assert.match(element("w-list").innerHTML, /Start a run to plant whispers/);
assert.equal(element("w-new").hidden, true);

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
assert.equal(said(told(), [quietRow(200, speakers, "w")], talk(200, speakers)), "Not detected.");
assert.equal(said(told(), [], talk(50, speakers)), "Neither of them had heard it yet.");
assert.equal(said(told(), [], talk(200, [cast[2], cast[3]])), "Neither of them had heard it yet.");
assert.equal(said(told(), [], talk(200, speakers)), "This one wasn't checked.");
assert.equal(said(told(), [{step: 200, time: "t", speakers, checked: [], failed: ["w"], mentions: []}], talk(200, speakers)),
  "This one wasn't checked.");
// The conversation a whisper came up in isn't also drawn grey.
assert.equal(story(told(), [mentionRow(200, speakers, "w")], [talk(200, speakers)]).talks.length, 0);

// The whole panel, with hostile text in every field.
state("idle", {step: 400, roster: []});
context.data.whispers = [told({failed: {[cast[3]]: "<b>boom</b>"}}), told({id: "scheduled-only", received: {}, sent: [], status: "scheduled", left: cast})];
context.data.mentions = [mentionRow(200, speakers, "w")];
context.data.conversations = [talk(200, speakers), talk(150, [cast[1], cast[3]])];
run("renderTrail()");
const chart = element("trail-chart").innerHTML;
assert.match(chart, /<svg/);
// Spread tree: two told, one secondhand, one failed.
assert.equal((chart.match(/class="tr-node"/g) || []).length, 3);
assert.equal((chart.match(/class="tr-node failed"/g) || []).length, 1);
assert.equal((chart.match(/class="tr-edge told"/g) || []).length, 2);
assert.equal((chart.match(/class="tr-edge talk"/g) || []).length, 1);
assert.equal((chart.match(/class="tr-edge failed"/g) || []).length, 1);
// The secondhand edge carries its conversation's key; clicking it opens the transcript.
assert.match(chart, new RegExp(`data-trail-hop="${run(`convoKey(${JSON.stringify(talk(200, speakers))})`).replace(/\|/g, "\\|")}"`));
assert.match(chart, /Maya&lt;\/span&gt; → &lt;span[^"]*Denise/);
// Mention counts are in the tooltip, not under the name.
assert.match(chart, /Brought it up&lt;\/span&gt;&lt;span&gt;1×/);
assert.doesNotMatch(chart, /class="sub"/);
// Hostile text stays text.
assert.doesNotMatch(chart, /<b>boom|<i>vote/);
assert.match(chart, /&amp;lt;i&amp;gt;vote/);
// Stat chips, with the full summary as the tooltip.
const stats = element("trail-summary").innerHTML;
assert.match(stats, /Reached <b>2<\/b>/);
assert.match(stats, /Secondhand <b>1<\/b>/);
assert.match(stats, /Missed <b>1<\/b>/);
assert.match(element("trail-text").innerHTML, /data-trail-open="w"/);
assert.match(element("trail-summary").title, /Told to 2 people\. 1 more heard it/);
// The picker omits scheduled whispers nobody has heard yet.
assert.doesNotMatch(element("trail-select").innerHTML, /scheduled-only/);
assert.match(element("trail-select").innerHTML, /&lt;b&gt;The vote moved/);
assert.doesNotMatch(element("trail-select").innerHTML, /<b>The vote/);
// A checked conversation that didn't bring it up: a tick on the lane of each person who knew it.
context.data.mentions = [mentionRow(200, speakers, "w"), quietRow(250, [cast[0], cast[1]], "w")];
context.data.conversations = [talk(200, speakers), talk(250, [cast[0], cast[1]]), talk(150, [cast[1], cast[3]])];
run("renderTrail()");
const quietChart = element("trail-chart").innerHTML;
assert.equal((quietChart.match(/class="tr-quiet"/g) || []).length, 2);
assert.match(quietChart, /data-trail-convo="[^"]+"/);
assert.match(quietChart, /Not detected/);
// Every clickable mark is focusable and has a complete aria-label.
const marksG = quietChart.match(/<g [^>]*data-trail-(agent|refl|convo|open)=[^>]*>/g) || [];
assert.ok(marksG.length >= 7);
for (const g of marksG) assert.match(g, /tabindex="0" role="button" aria-label="[^"]+\."/);
assert.doesNotMatch(quietChart, /aria-label="[^"]*(, \.|\. \.|: \.)/);
// The Whisper pill comes first in Tab order, then each lane with its own marks.
assert.ok(quietChart.indexOf('class="tr-you"') < quietChart.indexOf("data-trail-hop"));
// The tick's tooltip and the key's entries each explain themselves.
assert.match(quietChart, /Not detected\. · /);
assert.match(quietChart, /Reflection via a talk/);

// The trail follows the shared whisper focus.
context.data.whispers = [told(), told({id: "second", text: "A second one", received: {[cast[3]]: {step: 350, time: "February 13, 2023, 13:00:00"}}})];
run("setFocus({whisper: 'w'}); renderTrail()");
assert.match(element("trail-summary").innerHTML, /Reached <b>2<\/b>/);
run("setFocus({whisper: 'second'}); renderTrail()");
assert.match(element("trail-summary").innerHTML, /Reached <b>1<\/b>/);
// No focus: the newest sent whisper.
run("setFocus({whisper: null}); renderTrail()");
assert.match(element("trail-text").innerHTML, /data-trail-open="second"/);

// Empty states say what to do.
state("idle");
context.data.whispers = [];
run("renderTrail()");
assert.match(element("trail-chart").innerHTML, /Once a whisper has gone out/);
assert.equal(element("trail-select").hidden, true);
context.data = {status: "stopped", sim: null};
run("renderTrail()");
assert.match(element("trail-chart").innerHTML, /Start a run/);

console.log("Whisper labels, hints, grouping, row actions, ordering, chart, keyboard, escaping: passed");
