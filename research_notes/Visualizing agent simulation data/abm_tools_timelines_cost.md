# ABM Tool Conventions, Activity/Movement Timelines, Conversation Logs, and LLM Cost Monitoring

Scope note: the research budget (~15–20 tool calls) was spent on the highest-value primary sources: Kornhauser et al. 2009 (JASSS), NetLogo docs, Mesa docs, Andrienko & Andrienko movement papers (via abstracts and excerpts), conversation-visualization papers, and LangSmith, Langfuse, Helicone and OpenAI usage docs. Repast, AnyLogic, GAMA, ODD/Grimm, chord diagrams and Gantt/swimlane conventions were **not** covered by fetched sources; they are listed under Gaps.

## What do NetLogo/Mesa conventions and ABM visualization guidelines (Kornhauser et al. 2009; ODD) recommend?

### Takeaway
The standard ABM dashboard has four parts: a central **world view**, **time-series plots** of aggregate measures, **monitors** (single live numbers), and **controls** (setup, step and go buttons, sliders). Mesa's SolaraViz copies this layout. Kornhauser et al. 2009 recommend a muted, low-contrast background, small abstract agent shapes, perceptually grounded palettes, redundant encoding for important variables, trails only for a few agents, and removing "chart junk" before presenting.

### Cited Findings
**NetLogo interface conventions**
- NetLogo's View is "a visual representation of the NetLogo world of turtles and patches"; "Plots show data the model is generating"; "Monitors display the value of any reporter" and update several times per second. — [NetLogo Interface Tab Guide](https://docs.netlogo.org/interfacetab.html)
- Controls: sliders change a variable "without having to recode"; buttons are "either once or forever"; switches toggle booleans; choosers are drop-downs. The **Output** widget is "a scrolling area of text which can be used to create a log of activity in the model." — [NetLogo Interface Tab Guide](https://docs.netlogo.org/interfacetab.html)
- Plot pens have modes "line, bar (for a bar chart), or point." Axes can auto-scale independently. Pens can be shown in a legend below the plot ("Show in legend"). — [NetLogo Interface Tab Guide](https://docs.netlogo.org/interfacetab.html)
- NetLogo can export plot data, the view (PNG) and the whole interface. Turtle, Patch and Link monitors show all variables of one agent. — [NetLogo Interface Guide](https://docs.netlogo.org/interface.html)

**Mesa (SolaraViz) conventions**
- SolaraViz "combines grid displays and plots" and runs in Jupyter or as a web app. ModelController provides step, play, pause and reset. UserInputs and Slider expose model parameters. — [Mesa visualization API](https://mesa.readthedocs.io/latest/apis/visualization.html)
- `make_space_component(agent_portrayal, …)` draws the space. `AgentPortrayalStyle` fields are color (default 'tab:blue'), marker ('o'), size (50), zorder, alpha, edgecolors and tooltip. Property layers draw a colormap background with an optional colorbar. `make_plot_component` charts one or more measures over time. There are matplotlib and Altair backends. — [Mesa visualization API](https://mesa.readthedocs.io/latest/apis/visualization.html)
- The default 'tab:blue' color comes from matplotlib's Tableau-10 categorical palette (inference from the name), so Mesa expects a categorical color per agent type. — [Mesa visualization API](https://mesa.readthedocs.io/latest/apis/visualization.html)

**Kornhauser, Wilensky & Rand (2009) "Design Guidelines for Agent Based Model Visualization," JASSS 12(2)**
- Groups ABM visualizations into three categories: "conventional, unstructured and structured." The categories are not mutually exclusive. — [JASSS 12/2/1](https://www.jasss.org/12/2/1.html)
- Color: use pre-built palettes such as ColorBrewer. "Luminosity is prioritized over hue by the low-level visual processing system." "Colors can usually not be ordered on hue alone." — [JASSS 12/2/1](https://www.jasss.org/12/2/1.html)
- Background: "the background should have a low contrast and low intensity," and "the separation between background and foreground should be reinforced." — [JASSS 12/2/1](https://www.jasss.org/12/2/1.html)
- Shape: "the use of figurative icons instead of abstract shapes will impede the viewer's perception of the image as a whole." Choose shapes that are easy to tell apart (a circle vs. a line, not a circle vs. a square). — [JASSS 12/2/1](https://www.jasss.org/12/2/1.html)
- Trails: the viewer can see one agent's displacement over time "by asking the agent to leave a visible trail," but with many agents "the trails would merge and become indistinguishable." — [JASSS 12/2/1](https://www.jasss.org/12/2/1.html)
- Emphasis: "represent a model variable using several redundant visual variables". To show micro-behavior, "hide all agents except the ones" being illustrated, or use halos or blur. Secondary variables should not hamper the main ones. Remove debugging graphics ("chart junk"). — [JASSS 12/2/1](https://www.jasss.org/12/2/1.html)
- Animation: in the redesign example, temporal aliasing was fixed by shrinking each agent's step between frames. — [JASSS 12/2/1](https://www.jasss.org/12/2/1.html)
- The paper gives no explicit maximum number of colors. — [JASSS 12/2/1](https://www.jasss.org/12/2/1.html)

### Inferences
- For a dashboard with 8 agents in fixed categorical colors, the NetLogo/Mesa layout carries over directly: map as world view, a strip of monitors (KPI tiles), time-series plots below, and a scrolling event or conversation log in place of the Output widget.
- Kornhauser's guidance argues for a desaturated or dimmed town map so the 8 agent colors stand out, for redundant encoding (color plus a name label or initial, which also helps colorblind viewers), and for trails only for the selected or hovered agent, never all 8 at once.
- Their warning against figurative icons is in tension with a pixel-art "peg sprite" style. The fix is to keep sprites small and give each a solid color patch or outline in its agent color, so the color, not the sprite detail, carries identity.
- Eight hues is near the practical limit of categorical palettes (ColorBrewer's qualitative sets top out at 8–12). Hue alone can't be ordered, so agent color must never also encode a quantity.

### Gaps
- No fetched sources on Repast Simphony, AnyLogic or GAMA interface conventions. From general knowledge, all three use a 2D/3D display plus charts and inspectors, but this is uncited.
- Did not fetch Grimm et al. ODD / ODD+D papers. As far as I know, ODD documents model design and does not prescribe visualizations, but this is unverified.
- Did not reach the ABM-specific "visual analytics" literature beyond Kornhauser.

## Movement/trajectory and activity-over-time visualization conventions (Andrienko & Andrienko; time geography)

### Takeaway
The movement visual-analytics literature (Andrienko & Andrienko) treats raw trajectory lines on a map and the Hägerstrand space-time cube as the base forms. Both clutter and occlude quickly, so the literature turns to aggregation (flow maps, density) and linked temporal displays. Flow maps lose the time dimension unless animated or shown as small multiples.

### Cited Findings
- Drawing trajectories "as lines or traces on a map or in a space-time cube is not appropriate for massive movement data because such a display is illegible due to cluttering and overlapping of the symbols." The proposed fix is spatial generalization and aggregation into flows between places (Andrienko & Andrienko, IEEE TVCG 2010). — [Spatial Generalization and Aggregation (City Univ. repository)](https://openaccess.city.ac.uk/id/eprint/7614/1/Spatial_Generalization_and_Aggregation.pdf) (text taken from a search excerpt; the PDF itself was not machine-readable when fetched)
- Flow maps "do not reflect the temporal dimension of movement data but show cumulative movements" over a period. The approach can be extended to animated flow maps or a series of flow maps over time. — [same source](https://openaccess.city.ac.uk/id/eprint/7614/1/Spatial_Generalization_and_Aggregation.pdf) (search excerpt)
- Space-time cube: two axes for geographic space and a third (usually vertical) for time. Introduced by T. Hägerstrand in the 1960s. — [same source](https://openaccess.city.ac.uk/id/eprint/7614/1/Spatial_Generalization_and_Aggregation.pdf) (search excerpt)
- Even two trajectories on a map or in a space-time cube "may be difficult to analyse if they have common locations" (Andrienko et al., Cartographica 2007). — [Designing visual analytics methods for massive collections of movement data](https://openaccess.city.ac.uk/id/eprint/2842/1/Designing%20visual%20analytics%20methods%20for%20massive%20collections%20of%20movement%20data.pdf) (search excerpt)
- Flow maps get "extremely cluttered when there are flows between non-neighboring regions" (MobilityGraphs, 2016). — [VAST2015 / MobilityGraphs paper](https://openaccess.city.ac.uk/id/eprint/12849/1/VAST2015.pdf) (search excerpt)
- Trails merge and become indistinguishable when many agents are shown. — [Kornhauser et al. 2009](https://www.jasss.org/12/2/1.html)

### Inferences (strengths, weaknesses, fit for 8 agents)
- **Trails on the 2D map.** Strength: intuitive and in context. Weakness: with 8 agents sharing a small town and the same buildings, trails overlap (the Andrienko "common locations" problem). Fit: show the trail for the selected agent only, fading with age.
- **Heatmap / density of visits.** Strength: shows hotspots and doesn't depend on the number of agents. Weakness: loses identity and time, and a sequential color ramp competes with the categorical agent colors. Fit: good as a toggle layer, in one neutral sequential ramp, not per agent.
- **Space-time cube.** Strength: faithful to Hägerstrand; shows co-presence (two agents meeting in the same place at the same time) as converging lines. Weakness: 3D occlusion, needs rotation, hard to read on a flat dashboard. Fit: poor for a glanceable dashboard; maybe as an exploratory extra.
- **Location-by-time matrix / swimlane (Gantt) timeline.** Rows are agents (8 lanes, each in its agent color). The x-axis is sim time. Segments are colored or labeled by activity or location (or rows are locations, with agent-colored marks). Strength: no occlusion, scales over long runs, shows co-location as vertical alignment. Weakness: drops geography, and once agent color sets the lanes, a second categorical variable (location or activity) needs another channel such as labels, texture or lightness. Fit: probably the best primary "activity over time" chart for 8 agents. This is my synthesis; no fetched source states it.
- **Flow map between buildings.** Good for an aggregate "where people go" view, but it loses time and clutters with non-adjacent links.

### Gaps
- Did not fetch the Andrienko 2013 *Information Visualization* overview or the book *Visual Analytics of Movement* (2013) directly. The core.ac.uk PDF returned 403.
- No fetched source on Gantt/swimlane conventions for agent activity or on location-by-time matrices specifically. The inferences above are uncited synthesis.
- Hägerstrand's own time-geography sources (prisms, paths) were not fetched beyond the cube attribution.

## Conversation/dialogue logs between multiple agents

### Takeaway
Research tools for multi-party dialogue center on **temporal, speaker-lane layouts** (who spoke when) and turn-level glyphs. Examples: TeMoCo's "temporal mosaic," Discussion Flows for turn-taking and silences, and the Conversation Clock and Chat Circles from Donath, Karahalios and Viégas. For an 8-agent dashboard, a chat-transcript list with speaker-colored names, paired with a who-talked-when timeline, follows these conventions.

### Cited Findings
- TeMoCo: "A Visualization Tool for Temporal Analysis of Multi-party Dialogues in Clinical Settings" (Sheehan, Albert, Luz, Masoodian, 2019). Keywords: temporal mosaics, temporal visualization, speech visualization. — [Sheehan et al. 2019 (Zenodo)](https://zenodo.org/records/3689486/files/Sheehan2019.pdf); [Edinburgh research portal](https://www.research.ed.ac.uk/en/publications/temoco-a-visualization-tool-for-temporal-analysis-of-multi-party-/)
- Per the search summary, the temporal mosaic divides vertical space among the active participants over time. I could not verify this in the PDF text, which was not machine-readable. — [Edinburgh research portal](https://www.research.ed.ac.uk/en/publications/temoco-a-visualization-tool-for-temporal-analysis-of-multi-party-/)
- Discussion Flows (EuroVis 2021 short paper) is a multi-level visualization of engagement in multi-party meetings, built from transcripts and aimed at turn-taking and social cues such as awkward silences. — [Discussion Flows (Eurographics DL)](https://diglib.eg.org/bitstream/handle/10.2312/evs20211060/085-089.pdf) (search excerpt)
- ConToVi (El-Assady et al., EuroVis 2016) tracks speaker movement through a topic space, with glyphs per speaker turn. — [ConToVi (dbvis)](https://scibib.dbvis.de/uploadedFiles/FINAL_Submission.pdf) (search excerpt)
- VisArgue (ACL 2017 demo) analyzes transcribed multi-party discourse, including turn-taking. — [Ruan et al., P17-4009](https://preview.aclanthology.org/fix_video/P17-4009.pdf) (search excerpt)
- Chat Circles (Donath, Karahalios, Viégas) uses growing and shrinking circles to reflect turn-taking rhythm. The Conversation Clock (Bergstrom & Karahalios 2007) captures turn-taking in co-located meetings. — [Visualizing Conversation (academia.edu)](https://www.academia.edu/125416792/Visualizing_Conversation) (search excerpt)
- NetLogo's Output widget, a scrolling text log of model activity, is the ABM-native precedent for a transcript panel. — [NetLogo Interface Tab Guide](https://docs.netlogo.org/interfacetab.html)

### Inferences (strengths, weaknesses, fit for 8 agents)
- **Chat transcript list** (speaker name or avatar in agent color, timestamp, location). Strength: readable, keeps content. Weakness: no overview, and hard to see the overall pattern. Fit: essential, but group messages by conversation (participants plus place) rather than one global stream.
- **Who-talked-when timeline** (8 agent lanes, with bars for utterances or conversation spans and lines linking participants). Strength: shows turn-taking, silence and isolation (an agent who never talks). Fits the fixed lane colors. Weakness: hides content, so link it to the transcript on click.
- **Chord diagram / adjacency matrix of who-talked-to-whom.** Strength: compact summary of the social network for 8 nodes (an 8×8 matrix is small). Weakness: chords lose time and get hard to read when every chord is colored by agent. A heatmap matrix (rows = speaker, columns = listener) is often more precise. This is uncited synthesis.
- **Turn-taking plots** (utterances per agent per window, as a stacked bar or small multiples). Useful for balance and dominance, but 8 stacked categories are hard to compare except for the bottom layer.

### Gaps
- No fetched source on chord diagrams for dialogue or on LLM multi-agent conversation viewers (for example, Generative Agents' replay UI). The paper texts above were not machine-readable, so the details rest on search excerpts.

## LLM API usage and cost observability (LangSmith, Langfuse, Helicone, OpenAI) — what charts do they use?

### Takeaway
LLM observability dashboards converge on **time-series line or stacked-bar charts** of trace count, latency, tokens and cost. They break these down by model, user, feature or tag with a global "group by". They add KPI tiles for totals, and latency percentiles (p50/p95/p99), error rates, and ranked bars for top tools or models. Budgets are usually handled as limits and alerts rather than as a charted burn-down.

### Cited Findings
- LangSmith prebuilt dashboards have sections for Traces ("Trace count, latency and error rates"), LLM Calls (count and latency), Cost & Tokens (split by token type, total and per trace), Tools ("Run counts, error rates, and latency stats … broken down by tool name", top 5), Run Types and Feedback Scores. — [LangSmith dashboards](https://docs.langchain.com/langsmith/dashboards)
- LangSmith custom chart types: Line, Stacked bar, KPI, Ranked bar, Donut, Table. A single global group-by (run tags or metadata) applies across charts. — [LangSmith dashboards](https://docs.langchain.com/langsmith/dashboards)
- Langfuse: cost and latency "broken down by user, session, geography, feature, model and prompt version". Quality is tracked over time and across prompt versions. The dashboard shows "trace volume, model costs, evaluation scores, observation trends, and model usage." — [Langfuse metrics overview](https://langfuse.com/docs/metrics/overview)
- Langfuse custom dashboards: line charts ("Perfect for tracking trends over time (latency, cost, usage)"), bar charts to compare models, users or features, time series, and pie charts for proportions. Curated Latency, Cost ("Track token usage and associated costs over time") and Usage dashboards. — [Langfuse custom dashboards](https://langfuse.com/docs/metrics/features/custom-dashboards)
- Helicone: headline totals (requests, cost, average latency, error rate), time series of each, p50/p95/p99 latency, cost broken down by model, user or endpoint, and custom `Helicone-Property-*` headers to segment cost by feature. — [Helicone observability overview (Mintlify mirror of docs)](https://mintlify.com/Helicone/helicone/observability/overview); [Helicone metrics (mirror)](https://mintlify.com/helicone/helicone/observability/metrics). These are third-party mirrors; the official docs.helicone.ai page returned 404.
- OpenAI usage dashboard: its own project selector (empty = all projects), per-API-key filtering, timestamps in UTC, and access limited to org owners or users granted permission. — [OpenAI Help: API usage dashboard](https://help-lb.openai.com/en/articles/10478918-api-usage-dashboard)
- OpenAI project monthly budgets are set under Project → Limits ("Set Budget"). — [JHU guide to OpenAI usage limits](https://support.cmts.jhu.edu/hc/en-us/articles/38383798293133-Guide-to-Managing-API-Keys-and-Usage-Limits-on-platform-openai-com). A secondary news summary reports org and project hard limits returning 429, and says recorded spend can slightly exceed the limit; unverified against OpenAI. — [aicatchup news summary](https://aicatchup.com/news/openai-api-key-usage-spend-hard-limits)
- I found no authoritative source confirming the exact chart types in OpenAI's native usage dashboard. — (search result, see [OpenAI Help](https://help-lb.openai.com/en/articles/10478918-api-usage-dashboard))

### Inferences (strengths, weaknesses, fit for 8 agents)
- **Stacked area or stacked bar of cost per sim step, by agent** (8 agent colors) or by call type (plan, converse, reflect, embed). Strength: shows total and composition. Weakness: only the bottom layer and the total read accurately, and 8 stacked layers is the upper limit. Prefer stacking by the 3–5 call types and showing per-agent cost as a ranked bar, which matches LangSmith's "Ranked bar".
- **Cumulative spend vs. budget line.** A monotonic line with a horizontal budget threshold and optionally a projected run-out. Strength: answers "will this run fit the budget?" at a glance. Weakness: hides rate spikes, so pair it with a per-step rate chart. Vendors mostly handle budgets as limits and alerts, so this chart is a sensible addition rather than a copied convention.
- **Tokens per step (input vs. output, split as LangSmith does by token type).** Shows prompt bloat as memories grow. Use a log scale or a separate axis if embeddings dwarf the rest.
- **Latency percentiles (p50/p95/p99) per step or per call type.** The industry norm (Helicone, LangSmith); shows tail calls that stall the simulation clock. Means alone hide the tail.
- **KPI tiles** (total cost, tokens, calls, error rate, cost per sim-hour). These are the analog of NetLogo monitors and LangSmith KPI charts.
- **Pitfalls:** mixing $ and tokens on twin axes, pie or donut charts with 8 slices, coloring call types with the agent palette (it collides with agent identity, so use a separate neutral or sequential scheme for non-agent categories), and wall-clock vs. sim-time x-axes (choose one, label it, and keep it consistent with the map and timeline).

### Gaps
- Official Helicone docs could not be fetched (404). Findings rely on a Mintlify mirror.
- No authoritative description of the chart types in OpenAI's native usage dashboard was found.
- No sources found on cost visualization specific to LLM multi-agent simulations (for example, the Generative Agents cost reporting).
