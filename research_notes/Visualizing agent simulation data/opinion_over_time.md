# Visualizing opinion/stance data over time (opinion dynamics and computational social science)

Data shape this note targets: about 8 agents, each with a 0–100 stance score sampled periodically during a simulated run, plus a rationale and the evidence memories behind each reading. Each agent has a fixed categorical color in the dashboard.

## Which chart forms do opinion dynamics papers use (classical and LLM-based)?

### Takeaway
There are two dominant forms. One is a per-agent trajectory ("spaghetti") plot, opinion on y and time on x. The other is a distribution view: a final-state histogram, or an opinion-density-over-time "colored histogram" or heatmap. Summary metrics are usually a mean (bias) and a standard deviation (diversity), or one of several formal polarization measures. The LLM-agent work of Chuang et al. puts trajectories and final distributions side by side, but it colors lines by *initial opinion*, not by agent identity.

### Cited Findings
- Chuang et al., "Simulating Opinion Dynamics with Networks of LLM-based Agents" (arXiv:2311.09618, v4 April 2024). Fig. 4 is a grid of per-agent opinion-trajectory line plots, each paired with a plot of the final opinion distribution F_o^T. Panels vary confirmation bias (none, weak, strong) and framing (true/false), and there are baselines without interaction or role-play. Fig. 5 repeats the layout for different initial opinion distributions (e.g. 8 agents at +2 and 2 at −2) — [arXiv HTML](https://arxiv.org/html/2311.09618v4)
- In Chuang et al., opinions sit on a discrete 5-point scale from −2 to +2. A classifier maps the agent's free-text report to that numeric opinion. "The color of each line plot corresponds to the agent's initial opinion": dark blue for +2, light blue +1, grey 0, light red −1, dark red −2. That is a diverging color encoding of starting stance, not identity — [arXiv HTML](https://arxiv.org/html/2311.09618v4)
- Chuang et al. summarize the final state with two metrics. Bias B is the mean final opinion, and diversity D is the standard deviation of the final distribution — [arXiv HTML](https://arxiv.org/html/2311.09618v4)
- The paper's headline result is about distributions. Without bias, agents converge toward consensus "in line with scientific reality"; inducing confirmation bias through prompting produces opinion fragmentation — [arXiv abstract](https://arxiv.org/abs/2311.09618)
- Flache et al. 2017 (JASSS review, "Models of Social Influence: Towards the Next Frontiers"). Fig. 1 shows the evolution of opinion distributions in a 1-D bounded opinion space for three canonical outcomes: consensus, clustering and bi-polarization. Fig. 2 uses scatter-style plots with moderates as blue dots and initial extremists as red dots — [JASSS](https://www.jasss.org/20/4/2.html)
- Flache et al. give no single polarization metric. They call for shared standards and point to Bramson et al. (2016) for measuring bi-polarization — [JASSS](https://www.jasss.org/20/4/2.html)
- Bramson et al. 2016 ("Disambiguation of social polarization concepts and measures", J. Math. Sociology 40(2)) separate polarization into nine senses, give a formal measure for each, and apply them to General Social Survey attitude data — [Taylor & Francis](https://informahealthcare.com/doi/abs/10.1080/0022250X.2016.1147443); companion paper [Philosophy of Science 2017](https://philarchive.org/rec/BRAUPM-3)
- Bounded-confidence (Hegselmann–Krause / Deffuant) teaching tools commonly use the same two-panel pattern. The top panel shows each agent's opinion trajectory over time and the bottom panel shows the current opinion distribution — [HK model explainer](https://rf.mokslasplius.lt/hegselmann-krause-bounded-confidence-model/); a Frankfurt applet's "time chart" plots opinion trajectories for HK and Deffuant–Weisbuch — [Uni Frankfurt applet](https://itp.uni-frankfurt.de/~gros/StudentProjects/Applets_2014_OpinionDynamics/index.html)
- In symmetric HK settings, trajectories never cross. That property is one reason spaghetti plots stay readable for HK — [Frankfurt slides](https://itp.uni-frankfurt.de/~gros/StudentProjects/Applets_2014_OpinionDynamics/presentation.pdf)
- Jan Lorenz's NetLogo bounded-confidence model is described (per its search snippet) as having three views: a rolling colored histogram of opinion density over time, where patch color is the number of agents at that opinion; rolling trajectories colored by the agent's confidence bound; and trajectories of the mean and median opinion — [Modeling Commons](https://modelingcommons.org/browse/one_model/3405) (the page I fetched did not show this text, so it is unverified)
- Lorenz also reformulates bounded confidence as density-based, master-equation-style models, computed as the time evolution of the agents' density. This is the analytic counterpart of the density heatmap — [Lorenz 2007 survey, arXiv:0707.1762](https://arxiv.org/pdf/0707.1762)
- In an LLM fake-news simulation ("From Skepticism to Acceptance", arXiv:2403.09498), macro dynamics are shown as group counts over time (infected/recovered) with a red dashed SIS-model fit curve. Micro dynamics are shown as a case study comparing two named individuals' opinion trajectories over 15 days. "Sandra, being skeptical, tends to maintain a consistent view," while Michael's opinion shifts back and forth — [arXiv HTML](https://arxiv.org/html/2403.09498v2)
- Noorazar's 2020 survey (EPJ Plus) covers continuous and discrete opinion-space models and agent types such as stubborn agents. I did not check its figures — [arXiv:2004.05286](https://arxiv.org/abs/2004.05286v3)

### Inferences
- With 8 agents, the per-agent trajectory plot is the conventional form and is not overplotted. Density heatmaps and ridgelines are built for populations (hundreds to thousands of agents) and would look sparse and blocky with N=8.
- Pairing a trajectory panel with a "current/final distribution" strip (Chuang's layout) carries over well. A dot strip or beeswarm of the latest 8 readings works better than a histogram at N=8.
- Mean (bias) and SD (diversity) lines over time are cheap, literature-backed summary metrics to add as a secondary panel.
- Chuang's choice of coloring by initial stance conflicts with a fixed per-agent identity palette. A dashboard can keep identity colors on the lines and show stance through y-position only. Don't add a second diverging hue channel.

### Gaps
- I did not retrieve figures from the original DeGroot, Deffuant et al. 2000, Hegselmann & Krause 2002 (the PDF was not fetched), or voter-model papers. Statements about the "standard HK figure" (trajectory plots, or final opinion vs. ε bifurcation diagrams) rest on secondary sources only.
- I found no source that uses ridgelines or small-multiple histograms at time slices specifically in opinion dynamics. Both are plausible but unverified here.

## How do papers show stance transitions?

### Takeaway
Opinion-dynamics papers mostly show change implicitly, through trajectories. Explicit transition graphics come from viz and survey practice instead. Alluvial/Sankey diagrams show changes in group membership across time steps. Slopegraphs show before/after per entity.

### Cited Findings
- Rosvall & Bergstrom (2010, PLOS ONE, "Mapping Change in Large Networks") introduced alluvial diagrams to show changes in group composition over time and to highlight significant changes — [PLOS ONE doi:10.1371/journal.pone.0008694](https://doi.org/10.1371/journal.pone.0008694); [Wikipedia summary](https://en.wikipedia.org/wiki/Alluvial_diagram)
- Survey practice: FiveThirtyEight/Ipsos used an alluvial chart to show how Americans' top concern shifted across 6 survey waves before the 2022 midterms — [UC3M dataviz project](https://csslab.uc3m.es/dataviz/projects/2023/100513795/)
- The ggalluvial R package builds alluvial diagrams from tidy data within ggplot2's grammar — [JOSS paper](https://joss.theoj.org/papers/10.21105/joss.02017.pdf)
- A slopegraph is a line graph with only two points per category, drawn between two parallel axes; slope direction encodes increase or decrease. Tufte popularized it (*Visual Display of Quantitative Information*, 1983) — [Wikipedia: Slope chart](https://en.wikipedia.org/wiki/Slope_chart)
- Slopegraphs get busy with many categories and are designed for two time points only. Longer series call for line charts — [Wikipedia: Slope chart](https://en.wikipedia.org/wiki/Slope_chart); [Baryon: Slopegraphs](https://baryon.be/uncommon-chart-types-slopegraphs)

### Inferences
- Alluvial/Sankey charts need *binned categories* (e.g. oppose / neutral / support). With 8 agents, the flows would be 1–8 units wide and the chart would mostly show individual moves. A plain list ("Agent A: neutral → support at t=12") or a 3×3 transition count table is probably clearer.
- A slopegraph (start vs. now, or pre- vs. post-intervention) fits 8 identity-colored agents well. It works best with direct labels at both ends.
- A dumbbell plot (one row per agent, two dots joined) shows the same information as a slopegraph, sorted by change size. It is often easier to label. I found no source for it in this search.

### Gaps
- I found no opinion-dynamics paper using transition matrices or alluvial diagrams of stance bins. Whether this is conventional in the field is unverified.

## How do papers show the effect of an intervention?

### Takeaway
In LLM opinion simulations, interventions are compared mostly as conditions: small-multiple panels or grids (Chuang's bias × framing grid) or comparison tables against a no-intervention baseline. Within a single time series, the established convention from interrupted-time-series (ITS) practice is a labeled vertical line or shaded band at the intervention, ideally with a counterfactual.

### Cited Findings
- Chuang et al. show treatments (confirmation bias strength, true/false framing) as a grid of panels, each with trajectories plus a final distribution, alongside no-interaction baselines. This is a small-multiples treatment-vs-control design — [arXiv HTML](https://arxiv.org/html/2311.09618v4)
- "From Skepticism to Acceptance" compares intervention timing (day 1 vs. day 7) and frequency (daily vs. every 3 days) of an "official" agent in Fig. 4. The baseline appears in a table: the "No Official" row shows belief average 1.000, against 0.933 for single and 0.900 for multiple declarations. The authors conclude that "early and reasonably frequent regulation" reduces spread — [arXiv HTML](https://arxiv.org/html/2403.09498v2)
- Turner et al. (ITS graph guidance) list the core elements of a good ITS figure: data points, the interruption time, pre- and post-interruption trend lines, and the counterfactual trend. They recommend a vertical line or shading, with a label, for the interruption, and a different line pattern for the counterfactual — [PMC7818488](https://pmc.ncbi.nlm.nih.gov/articles/PMC7818488)
- In a review of 217 public-health ITS graphs, 73% marked the interruption time but only 17% drew a counterfactual line — [Erik Gahner, summarizing Turner et al.](https://erikgahner.dk/?p=23392)
- CausalPy's ITS example uses a solid line at intervention start, a dashed line at its end, and a shaded "impact" region between observed and counterfactual — [CausalPy docs](https://causalpy.readthedocs.io/en/latest/notebooks/its_post_intervention_analysis.html)

### Inferences
- For an injected message in a dashboard: draw a vertical rule at the injection tick with a short label ("Message injected: …"), and optionally shade the post-injection window. A per-agent marker can show when each agent actually *received* or *remembered* the message, since exposure may lag injection.
- A true counterfactual needs a control run, such as the same seed without the injection. If one exists, show it as a dashed or ghosted line per agent, or as small multiples of control vs. treatment. Without a control run, a before/after slopegraph across the injection point is the honest substitute. It does not support causal claims.

### Gaps
- I found no LLM-opinion paper that draws event markers on trajectory plots. The text of 2403.09498 does not say how intervention times appear in its figures.
- I found no difference-in-differences style figure in the opinion-dynamics literature in this search.

## Pitfalls: overplotting, too many colors, sparse/irregular sampling, gaps, discrete vs continuous

### Takeaway
At N=8, overplotting is manageable but real when lines cross or cluster. The fixes are highlight-on-focus or small multiples. Eight categorical colors sit at the upper limit of reliable color matching, so direct labels are advised. Sparse samples should be drawn as points at true timestamps, with step lines or visible gaps, not smooth interpolation. A coarse or discrete underlying scale should not be shown as falsely continuous.

### Cited Findings
- Spaghetti plot remedy 1: draw all series as thin, faint lines and redraw the series of interest bold. Remedy 2: small multiples with identical x/y axes for fair comparison. The European Data Portal guide recommends small multiples only when all series are equally important — [Python Graph Gallery: spaghetti](https://www.python-graph-gallery.com/124-spaghetti-plot); [data.europa.eu: number of series](https://data.europa.eu/apps/data-visualisation-guide/number-of-series)
- The European Data Portal guide says the readable number of lines depends on chart size, how often lines cross, and how close the values are. It suggests a thicker stroke, drawing the key series on top, or a halo for emphasis — [data.europa.eu](https://data.europa.eu/apps/data-visualisation-guide/number-of-series)
- Wilke (*Fundamentals of Data Visualization*): qualitative scales work best with 3–5 categories. At 8–10, "the task of matching colors to categories becomes too burdensome to be useful," so "use direct labeling instead of colors when you need to distinguish between more than about eight categorical items." Test figures in a color-vision-deficiency simulator — [Wilke, ch. 19](https://clauswilke.com/dataviz/color-pitfalls.html)
- The European Data Portal guide suggests about 7 as a good maximum number of color categories. An Atlassian guide advises 10 or fewer — [data.europa.eu: colour for categories](https://data.europa.eu/apps/data-visualisation-guide/colour-for-categories); [Atlassian](https://www.atlassian.com/data/charts/how-to-choose-colors-data-visualization)
- RColorBrewer qualitative palettes top out at 12 colors, and ColorBrewer's colorblind-safe qualitative option is very limited (a summary reports a maximum of 4 colors under that filter). Polychrome targets 24+ distinguishable colors for normal color vision — [Polychrome, J. Stat. Software 2019](https://www.jstatsoft.org/article/view/v090c01)
- Cleveland & McGill (1984, JASA) rank position along a common scale as the most accurate perceptual task, and shading/color saturation the least. Heer & Bostock's crowdsourced replication largely confirmed the ranking — [Cornell INFO 3312 slides](https://info3312.infosci.cornell.edu/slides/04-graphical-perception.html); [arXiv 2212.10533 (critique of rankings)](https://arxiv.org/pdf/2212.10533)
- Missing data: connecting across a gap implies measurements that never happened. Leave gaps (NA), mark missing segments distinctly, and use step interpolation to make sampling intervals visible — [Datawrapper Academy](https://www.datawrapper.de/academy/patchy-data); [Bocoup](https://bocoup.com/blog/showing-missing-data-in-line-charts)
- Some tools draw missing values as zeros by default (Qlik's options: connections, zeros, gaps), which misleads — [Qlik community](https://community.qlik.com/t5/Ideas/Fix-continuous-line-chart-s-display-of-missing-values/idi-p/1729498)
- Discrete scales: Chuang et al.'s opinions are classifier outputs on a 5-level −2..+2 scale, yet they are plotted as line trajectories — [arXiv HTML](https://arxiv.org/html/2311.09618v4)

### Inferences
- With 8 identity colors, the safest pattern is to keep them, add direct end-of-line labels or agent sprites at the latest point, and dim the other agents on hover/selection. Small multiples (8 mini charts on a shared 0–100 y-axis) are a strong alternative, and their position encoding does not depend on telling hues apart.
- Encode stance by y-position, never by color: identity owns the hue channel, and position is the most accurate channel (Cleveland & McGill).
- Mark each actual reading as a dot. Connect dots with straight or step segments only between consecutive readings, and break the line where an agent had no reading. That keeps sparse or irregular sampling honest.
- If the LLM's 0–100 scores cluster on round numbers (e.g. multiples of 5 or 10), the effective scale is coarse. Small jitter, or showing the rationale on hover, keeps readers from over-reading 1–2 point wiggles. This is an inference; I found no source on LLM score granularity.
- The rationale and evidence memories fit best as details-on-demand: click a dot to open its rationale and cited memories. This is general guidance; I found no source in this search.

### Gaps
- I did not retrieve primary text from Tufte (small multiples), Few, or Munzner on the number of series or categorical colors. The Tufte claims rest on the slopegraph secondary sources above. I found no Munzner or Healy statement on palette size.
- I found no source specifically on visualizing irregularly sampled per-agent LLM readings.

## Guidance from viz research relevant to 8 colored series

### Takeaway
Eight series is at the edge of what color alone can carry (sources say about 7–10 hues, with direct labeling advised beyond about 8). Tufte-style small multiples, highlight-and-dim, and direct labeling are the standard ways to keep 8 identity-colored trajectories readable.

### Cited Findings
- Practical ceilings cluster at about 7–10 distinguishable categorical colors, with direct labeling advised beyond about 8 — [Wilke](https://clauswilke.com/dataviz/color-pitfalls.html); [data.europa.eu](https://data.europa.eu/apps/data-visualisation-guide/colour-for-categories)
- Small multiples with shared axes are recommended when there are many equally important series — [data.europa.eu](https://data.europa.eu/apps/data-visualisation-guide/number-of-series); [D3 Graph Gallery: small multiples](https://d3-graph-gallery.com/graph/line_smallmultiple.html)
- Position on a common scale is the most accurate channel — [Cornell slides on Cleveland & McGill](https://info3312.infosci.cornell.edu/slides/04-graphical-perception.html)

### Inferences
- Recommended stack for this dashboard:
  1. A main trajectory chart: 8 identity-colored lines with dots per reading, gaps where a reading is missing, end labels or sprites, hover-to-highlight, and a vertical labeled rule at each intervention.
  2. An optional small-multiples toggle: one panel per agent on a shared 0–100 axis.
  3. A secondary metrics strip: mean (bias) and SD (diversity) over time, following Chuang et al.
  4. A slopegraph or dumbbell for start vs. now, or pre vs. post intervention.
  5. Click a dot to see its rationale and evidence memories.
- Avoid density heatmaps, ridgelines and alluvial charts at N=8; they are population-scale forms.

### Gaps
- None beyond those noted above.
