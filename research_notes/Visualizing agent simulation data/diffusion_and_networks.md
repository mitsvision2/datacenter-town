# Visualizing Information Diffusion Cascades and Small Social Networks

Context: data is "a message injected to some of ~8 agents; who received it directly, who heard it secondhand in a conversation and from whom, at what time, and each person's stance before/after", plus "who talks to whom (conversation counts over time)". Dashboard constraint: each of 8 agents has a fixed categorical color.

## Q1. Which chart forms do cascade studies use (trees, time-anchored trees, S-curves, compartment curves, swimlanes, storylines)?

### Takeaway
The major cascade papers use two families of figures: (a) small node-link drawings of individual cascade trees, with the root/seed highlighted, to show what a cascade looks like, and (b) aggregate statistical plots (log-log CCDFs of size, depth and structural virality, plus time-to-reach-depth/size curves) to compare many cascades. None of the papers I checked uses a time-on-x tree or a storyline. Those forms come from the visualization literature (xkcd's narrative charts, Tanahashi & Ma 2012), and they fit a single, 8-person, time-stamped cascade much better than CCDFs, which only make sense across thousands of cascades.

### Cited Findings
**Cascade-research conventions**
- Goel, Anderson, Hofman & Watts (Management Science 2016), Fig. 1: "A Schematic Depiction of Broadcast vs. Viral Diffusion, Where Nodes Represent Individual Adoptions and Edges Indicate Who Adopted from Whom." Broadcast is one parent with a large burst of children. Viral is "a multigenerational branching process in which any one node directly 'infects' only a few others." — [Goel et al. 2016 PDF](https://www.5harad.com/papers/twiral.pdf)
- Structural virality ν(T) is "the average distance between all pairs of nodes in a diffusion tree T" (the Wiener index). The authors chose it because plain depth and average depth misclassify broadcast-heavy trees. — [Goel et al. 2016 PDF](https://www.5harad.com/papers/twiral.pdf); paper record: [EconPapers, Mgmt Sci 62(1):180–196](https://econpapers.repec.org/RePEc:inm:ormnsc:v:62:y:2016:i:1:p:180-196)
- That paper's quantitative figures are a log-log CCDF of cascade sizes (Fig. 2) and box plots of structural virality by size on log-log axes (Fig. 5). Cascades are treated "as static objects representing the final state of a given diffusion process," so time is not part of the tree drawing. — [Goel et al. 2016 PDF](https://www.5harad.com/papers/twiral.pdf)
- The authors note that classical diffusion studies (Coleman 1957, Rogers 1962, Bass 1969, Valente 1995) "typically had access to only aggregate diffusion data, such as the cumulative number of adoptions ... over time." That is the cumulative adoption (S-curve) tradition. They also describe the epidemic framing, in which an agent spreads "from 'infectives' ... to 'susceptibles'". — [Goel et al. 2016 PDF](https://www.5harad.com/papers/twiral.pdf)
- Goel, Watts & Goldstein (EC 2012, "The Structure of Online Diffusion Networks") give each tree shape a canonical name, e.g. (x), (x,x), ((x)), and draw small example trees (Fig. 1). They plot the frequency of the most common tree shapes (Fig. 2) and the distribution of adoptions by depth (Fig. 4). Fig. 7 draws the four largest cascades as node-link diagrams: "Colors indicate node depth, with the large, green points corresponding to seed nodes." — [Goel, Watts, Goldstein PDF](https://5harad.com/papers/diffusion.pdf)
- In that EC 2012 data, 73–95% of cascades are only the seed, and just 1–6% of adoptions happen more than one degree from a seed. Shallow trees dominate. — [Goel, Watts, Goldstein PDF](https://5harad.com/papers/diffusion.pdf)
- Cheng, Adamic, Dow, Kleinberg & Leskovec (WWW 2014, "Can cascades be predicted?"):
  - Fig. 1 shows a cascade "represented by solid edges on a graph", with "dashed lines indicat[ing] friendship edges". The cascade tree is overlaid on the underlying social graph.
  - Fig. 3 shows cascades of differing structural virality, with "the root is red".
  - Fig. 2 is a log-scale CCDF of cascade size and structural virality.
  - Fig. 9 compares early cascade configurations (root plus the first three reshares). — [ar5iv 1403.4608](https://ar5iv.labs.arxiv.org/html/1403.4608)
- Cheng et al. find that "early on, breadth matters more than depth" and that temporal features are highly predictive. — [Search summary of arXiv 1403.4608](https://pdf.arxiv.org/pdf/1403.4608); [INFO 2040 blog summary](https://blogs.cornell.edu/info2040/?p=48650)
- Vosoughi, Roy & Aral (Science 2018) compare true and false cascades by depth, size, breadth and speed. One figure plots "the number of minutes it takes for true (green) and false (red) rumor cascades to reach any (E) depth and (F) number of unique Twitter users." Color encodes the cascade's class (veracity), not individuals. — [Mother Jones reproduction](https://adops.motherjones.com/politics/2018/03/new-study-twitter-users-spread-fake-news-farther-and-faster-than-the-truth); [MIT Media Lab record](https://www.media.mit.edu/publications/the-spread-of-true-and-false-news-online/)
- Leskovec et al. ("Cascading Behavior in Large Blog Graphs", SDM 2007) catalogue cascade shapes and find the star is the most common shape. They report that almost every metric follows a power law. — [arXiv 0704.2803](https://arxiv.org/pdf/0704.2803)
- A 2020 critique ("cascade virality") argues that structural virality treats the cascade as an unrooted tree. Its figures draw rooted vs. unrooted cascades with the source colored orange, and they omit arrowheads because the root already implies the direction of flow. — [arXiv 2006.01027](https://arxiv.org/pdf/2006.01027)

**Cumulative adoption (S-curve)**
- Diffusion-of-innovations work plots the accumulated number of adopters over time as an S-shaped curve. One source puts "take-off" at about 10–25% cumulative adoption; another says about 10–20%, and the figures vary by source. — [arXiv 1906.04206](https://arxiv.org/pdf/1906.04206); [Andrew Clark summary](https://andrewclark.super.site/all-media/diffusion-of-innovations)

**Storylines / narrative charts**
- In xkcd #657 "Movie Narrative Charts", x is time, each character is a line, and the vertical grouping of lines shows who is together at each moment. — [xkcd 657](https://xkcd.com/657/); [explain xkcd](https://explainxkcd.com/657)
- Tanahashi & Ma (InfoVis 2012) say that storyline visualizations show "how social interactions change over time" and can reveal both global trends and local interactions. They argue that earlier automatic layouts ignored illustrators' principles, and they optimize layout with evolutionary computation over multiple objectives. — [IEEE VIS 2012 listing](https://ieeevis.org/year/2012/paper/infovis/design-considerations-optimizing-storyline-visualizations)
- Later storyline work lists the standard optimization goals as minimizing "line wiggles, line crossings, and white space." Interactions are encoded by "the convergence and the divergence of two corresponding lines". With many lines, the charts suffer "visual clutter". — [3DStoryline, arXiv 2408.01775](https://arxiv.org/html/2408.01775v1)
- Storyline layout follows Ogawa & Ma's early rules, e.g. that crossings are inevitable but should be avoided where possible. — [Di Bartolomeo et al. 2026 storyline survey](https://www.cg.tuwien.ac.at/research/publications/2026/di_bartolomeo-2026-tss/di_bartolomeo-2026-tss-paper.pdf)
- Storyline charts have been built for every Star Wars episode (FlowingData, 2015), and NLP tools exist that generate xkcd-style charts from screenplays. — [FlowingData](https://flowingdata.com/2015/12/17/timelines-show-star-wars-character-interactions/); [OpenNews Source](https://source.opennews.org/articles/automating-xkcd-style-narrative-charts/)

### Inferences
- **Tree vs. DAG.** If each agent records a single "heard it from" source, the cascade is a tree, as in all the papers above. If an agent hears the message from several people, it becomes a DAG. The usual approach is to draw the first exposure as the tree edge and show later exposures as secondary edges, either dashed or thinner, following Cheng et al.'s dashed-edge convention.
- **Recommended main view: a time-anchored cascade.** Use one swimlane row per agent, in that agent's fixed color, with x as simulation time. Mark the injection with a distinct seed glyph, since every paper highlights the root. Draw secondhand receipt as a curved arrow from the teller's lane to the listener's lane at the time of the conversation. This is effectively a storyline/swimlane hybrid. With 8 lanes, the clutter and crossing problems of storylines are minor, and the fixed-row layout avoids any layout optimization.
- **Small companions.**
  - A cumulative "agents reached" step curve, split into direct vs. secondhand. With n=8 it is a step function rather than a smooth S-curve.
  - A compartment-style stacked area (unaware / heard / changed stance) borrows the epidemic framing. Again, with 8 agents it is coarse and should be drawn as steps.
- **Forms to avoid.** CCDFs, box plots and structural-virality numbers only make sense across many runs. They could appear in a multi-run comparison view, not in a view of a single run.

### Gaps
- I couldn't open the Vosoughi et al. full text to list every figure type or confirm the figure numbers; the cited description comes from a press reproduction. I also couldn't confirm whether its supplement draws cascade trees.
- I couldn't read Tanahashi & Ma's actual list of design considerations; I only have the abstract plus secondary summaries of its goals (wiggles, crossings, white space).
- I found no cited source for a "time-on-x cascade tree" as a named convention in cascade research. The recommendation above is my inference.
- I didn't find a primary source for SIR compartment curves in information-diffusion visualization (beyond the susceptible/infective framing in Goel 2016).

## Q2. How is outcome or attribute (e.g., stance change) encoded on cascade nodes?

### Takeaway
In the cascade papers, node color encodes a structural role (seed/root vs. others, or depth). When color encodes an outcome, it applies to the whole cascade (true vs. false), not to a node. None of the sources showed per-node before/after change. In this dashboard, color is already reserved for agent identity, so stance has to use a second channel.

### Cited Findings
- Seeds are drawn as large green points and other nodes are colored by depth. — [Goel, Watts, Goldstein PDF](https://5harad.com/papers/diffusion.pdf)
- The root is drawn in red. — [Cheng et al., ar5iv](https://ar5iv.labs.arxiv.org/html/1403.4608)
- The diffusion source is drawn in orange. — [arXiv 2006.01027](https://arxiv.org/pdf/2006.01027)
- Cascade class is shown by color: true is green and false is red. — [Mother Jones reproduction of Vosoughi et al.](https://adops.motherjones.com/politics/2018/03/new-study-twitter-users-spread-fake-news-farther-and-faster-than-the-truth)
- Archambault & Purchase study "dynamic attribute cascades", which are node attributes spreading over a graph. Small multiples were significantly faster for judging spread, with no difference in error. Participants preferred animation, and they preferred a hierarchical layout to a force-directed one. — [Monash record](https://research.monash.edu/en/publications/on-the-effective-visualisation-of-dynamic-attribute-cascades/)
- Color works by comparison with neighboring colors and is "surprisingly bad for absolute comparisons." Small, noncontiguous color regions support "only 6-12 bins." — [Munzner, color slides](https://www.cs.ubc.ca/~tmm/courses/547-14/slides/color-stone.pdf); [Munzner, minicourse slides](https://www.cs.ubc.ca/~tmm/talks/minicourse14/vad16bryan.pdf)
- Munzner is quoted in Berinato's *Good Charts* as saying "You don't get more than eight" categorical colors. This is a secondhand quote. — [MPUG article](https://mpug.com/many-colors-many-charts)

### Inferences
- 8 agent colors already uses the whole safe categorical budget. Stance (before/after) should therefore not get more hues. It can be encoded by:
  - position, such as a small diverging stance scale (against / neutral / for) drawn as a before→after slope or dumbbell per agent row;
  - glyph shape or fill, such as a hollow ring for before and a filled ring for after;
  - a neutral grey-to-black luminance ramp;
  - arrow direction.
- A dumbbell or slope chart with one row per agent (left = before stance, right = after stance, row tinted in the agent's color) reads more clearly than coloring tree nodes. Changers stand out by line length or angle.
- Any "seed" or "direct vs. secondhand" status should use shape or stroke style (seed = star or diamond; secondhand edge = dashed), following the root-highlight convention without spending a hue.

### Gaps
- None of the sources showed per-node before/after attribute change on a cascade. The encoding above is inferred from general color-budget guidance.

## Q3. How should a small (8-node) network be drawn: node-link vs. matrix, edge weights, change over time, egocentric views?

### Takeaway
For a small, sparse graph like 8 agents, node-link is the empirically preferred form (Ghoniem et al.). Matrices win only when graphs are larger or denser. Beck et al.'s survey makes the depiction of time the main design choice for dynamic graphs: animation or timeline (static). Studies find small multiples faster than animation, with mixed accuracy results.

### Cited Findings
- **Node-link vs. matrix.**
  - Ghoniem, Fekete & Castagliola (InfoVis 2004) compared the two forms on seven generic tasks. For graphs with more than about 20 vertices, matrices outperformed node-link on most tasks; path finding was the exception, and node-link won it. — [dblp](https://dblp.org/rec/conf/infovis/GhoniemFC04); [Fekete, "Visualization of Graphs" slides](https://aviz.fr/~fekete/Visualization%20of%20Graphs.pdf)
  - The journal version (Information Visualization 4(2), 2005) concludes that node-link is preferable for small, sparse graphs, and matrices are more readable for dense and medium/large graphs except for path finding. — [BibBase record](https://bibbase.org/network/publication/ghoniem-fekete-castagliola-acomparisonofthereadabilityofgraphsusingnodelinkandmatrixbasedrepresentations-2004) (I read abstracts and secondary slides, not the full text)
- **Dynamic graphs, Beck et al. 2017** (Computer Graphics Forum 36(1):133–159).
  - The survey identifies "the representation of time as the major distinguishing feature for dynamic graph visualizations", ahead of node-link vs. matrix. Its top-level split is animated diagrams vs. static timeline-based charts.
  - Evaluations of animation focus on "dynamic stability for preserving the viewer's mental map", or they compare animation with timelines. — [Uni Duisburg-Essen record](https://vis.informatik.uni-due.de/en/publications/a-taxonomy-and-survey-of-dynamic-graph-visualization-13409); [EG Digital Library](https://diglib.eg.org/handle/10.1111/cgf12791)
- **Animation vs. small multiples, Archambault, Purchase & Pinaud (TVCG 2011).**
  - Small multiples were faster than animation on all five tasks.
  - Small multiples had more errors on questions about which nodes or edges appeared at the same time.
  - Preserving the mental map had little effect on errors or time. — [Monash record](https://research.monash.edu/en/publications/animation-small-multiples-and-the-effect-of-mental-map-preservati/)
- **Archambault & Purchase (Information Sciences 2016).** There was no significant overall difference between animation and small multiples. Animation helped when drawing stability was low and important nodes could not be highlighted across time. — [Swansea Cronfa 20860](https://cronfa.swansea.ac.uk/Record/cronfa20860)
- **Edge crossings.**
  - Purchase's studies find edge crossings "by far the most important aesthetic" for understanding graph structure.
  - Later work by Ware et al. shows that for path tasks, what matters is crossings on the path itself.
  - The impact of crossings may be negligible for small graphs with large crossing angles. — [Eye-tracking study, arXiv 0810.4431](https://arxiv.org/pdf/0810.4431); [Purchase et al., "Graph drawing aesthetics—created by users, not algorithms"](https://www.cs.auckland.ac.nz/~beryl/publications/AUIC%202010%20Graph%20drawing%20aesthetics.pdf)

### Inferences
- **Who-talks-to-whom, aggregate.** With 8 nodes (28 possible pairs), a node-link diagram in a fixed circular layout is the natural choice: stable, crossings tolerable, agents in their colors. Edge width encodes conversation count. An 8×8 matrix heatmap, with rows and columns labeled by colored agent chips, is a compact alternative. It has no crossings, it shows exact counts, and it scales if the town grows. The Ghoniem results suggest node-link for 8 agents, but because the graph may be dense (most pairs talk), a matrix is reasonable too.
- **Change over time.** A fixed layout removes the mental-map problem entirely. Small multiples per day or time window, or a timeline (a time × pair heat strip, or a pair-lane timeline), follow Beck's timeline branch and the speed advantage found for small multiples. If animation is used, it should be a scrubber over a fixed layout, not a re-running force layout.
- **Egocentric view.** On selecting an agent, highlight its edges and fade the rest. This is a cheap way to answer "whom did X talk to" without a separate chart.

### Gaps
- I couldn't retrieve Beck et al.'s full text (403/DNS failures), so I'm missing its specifics on egocentric views, edge-weight encodings, and juxtaposed vs. superimposed timelines.
- I didn't find a primary empirical source on edge-width encoding of weights in small networks.

## Q4. Pitfalls: hairballs, edge crossings, layout instability, color overload

### Takeaway
At 8 agents, hairballs and scalability are not real risks. The real risks are layout instability over time (if a force layout re-runs), colors carrying two meanings (identity vs. stance or cascade role), and storyline or arrow clutter if every conversation, not just message-carrying ones, is drawn.

### Cited Findings
- **Mental map.** Preserving the mental map (layout stability) is the main concern in evaluations of animated dynamic graphs. — [Beck et al. record](https://vis.informatik.uni-due.de/en/publications/a-taxonomy-and-survey-of-dynamic-graph-visualization-13409)
- **Stability evidence.** In one study, mental-map preservation had little measured effect on errors or time. — [Archambault et al. 2011](https://research.monash.edu/en/publications/animation-small-multiples-and-the-effect-of-mental-map-preservati/) Animation helped specifically when drawings were unstable. — [Archambault & Purchase 2016](https://cronfa.swansea.ac.uk/Record/cronfa20860)
- **Crossings.** Crossings are the most damaging aesthetic in general, though less so for small graphs with large crossing angles. — [arXiv 0810.4431](https://arxiv.org/pdf/0810.4431)
- **Storylines.** Many lines cause "visual clutter and obscured visualization". — [arXiv 2408.01775](https://arxiv.org/html/2408.01775v1)
- **Color.** There are only about 6–12 usable categorical bins for small scattered marks. — [Munzner slides](https://www.cs.ubc.ca/~tmm/courses/547-14/slides/color-stone.pdf) The quote "you don't get more than eight" is attributed to Munzner secondhand. — [MPUG](https://mpug.com/many-colors-many-charts)
- **Layout choice for cascades.** For dynamic attribute cascades, users preferred hierarchical over force-directed layouts. — [Monash record](https://research.monash.edu/en/publications/on-the-effective-visualisation-of-dynamic-attribute-cascades/)

### Inferences
- Keep agent color as the only hue channel across every chart: lanes, nodes, matrix labels and edges. Encode role (seed/direct/secondhand) with shape or dash, and stance with position or luminance. Use a single accent (e.g. a neutral highlight) for "message" edges, so they don't compete with agent colors.
- In the network view, separate "talked" edges (all conversations, thin and grey or tinted) from "transmitted the message" edges (emphasized), or the cascade gets lost in general chatter.
- Prefer deterministic layouts (fixed circle, fixed lane order) over force-directed ones. They keep positions identical across runs and time steps, which matters for a live-updating dashboard.

### Gaps
- I found no network-specific empirical study of hairball thresholds; the hairball concern at this scale is inferred as negligible.
