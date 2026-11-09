# How LLM Agent-Based Social Simulation Papers and Tools Visualize Their Runs

Scope: figures and interfaces in LLM multi-agent social simulation work, organized by data type. Figure descriptions come from arXiv HTML text: captions plus surrounding prose. The images themselves were not viewed, so any axis label not stated in the text is marked as inferred or unknown.

## Q1. Generative Agents (Park et al. 2023): Smallville replay UI, diffusion figure, relationships, memory stream, evaluation

### Takeaway
Generative Agents draws the whole run as a sprite-based town with an emoji bubble over each agent. Memory and retrieval appear as illustrative schematics, not data plots. The social results are thin: one diffusion-path diagram, plus percentages and network density stated in text. The only quantitative chart is a TrueSkill bar chart. The real memory inspector is a plain text page per agent in the code release, not in the paper.

### Cited Findings
- **Map/activities (live UI):** The sandbox uses the Phaser web framework and shows an overhead sprite town. Each agent's current action appears as emojis in a speech bubble above its avatar. Clicking an avatar shows the full natural-language action description. Users can chat with agents, speak as an agent's "inner voice," or edit object state in natural language (e.g., set a stove to "burning"). — [arXiv 2304.03442](https://arxiv.org/html/2304.03442)
- **Fig. 1:** Screenshot of Smallville with 25 agents. **Fig. 2:** Labeled map of the town. The world is modeled as a tree (world → areas such as houses and the cafe → objects such as a table), and each agent remembers only the subtree it has seen. — [arXiv 2304.03442](https://arxiv.org/html/2304.03442)
- **Fig. 3:** One agent's morning (John Lin) as an illustrated sequence: wake, brush teeth, shower, eat, talk with family, go to work. This is a single-agent narrative timeline, not a chart. The figure says he wakes around 6 am while the text says 7 am, a small inconsistency. — [arXiv 2304.03442](https://arxiv.org/html/2304.03442)
- **Fig. 4:** Screenshot of agents gathered at the Valentine's Day party at Hobbs Cafe. — [arXiv 2304.03442](https://arxiv.org/html/2304.03442)
- **Memory stream diagrams:**
  - Fig. 5 is the architecture loop: perceive → memory stream → retrieve → plan/reflect/act, with outputs written back to the stream.
  - Fig. 6 shows a long list of observations (e.g., "refrigerator is idle") on the left. On the right, a query ("What are you looking forward to the most right now?") ranks memories by retrieval score; party-related memories rank highest.
  - Fig. 7 is a reflection tree for Klaus Mueller: leaf observations are synthesized upward into higher-level reflections such as "dedicated to research."
  - [arXiv 2304.03442](https://arxiv.org/html/2304.03442)
- **Information diffusion:**
  - Fig. 9 is a diffusion-path diagram of who told whom about Isabella's party. By the end, 12 agents besides Isabella had heard.
  - Quantities appear only in text: party awareness rose from 1 agent (4%) to 13 (52%); Sam's election candidacy rose from 1 (4%) to 8 (32%) over two game days. Five of 12 invitees attended.
  - [arXiv 2304.03442](https://arxiv.org/html/2304.03442)
- **Relationships:** No network graph appears in the paper. Network density is reported numerically as rising from 0.167 to 0.74, using η = 2|E|/(|V|(|V|−1)). Hallucinated relationship claims were 1.3% (6 of 453 responses). — [arXiv 2304.03442](https://arxiv.org/html/2304.03442)
- **Evaluation:** Fig. 8 is a bar chart of TrueSkill μ per condition, with σ ≈ 0.68–0.72:

  | Condition | TrueSkill μ |
  |---|---|
  | Full architecture | 29.89 |
  | No reflection | 26.88 |
  | No reflection or planning | 25.64 |
  | Crowdworker | 22.95 |
  | No memory, planning, or reflection | 21.21 |

  Evaluators could access the agent's full memory stream during a replay. — [arXiv 2304.03442](https://arxiv.org/html/2304.03442)
- **Replay/demo tooling (code release):**
  - `/simulator_home` shows the live map and a list of active agents; the user moves around with the arrow keys.
  - `/replay/<sim>/<step>` replays a saved run. The author says it is mainly for debugging: all character sprites look identical and visuals are not optimized.
  - `/demo/<sim>/<step>/<speed>` plays a compressed run with proper sprites, at speeds 1–5.
  - [GitHub joonspk-research/generative_agents](https://github.com/joonspk-research/generative_agents)
- **Memory inspector (persona_state page in the code release):** The template is a per-agent text page with these sections:
  - Basic info: name, age, current time, current tile.
  - Settings: vision radius, attention bandwidth, retention.
  - Personality: innate, learned, currently, lifestyle.
  - Current Action State: daily requirements, daily schedule, action address, start time, duration, description, and "pronunciatio" (the emoji).
  - Agent's Memory (Event): `[node_N] created: description`. Subject–predicate–object triples and keywords exist in the template but are commented out.
  - Agent's Conversation History: created, description, and utterance-by-utterance filling.
  - Agent's Thought: description with "Depth" and "Evidence" (the node IDs a reflection cites).
  - Poignancy/importance scores are **not** displayed anywhere on the page.
  - [persona_state.html in the original repo](https://github.com/joonspk-research/generative_agents/blob/main/environment/frontend_server/templates/persona_state/persona_state.html). I verified this against the local copy from the repo's initial commit.

### Inferences
- **What it does well:** The emoji bubble over each sprite gives a glanceable "what is everyone doing right now" view. The persona_state page exposes everything needed to audit an agent, including reflection evidence links.
- **What it does poorly:** There is no time axis anywhere: no per-agent timeline or swimlane, no location heatmap, no awareness-over-time curve, and no rendered relationship graph. The memory page is an unranked chronological dump with no importance, recency, or retrieval scores, and no filtering. Diffusion is shown only as a static who-told-whom path.

### Gaps
- I could not view the images, so the exact layout of the Fig. 9 diffusion diagram (node/edge encoding, whether time is shown) is unconfirmed.
- I did not read the last third of the paper text (from character 100,000 on), so appendix figures are not covered.

## Q2. Other systems: 1,000 People, Chuang opinion dynamics, S3, AgentVerse, Project Sid, AgentSociety, OASIS, Humanoid Agents, Sotopia, RecAgent

### Takeaway
Most papers chart outcomes, not runs:
- **Aggregate curves over time:** awareness counts, sentiment, polarization share, entropy.
- **Simulated vs. real side-by-side panels.**
- **Per-agent "spaghetti" trajectories:** used for opinion dynamics.
- **A few networks:** Project Sid, OASIS.
- **A few spatial maps:** Project Sid meme scatter, AgentSociety hurricane activity map.

Project Sid has the richest repertoire: role timelines, an action-by-role matrix, meme maps, conversion graphs.

### Cited Findings
**Project Sid (Altera, Minecraft, up to 1,000 agents)** — [arXiv 2411.00114](https://arxiv.org/html/2411.00114)
- **Fig. 5 (item collection):** (A) unique items over time, 25 agents, three conditions (lines averaged over 5 runs). (B) cumulative unique items across 49 agents over 4 hours, with the per-agent average as a dotted line.
- **Fig. 6 (sentiment):** sentiment over time on a 0 (hate) to 10 (love) scale, with and without the social-awareness module, with SEM shading. Panel E plots food given by a chef against sentiment toward each recipient.
- **Fig. 7 (relationships and perception):**
  - (A) directed relationship graph of 50 agents after 4 hours; edges are red for positive and blue for negative sentiment.
  - (B) scatter of perceived vs. true likeability, with regression lines.
  - (C) perception accuracy (regression slope) over time.
  - (D) in-degree vs. extroversion.
  - (E) histogram of pairwise sentiment differences.
- **Fig. 8 (role specialization):**
  - (A, B) agent roles over time, derived from rolling windows of social goals: a per-agent timeline/swimlane of role.
  - (C, D, F, G) role distributions, including martial and artistic villages.
  - (E) bar chart of role entropy; 95% CI over 3 sims.
- **Fig. 9 (actions by role):** normalized action frequency by role for a 30-agent village. The text doesn't name the chart type; the description suggests a heatmap/matrix.
- **Fig. 10 (tax law and voting):**
  - (C) community-chest deposits in tax vs. non-tax seasons.
  - (D, E) per-agent lines of % of inventory paid as tax over time, with a mean line and 95% CI, before and after a constitutional amendment.
  - (F–H) ablation comparisons.
- **Fig. 11 (memes):**
  - (A) spatial scatter of agents at minute 100, colored by whether their recent speech contained a meme.
  - (B) bar chart of meme count by town.
  - (C–E) meme-count time series per town.
- **Fig. 12 (Pastafarian religion spread):**
  - (A) event plot of religious-keyword chats per agent over the run, marking priests, direct converts, and indirect converts.
  - (B) conversion level per agent over time.
  - (C) number of agents at each conversion level over time.
  - (D) area of influence over time.
  - (E) conversion graph with critical vs. non-critical exposure edges.
- The paper has no dedicated town map; space appears only in Figs. 10C, 11A, and 12D.

**AgentSociety (Tsinghua FIB lab, 10k+ agents in a city)** — [arXiv 2502.08691](https://arxiv.org/html/2502.08691)
- **GUI (paper):** The paper says the GUI covers experiment management, surveys, and monitoring/playback. Users can chat with agents or send surveys in real time. Playback shows agent records from PostgreSQL: locations, profiles, status history, thought and dialogue history, and survey responses.
- **Fig. 16 (gun-control polarization):** opinion change under three setups:
  - Control: 39% of agents become more polarized, 33% more moderate.
  - Homophilic interaction: 52% become more polarized.
  - Heterogeneous interaction: 89% become more moderate, 11% adopt opposing views.
- **Fig. 17 (inflammatory message):** (a) information spread over time and (b) emotional intensity over time, comparing control, experimental, node-intervention, and edge-intervention conditions.
- **Figs. 18 and 21:** word clouds of agent opinions.
- **Figs. 19–20 (economy and UBI):** GDP and consumption over steps; UBI at step 96 compared against no UBI on consumption and depression (CES-D) over the next 24 steps.
- **Fig. 22 (hurricane):** spatial maps of activity level (travelers ÷ area population) before, during, and after landfall. Activity drops from about 70–90% to about 30%.
- **Fig. 23:** normalized daily trips over nine days, simulated vs. real.
- **Figs. 24–25 (eco-norms):** per-team bars, a scatter of norm-strength increase vs. CO2 reduction, and pie charts of norm composition.
- **Web UI docs:** The "View" action on an experiment opens a results visualization. Users can follow agent movement trajectories, state changes, "inner activities," and agent-to-agent dialogues, and track global metric changes. Clicking an agent avatar opens a detail panel from which you can interview it or send a questionnaire. Map preview redirects to the MOSS platform. — [AgentSociety docs: Using the Visual Interface](https://agentsociety.readthedocs.io/en/latest/01-get-started/04-webui.html)

**OASIS (Twitter/Reddit simulation, up to 1M agents)** — [arXiv 2411.11581](https://arxiv.org/html/2411.11581)
- **Fig. 4:** information propagation metrics over time — scale, depth, and max breadth of cascades — as mean ± CI, simulated vs. real, over 198 instances. Depth is visibly lower in simulation.
- **Fig. 5 (group polarization):** bar charts per judged round, every 10 steps across 80 steps. Red = more extreme, blue = more progressive, green = draw. Example responses appear alongside.
- **Figs. 6 and 8 (herd effect):** Fig. 6 shows mean comment scores for up-treated, down-treated, and control comments, humans in red vs. agents in blue, with 95% CIs. Fig. 8 shows disagree scores over time steps and agent scales.
- **Fig. 7:** opinion distribution of 196 core users, made with Nomic Atlas (an embedding map).
- **Fig. 9:** posts per step about official news vs. misinformation.
- **Fig. 10:** graph of newly formed follow relationships; clustering is visible.
- **Figs. 11–13:** normalized-RMSE ablations (RecSys, temporal feature, LLM backend).
- The paper describes no dashboard.

**Chuang et al. (LLM opinion dynamics)** — [arXiv 2311.09618](https://arxiv.org/html/2311.09618)
- **Fig. 4 (global warming):** per-agent opinion trajectories, one line per agent, colored by initial opinion from dark blue (+2) to dark red (−2). Rows are no, weak, and strong confirmation bias; panels are false vs. true framing; baselines appear alongside. The figure also includes a final opinion distribution. The text doesn't label the axes; x = step and y = opinion on −2..+2 is inferred.
- **Fig. 5:** the same encoding with different initial opinion mixes.
- **Fig. 6 (appendix):** reflective memory. Its caption contradicts itself, saying reflective memory at the start and cumulative memory at the end.
- Bias (mean of final opinions) and diversity (their SD) are reported only in tables, not plotted. The paper has no heatmaps.

**S3 (social-network simulation)** — [arXiv 2307.14984](https://arxiv.org/html/2307.14984)
- **Fig. 2 (Eight-child Mother event):** 2×2 panels of true vs. simulated spread (the number of people who know of the event per time step) and true vs. simulated emotion density. Both emotion trends show two peaks.
- **Fig. 3 (Japan nuclear wastewater event):** true vs. simulated spread, plus the proportion of positive attitudes toward nuclear energy over time. Both show a sharp drop followed by gradual recovery.
- The paper renders no network; results are otherwise in tables.

**Humanoid Agents** — [arXiv 2310.05418](https://arxiv.org/html/2310.05418)
- **Unity WebGL game (Fig. 3):** renders the simulation's JSON output as animation in one of three worlds. At each time step it shows each agent's location, basic needs, emotion, activity, social relationships, and conversation.
- **Plotly Dash analytics dashboard (Fig. 4):**
  - Time series of basic-need satisfaction (fullness, fun, health, social, energy).
  - Time series of relationship closeness.
  - Hovering a point shows the agent's emotion and activity at that moment.

**Sotopia** — [arXiv 2310.11667](https://arxiv.org/html/2310.11667)
- Evaluation-centric figures:
  - Fig. 2: distribution plot of GPT-4 minus human scores per dimension.
  - Fig. 3: pairwise overall performance across model pairs. The text doesn't name the chart type; it is likely a matrix.
  - Tables of 7-dimension SOTOPIA-EVAL scores.
- Conversations are shown as qualitative transcripts that include non-verbal actions (Figs. H.1–H.13).
- Humans used a turn-based chat interface (Fig. F.1).

**RecAgent (recommender sandbox)** — [arXiv 2306.02552](https://arxiv.org/html/2306.02552)
- **Fig. 4 (information cocoons):** entropy over 50 rounds for the baseline and mitigation strategies.
- **Fig. 5 (conformity):** score distributions (1–10) per round; friend count vs. attitude-change probability; one agent's score trajectory.
- **Fig. 2:** believability ratings, which drop after about 15 rounds.
- **Figs. 7–8:** intervention case studies as chat transcripts.
- The paper text does not describe a visual UI.

**AgentVerse** — [arXiv 2308.10848](https://arxiv.org/html/2308.10848)
- No data charts; results are in tables.
- Fig. 5 (Minecraft bookshelf crafting) and Fig. 6 (emergent behaviors: volunteer, conformity, destructive) are illustrated dialogue/scene vignettes.

### Inferences
- **Per-agent trajectories:** Chuang's opinion spaghetti plots; Project Sid's tax-paid lines and conversion level per agent.
- **Aggregate curves:** almost universal (S3, OASIS, AgentSociety, RecAgent, Project Sid).
- **Spread maps:** spatial ones in Project Sid Fig. 11A and AgentSociety Fig. 22; topological ones in Project Sid Fig. 12E, OASIS cascade metrics, and Generative Agents Fig. 9.
- **Swimlane-like role timelines:** only Project Sid Fig. 8A/B.
- **Location heatmaps:** only AgentSociety's hurricane activity maps (regional aggregates). None of the papers I checked shows a per-building occupancy heatmap or a per-agent activity Gantt for a whole day.
- **The "simulated vs. real" twin panel** (S3, OASIS, AgentSociety Fig. 23) is the standard validation figure. It shows shape agreement well, but hides which agents drove the curve.
- **Word clouds** (AgentSociety) summarize opinions cheaply but lose who said what and when.

### Gaps
- **Park et al. 2024, "Generative Agent Simulations of 1,000 People" ([arXiv 2411.10109](https://arxiv.org/abs/2411.10109)):** the HTML version returned 404 and I did not get the figures. From memory (unverified this session), the main figures are bar charts of normalized accuracy against two-week test–retest on the GSS, Big Five, and economic games, plus a scatter of replicated vs. original experimental effect sizes. Verify before citing.
- **AgentSociety Section 7:** axis details are summarized from text, not images.
- **Other systems not researched within budget:** AI Town (a16z), Concordia (DeepMind), YuLan-OneSim, GenSim.

## Q3. Dashboards/inspectors for memory and conversations

### Takeaway
Three systems ship real run inspectors:
- **Generative Agents:** map replay plus a per-agent text page (persona_state).
- **AgentSociety:** web UI with trajectories, dialogues, agent detail panel, metric charts, and interview/survey.
- **Humanoid Agents:** Unity game plus a Plotly Dash time-series dashboard.

Others (OASIS, S3, Chuang, Sotopia, RecAgent, AgentVerse) publish only static figures and transcripts.

### Cited Findings
- **Generative Agents:** live view, replay, and demo routes, plus a persona_state page listing events, conversations (with utterances), and thoughts (with depth and evidence). It shows no importance scores. — [repo](https://github.com/joonspk-research/generative_agents); [template](https://github.com/joonspk-research/generative_agents/blob/main/environment/frontend_server/templates/persona_state/persona_state.html)
- **AgentSociety:** replay of trajectories, states, inner activities, dialogues, and global metrics; click an avatar for details, interview, or survey. — [docs](https://agentsociety.readthedocs.io/en/latest/01-get-started/04-webui.html); [paper](https://arxiv.org/html/2502.08691)
- **Humanoid Agents:** per-time-step status in the game view; time-series dashboard with hover details. — [arXiv 2310.05418](https://arxiv.org/html/2310.05418)
- **OASIS:** no dashboard is described; the only named visualization tool is Nomic Atlas, used for the opinion embedding. — [arXiv 2411.11581](https://arxiv.org/html/2411.11581)

### Inferences
- Common inspector pattern: map + click agent → detail panel (profile, current action, memory/dialogue lists).
- Common missing pieces:
  - Memory ranked by importance or retrieval score; Generative Agents' Fig. 6 shows these scores, but no UI does.
  - Linking a conversation to its downstream memory and behavior changes.
  - A cross-agent time axis tying positions, conversations, and spread together.

### Gaps
- I did not see screenshots of the AgentSociety or Humanoid Agents UIs, so their exact layouts and chart encodings are unconfirmed.
