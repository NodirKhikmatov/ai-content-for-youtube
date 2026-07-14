# AI Content Studio — Strategic & Technical Blueprint
*South Korea-based, globally-distributed autonomous content system. Prepared 2026-07-14.*

---

## 0. Where I'm pushing back before we design anything

You asked me to challenge assumptions instead of agreeing. Here are five places where your brief, taken literally, points at a worse outcome than you probably want — backed by the research below, not vibes.

**1. "Generate videos that look natural" is the wrong optimization target — it's a compliance liability, not a feature.**
YouTube's 2026 disclosure rule requires the "Altered or synthetic content" label specifically when AI content *could be mistaken for real footage* — a synthetic human, an altered real event, a realistic scene that didn't happen. The more "natural" your output looks, the more disclosure obligations and detection risk you accumulate, for zero revenue upside (disclosure doesn't reduce CPM, but getting caught *not* disclosing something disclosure-worthy is a strike). Meanwhile the actual top earners in this space (Bright Side — 45M subs, $23K–75K/mo; DaFuq Boom — $500K–1.3M/mo; NexLev's court-case channels) are not photoreal synthetic-human content at all. They're narrated documentary/B-roll/motion-graphics formats. "Natural-looking" and "profitable" are not the same axis — don't spend engineering effort chasing photorealism.

**2. "Autonomous" and "minimal human input" are literally the disqualifying language in YouTube's policy.**
The inauthentic-content policy explicitly flags "videos created entirely by bots, scripts, or software with minimal human input" and enforces via a three-strike system — 16 channels, 4.7B lifetime views, ~$10M/yr in ad revenue were removed in a single January 2026 sweep. If you build a system whose explicit goal is *zero human judgment in the loop*, you are architecting exactly the thing enforcement is tuned to find. The fix isn't to fake human involvement — it's to make a real editorial/originality decision a structural, auditable part of the pipeline (see the Originality & Angle Agent and the Compliance Agent below), not a rubber stamp.

**3. Treating YouTube, Instagram, and TikTok as three equal legs of a stool is wrong for this strategy specifically.**
- **YouTube**: highest RPM ceiling (finance $7–25 RPM, drama/betrayal $12.82, education $10–25), API-cheap to publish (upload quota dropped from ~1600 to ~100 units in Dec 2025 — up to 100 uploads/day on default quota), but currently running active, aggressive automation enforcement.
- **TikTok**: requires visible AI labeling (1.3B videos already labeled, C2PA-based detection, 4-tier penalties) but is *comparatively tolerant* of labeled AI content if retention holds (70%+ completion rate is now the viral threshold). RPM is low ($0.40–2.00/1000 views) — treat it as a distribution/funnel channel, not a revenue channel.
- **Instagram**: Adam Mosseri stated in his 2026 year-end memo that IG will explicitly prioritize "raw, real human content" over AI material this year. Reels reach already fell 31–35% YoY, accounts with 10+ reposts/30 days are excluded from recommendations entirely, and RPM is the worst of the three ($0.01–0.12/1000 views via Reels bonus). **For an AI-content-first strategy, Instagram is currently the weakest of the three platforms by policy direction, reach, and economics.** I'd deprioritize it in the MVP and revisit only once you have a proven format and are willing to invest in genuinely non-automated-feeling IG-native execution.

**4. Multi-channel scaling the way "faceless YouTube" courses teach it (20 templated channels, one operator) is the exact network signature enforcement targets.**
NexLev-style "20 channels, same pipeline" is held up as a success story in the marketing material, but a single-sweep removal of 16 channels strongly implies cross-channel pattern detection is already live. The lesson isn't "don't scale channels" — it's "don't clone the same production template across channels." Each channel needs a genuinely distinct editorial voice, research depth, and production pipeline, not a find-and-replace niche swap. I've built this into the roadmap (Phase 3) rather than the architecture (portfolio strategy is a business decision, not a per-video agent).

**5. "Maximize long-term monetization" and "the video generation model" are not the same problem — don't over-invest in the commodity layer.**
Sora 2 launched and was fully deprecated within about six months (API shutdown Sept 2026). Video-gen models are churning on a 3–6 month cycle. If your architecture treats "Video Generation Agent" as your core IP, you're building on the fastest-depreciating layer in the stack. The actual moat — the thing that doesn't get commoditized by the next model release — is the research/originality/fact-checking/storytelling layer that decides *what's worth making and why it's different from the 500 other videos on this topic*. The architecture below treats video/voice generation as swappable backends behind an interface, and elevates research + originality scoring to first-class pipeline stages.

None of this means the ambition is wrong — it means: bias toward genuinely differentiated, narrated, documentary-style long-form as the core product, use short-form as a distribution funnel not a revenue center, keep a real (if lightweight) human/judgment checkpoint even at full scale, and build for model churn rather than around one vendor.

---

## 1. Platform research — what's actually true right now

### 1.1 YouTube Partner Program (2026)

**Eligibility (two-tier, confirmed current):**
| Tier | Requirement |
|---|---|
| Early access (fan funding) | 500 subs + 3 public uploads in 90 days + (3,000 long-form watch hours in 365 days OR 3M Shorts views in 90 days) |
| Full monetization (ads) | 1,000 subs + 4,000 watch hours in 12 months, OR 1,000 subs + 10M Shorts views in 90 days |

**The policy that matters most: "Inauthentic content" (renamed from "repetitious content," effective July 15 2025, first major enforcement wave January 2026).**
- Defined as mass-produced or template-driven content with little to no variation, or content that's "easily replicable at scale" — the test is whether your videos are *interchangeable with each other*, not whether AI was used.
- Explicitly named disqualifiers: bot/script-generated videos with minimal human input, auto-generated slideshows, verbatim TTS-over-stock-footage with no POV, bulk-uploaded near-duplicates, compilations with no commentary/context, unedited reposts.
- Enforcement: three-strike system — warning → 90-day suspension → permanent PVP removal. January 2026 sweep: 16 channels, 4.7B lifetime views, ~$10M/yr ad revenue removed in one pass.
- **What still monetizes fine**: AI-assisted or AI-generated content that offers "original value" — meaningful commentary, narrative structure, editing, creative choices — with the "Altered or synthetic content" disclosure toggled on when the content could be mistaken for real footage/events. AI is not the trigger; formulaic low-effort production is.
- **Reused content policy is unchanged** — commentary, clips, compilations, and reaction content with real added value remain eligible; the July 2025 update did not touch this.
- **Low-value content** (separate but overlapping category): content that just reads off a webpage/news feed, slideshows with no narrative/educational value, low-effort filtered/cropped/sped-up reposts.
- **Limited ads triggers**: content depicting real people without consent, medical/financial advice framing, anything that could mislead about current events, overused/generic TTS voices paired with copy-paste scripts (July 2025 update specifically targeted this combination).
- **Copyright**: pure AI output cannot be copyrighted (US Supreme Court declined *Thaler v. Perlmutter* cert, March 2026 — lower-court "AI can't hold copyright" rulings stand). Content that wraps AI-generated elements in human-authored scripts, voice direction, and editing remains on solid ground for both copyright *and* platform policy.

### 1.2 Instagram (2026)

- **Ranking signals** (Mosseri-confirmed): watch time (now measured as total watch time + replay rate, not just 3-second view count) > sends-per-reach (DM shares, worth 3–5x a like for reaching new audiences) > likes-per-reach (matters more for existing followers).
- **Strategic pivot**: Mosseri's year-end memo explicitly states IG will prioritize "raw, real human content" over AI material through 2026. Reels reach fell 31–35% YoY (avg reach 14,922 → 9,689). Increasing post volume made things *worse* for accounts tracked by Metricool (21% more posting, lower reach/engagement) — saturation is actively penalized.
- **Repost/originality penalty**: original content gets 40–60% more distribution than reposts; 10+ reposts in 30 days = full exclusion from recommendations.
- **Monetization**: 55/45 creator/Meta revenue share on Reels ads; Reels Play Bonus 2.0 pays $0.03–$0.12/1000 views across engagement+retention+conversion tiers — the lowest RPM of the three platforms by a wide margin.
- **Verdict**: structurally the worst-fit platform for an AI-content-first strategy right now. Treat as optional/future, not core.

### 1.3 TikTok (2026)

- **Creator Rewards Program eligibility**: 10,000 followers, 100,000 views in last 30 days, 18+, eligible region, good standing, original content (no duets/stitches/reposts), videos ≥60 seconds to qualify for the higher-paying tier.
- **RPM**: $0.40–$2.00/1000 qualified views, driven by originality, play duration, engagement, and "search value" (does the video answer something people search for on TikTok).
- **Algorithm**: completion rate is ~40–50% of ranking weight. The viral threshold moved from a ~50% completion baseline (2024) to over 70% in 2026 — below that, videos rarely clear 10K views; above it, distribution is close to unbounded. New videos are now follower-tested before non-follower push (2026 change). Shares/saves now outrank likes.
- **AI content policy**: mandatory visible labeling for AI-generated realistic faces/voices/scenes, enforced via C2PA Content Credentials plus automated detection (detection accuracy 18%→35-45% over 2024–2025). 1.3B videos already labeled; 52% of all TikTok content has some AI element — meaning labeled AI content is now *normal*, not a scarlet letter, as long as it's disclosed. Four-tier penalty system for unlabeled synthetic media (51,618 removals in H2 2025).
- **Posting cadence**: 1–4x/day; new accounts benefit from higher frequency (2–3x/day) for algorithm signal, established accounts can taper to ~1/day; >5/day shows diminishing returns.

### 1.4 Platform comparison

| Factor | YouTube (long-form) | TikTok | Instagram Reels |
|---|---|---|---|
| RPM ceiling | $7–25 (up to $25+ finance/legal) | $0.40–2.00 | $0.01–0.12 |
| AI-content policy stance 2026 | Tolerant if original value; aggressive enforcement on templated/low-effort | Tolerant if labeled + retention holds | Actively de-prioritizing AI content |
| Reach trend | Stable/growing for quality long-form | Strong, algorithm-driven | Declining 31–35% YoY |
| Automation-friendliness | High (cheap API, but policy risk on templating) | Medium (labeling overhead) | Low (repost penalties, human-content bias) |
| Role in this system | **Primary revenue engine** | **Distribution/funnel** | **Deprioritized / future** |

---

## 2. Which content type wins on all four axes

Not a hedge — a ranked answer:

1. **Highest overall (viral + monetized + scalable + durable): narrated, research-backed long-form documentary/story format (8–15 min) on YouTube, repurposed into short-form cuts for TikTok/Shorts.** This is the actual pattern behind every large faceless-channel success case in the research (Bright Side, DaFuq Boom, Daily Dose of Internet, NexLev's court-case channels — one video cost $250 to produce and made $20K+ from 5M views). It scores well because: (a) long watch time + premium-CPM topic categories (finance/legal/true-crime/education) directly drive RPM, (b) the format tolerates and rewards genuine research/POV, which is your durability moat against both algorithm changes and policy enforcement, (c) it's naturally sliceable into short-form clips for TikTok distribution without separate production.
2. **Highest pure virality, weakest monetization: hook-driven 15–45s vertical clips (TikTok/Shorts).** Necessary for discovery and audience-building, structurally low RPM, best treated as top-of-funnel that feeds subscribers to the long-form channel, not a revenue line itself.
3. **Highest automation ease, lowest durability: templated compilation/listicle/quote content.** Cheapest to produce, but this is *precisely* the shape of content named in YouTube's inauthentic-content examples and is most exposed to the next enforcement wave. Do not build the MVP around this even though it looks like the easy win.
4. **Worst risk-adjusted bet: photorealistic synthetic-human "AI influencer" talking-head content.** Highest production cost and complexity, highest disclosure/detection exposure on YouTube, actively penalized by Instagram's 2026 stance, and not what the actual top earners are doing. Skip it.

---

## 3. 20 content niches, ranked

Scale: Competition & Automation Difficulty (Low is good), CPM/RPM & Viral Potential & Sustainability (High is good).

| # | Niche | Competition | CPM/RPM | Viral Potential | Automation Difficulty | Long-term Sustainability | Notes |
|---|---|---|---|---|---|---|---|
| 1 | Personal finance / investing explainers | High | Very High ($15–50 CPM) | Medium | Medium | High | Best RPM ceiling; needs real fact-checking to avoid "financial advice" limited-ads trigger |
| 2 | True crime / court case narration | Medium-High | High | High | Medium | High | Proven model (NexLev); needs strong sourcing to avoid misinformation flags |
| 3 | History deep-dives / "what if" scenarios | Medium | High | Medium | Medium | Very High | Evergreen, low regulatory risk, ages well |
| 4 | Legal case breakdowns ("you won't believe this lawsuit") | Medium | High | High | Medium | High | Overlaps #2; strong hook potential |
| 5 | Reddit story narration (relationship/betrayal/revenge) | High | High ($12.82 RPM data point) | Very High | Low | Medium | Cheap to produce but crowded and template-risk if not reworked editorially |
| 6 | AI tools & productivity news | Medium | High ($10–25) | High | Low | Medium | Fast-moving beat = easy trend pipeline, but short shelf life per video |
| 7 | Real estate & wealth-building | Medium | High | Low-Medium | Medium | High | Steady advertiser demand, less viral, strong long-tail search traffic |
| 8 | Psychology & self-improvement | High | Medium-High | Medium | Medium | High | Durable, but very competitive; needs a genuine POV to stand out |
| 9 | Cybersecurity / scam awareness explainers | Low-Medium | Medium-High | Medium | Medium | High | Underserved niche, strong advertiser fit, evergreen |
| 10 | Health & longevity science explainers | Medium-High | High | Medium | High | High | High CPM but heavy fact-checking burden (medical-advice limited-ads risk) |
| 11 | B2B SaaS / tech explainers | Low | High | Low | Medium | High | Small audience, high advertiser value; good for a second, non-viral channel |
| 12 | English learning / language learning content | Medium | High ($11.88 RPM data point) | Medium | Low | Very High | Global audience matches your South-Korea-based/global-English brief well |
| 13 | Space & science documentaries | Medium | Medium-High | Medium | Medium | Very High | Evergreen, strong watch time, moderate competition |
| 14 | Biography / "life story of X" | Medium | Medium | Medium | Medium | High | Durable format, needs strong research agent to avoid factual-error risk |
| 15 | Mythology & folklore storytelling | Low-Medium | Medium | Medium | Low | High | Underused, good fit for narrative/storytelling-agent strength |
| 16 | Sports history / documentary | Medium | Medium | Medium | Medium | High | Passionate niche audiences, decent CPM, seasonal spikes |
| 17 | Product review / gadget explainers | High | Medium | Medium | High | Medium | Needs real hands-on testing data to avoid low-value flag; hard to automate honestly |
| 18 | Kids/family animated stories | Very High | Medium (COPPA-restricted ads) | High | High | Medium | Huge market (Cocomelon) but COPPA kills targeted-ad CPM and raises compliance overhead |
| 19 | Conspiracy-adjacent mystery/unsolved | Medium | Low-Medium | High | Low | **Low** | High misinformation-policy exposure; explicitly avoid as a primary niche |
| 20 | Motivational/quote compilations | Very High | Low | Low | Very Low | **Very Low** | This is the literal template YouTube's inauthentic-content policy describes; do not build here |

**Recommendation for your MVP channel: #1 (finance), #2/#4 (true crime/legal), or #12 (English learning)** — pick based on your own domain knowledge, since the fact-checking and originality layer is your moat and works best where you can personally sanity-check output quality early on.

---

## 4. Multi-agent architecture

Design principle from Section 0: research/originality/compliance are first-class pipeline stages, not afterthoughts; video/voice generation are swappable backends behind an interface; there is always at least one genuine judgment checkpoint before publish.

### Pipeline overview

```
STRATEGY        Trend Research → Competitor Intelligence → Portfolio Strategy
                        │
RESEARCH        Deep Research → Fact Checker → Originality & Angle
                        │
CREATION        Script Writer → Storytelling Structure → SEO/Metadata → Thumbnail
                        │
HUMANIZATION    Humanization & Voice-Style
                        │
PRODUCTION      Voice Synthesis → Video/Visual Generation → Sound Design
                    → Video Assembly → Subtitle/Caption
                        │
QA/COMPLIANCE   Quality Review → Copyright/Content-ID Risk → Policy/Monetization Compliance
                        │
DISTRIBUTION    Cross-Platform Repurposing → Publishing/Scheduling
                        │
GROWTH LOOP     Analytics → A/B Testing → Learning/Optimization  ──▶ feeds back to Strategy
```

An **Orchestrator (Supervisor) Agent** owns this as a Temporal workflow / LangGraph state graph — not a plain pipeline. It handles retries, branching (e.g., Fact Checker rejection routes back to Deep Research, not forward), and holds the human-approval signal wait at MVP stage.

### 4.1 Strategy layer

**Trend Research Agent**
- *Inputs*: platform trend APIs, Google Trends, competitor channel RSS/API pulls, Reddit thread signals.
- *Outputs*: ranked list of candidate topics with a novelty score and a projected-CPM-niche tag.
- *Prompt strategy*: structured extraction, not open generation — force the model to cite the specific signal (search volume delta, competitor upload spike, subreddit thread velocity) behind each candidate.
- *Memory*: rolling 90-day vector store of past-covered topics (critical: this is what prevents you from re-covering the same angle and tripping the "interchangeable videos" test).
- *Tools*: YouTube Data API (search/trending), Google Trends API, Exa/Tavily search, Reddit API (PRAW), SerpAPI.
- *Decision logic*: reject any topic with >0.85 cosine similarity to something published in the last 90 days unless a genuinely new angle is proposed.
- *Failure handling*: if all candidates fail novelty threshold, escalate to Portfolio Strategy Agent rather than force a low-quality pick.

**Competitor Intelligence Agent**
- *Inputs*: channel list per niche, their recent uploads (title/thumbnail/transcript/view velocity).
- *Outputs*: gap analysis — what's covered, what's saturated, what's under-served.
- *Tools*: YouTube Data API, yt-dlp for transcript pulls, vision model for thumbnail pattern analysis.
- *Memory*: per-competitor embedding history to detect when a niche is getting crowded.
- *Failure handling*: stale/rate-limited API falls back to cached data with an explicit staleness flag surfaced downstream — never silently serve old data as fresh.

**Portfolio Strategy Agent** *(new — not in your original list)*
- *Inputs*: outputs of both agents above, current per-channel performance from Analytics, current channel/niche map.
- *Outputs*: which channel (or "new channel") a topic should be routed to, and explicit instruction to vary production style if this is a second+ channel in a niche cluster.
- *Decision logic*: this is where the "don't clone the same template across channels" rule from Section 0 gets enforced structurally — it will not route two channels to identical script/voice/pacing configs.
- *Failure handling*: if no channel fits and a new channel isn't justified by data, defer the topic rather than force-fit it.

### 4.2 Research layer

**Deep Research Agent**
- *Inputs*: selected topic from Strategy layer.
- *Outputs*: structured research brief — claims, sources, counterpoints, a specific "why this angle, why now" thesis.
- *Prompt strategy*: multi-pass — first gather, then a separate pass explicitly instructed to find disconfirming evidence (reduces one-sided narrative risk that both hurts quality and raises misinformation exposure).
- *Tools*: Exa/Tavily/Perplexity API, primary-source fetch via WebFetch-equivalent, Reddit/forum sentiment.
- *Memory*: citation store in the vector DB, reusable across future related topics.
- *Failure handling*: if source count or source diversity falls below threshold, route to Fact Checker with a low-confidence flag rather than proceeding silently.

**Fact Checker Agent**
- *Inputs*: research brief + draft script (runs twice: pre-script and post-script).
- *Outputs*: per-claim verdict (verified / disputed / unverifiable) with source links.
- *Decision logic*: any "disputed" or "unverifiable" claim tied to medical/financial/legal advice or real-person allegations blocks the pipeline — hard stop, not a warning (this is what protects you from the "Limited Ads" triggers named in Section 1.1).
- *Failure handling*: on tool failure (search API down), do not default to "assume true" — pipeline pauses and escalates.

**Originality & Angle Agent** *(new — this is your compliance/quality moat)*
- *Inputs*: draft script + Trend Research's novelty score + full corpus of your own past scripts.
- *Outputs*: a pass/fail plus a rewrite directive if the script is structurally too similar to prior output (same intro pattern, same pacing template, same conclusion format).
- *Decision logic*: explicitly modeled on YouTube's "interchangeable content" test — measures structural similarity (not just topical), because that's literally what the policy checks for.
- *Memory*: embeddings of full script structure (not just topic) across channel history.
- *Failure handling*: on failure, forces a human-review flag rather than auto-approving — this agent is not allowed to fail open.

### 4.3 Creation layer

**Script Writer Agent** — *Inputs*: approved research brief. *Outputs*: full narration script with scene/beat markers. *Prompt strategy*: constrained to the Storytelling Agent's structural template but required to vary sentence rhythm/hook phrasing per the Humanization Agent's style guide. *Memory*: channel voice/style guide. *Tools*: Claude Opus (best factual grounding per benchmarks). *Failure handling*: length/pacing validation (words-per-minute vs target runtime) before handoff; auto-retry with explicit trim/expand instruction.

**Storytelling/Narrative Structure Agent** — *Inputs*: research brief. *Outputs*: beat sheet (hook → stakes → escalation → payoff), independent of the Script Writer so structure and prose are decoupled and can be varied independently (supports the Originality Agent's job). *Decision logic*: enforces a strong-hook-in-first-8-seconds rule, mapped directly to TikTok's 70%-completion retention data even for YouTube content, since the same principle drives YouTube average-view-duration.

**SEO & Metadata Agent** — *Inputs*: final script + competitor title/tag data. *Outputs*: title variants, description, tags, chapters. *Tools*: YouTube Data API for competitor SERP data. *Decision logic*: rejects clickbait-mismatch titles (title claims not supported by the fact-checked script) — this is both an ethics and a policy-risk gate (misleading-viewers is an explicit Limited-Ads trigger).

**Thumbnail Agent** — *Inputs*: script beats, channel style guide. *Outputs*: 3–5 thumbnail candidates. *Tools*: image-gen model + vision-model self-critique pass (contrast, face-size, text-legibility at small size). *Memory*: past thumbnail CTR data from Analytics feeds back into style weighting.

**Humanization & Voice-Style Agent** — *Inputs*: draft script. *Outputs*: edited script with deliberate imperfections/personality/varied cadence — this is not about "sounding human to evade detection," it's about actually not being formulaic, which is the real policy target. *Decision logic*: varies opening-line pattern, transition phrasing, and pacing per video against a rotating template pool, specifically to defeat the Originality Agent's own similarity check (adversarial pairing between these two agents is intentional).

### 4.4 Production layer

**Voice Synthesis Agent** — *Inputs*: final script. *Outputs*: timed audio track. *Tools*: ElevenLabs (primary, quality benchmark) with Fish Audio/Chatterbox as a cost-controlled fallback for lower-tier content. *Decision logic*: rotates among a pool of licensed voices per channel (never one static voice reused verbatim across all videos — another "interchangeable content" defense). *Failure handling*: on API failure/quota, falls back to secondary TTS vendor rather than blocking the pipeline, flags the substitution for review.

**Video/Visual Generation Agent** — *Inputs*: scene list from script. *Outputs*: B-roll clips, motion graphics, stock-footage matches. *Tools*: abstracted interface over Veo 3.1 (hero shots, native audio) and Kling 3.0 (cheap bulk B-roll, $0.10/s) — **built behind a vendor-agnostic interface specifically because Sora 2 was deprecated ~6 months after launch; do not hard-code a single video-gen vendor anywhere in this agent.** *Decision logic*: routes shot complexity/importance to the appropriate cost tier.

**Sound Design Agent** *(new)* — *Inputs*: assembled scene timeline. *Outputs*: music bed + SFX layer. *Tools*: licensed music API (e.g., Artlist) + Claude for mood-matching to scene beats. *Decision logic*: retention-driven — flags any 20+ second stretch with no audio variation as a retention risk before it reaches QA.

**Video Assembly/Editor Agent** *(new)* — *Inputs*: voice track, visuals, sound design, subtitle timing. *Outputs*: assembled cut. *Tools*: ffmpeg + Remotion (programmatic, code-driven assembly — good fit given you're a full-stack dev already). *Decision logic*: enforces pacing rules derived directly from the TikTok retention data (cut frequency, no dead air >3s, hook must land in first 8s) even on long-form YouTube cuts, since these principles transfer.

**Subtitle/Caption Agent** — *Inputs*: audio track. *Outputs*: burned-in + soft-sub caption files per platform. *Tools*: WhisperX/Deepgram for forced alignment. *Failure handling*: word-error-rate check against source script; anything above threshold routes to manual correction, not auto-published.

### 4.5 QA & compliance layer

**Quality Review Agent** — *Inputs*: assembled video + all upstream artifacts. *Outputs*: pass/fail + annotated issue list. *Decision logic*: LLM-as-judge using Gemini 3.1 Pro (native video understanding) against a rubric (pacing, factual consistency with script, visual-audio sync, brand style). *Failure handling*: **this is your MVP-stage human-in-the-loop gate** — auto-pass threshold starts very high (only near-perfect scores skip human review) and is loosened only as track record accumulates (see roadmap).

**Copyright/Content-ID Risk Agent** — *Inputs*: all visual/audio assets. *Outputs*: risk score per asset. *Tools*: reverse-image/audio fingerprint check against Content ID-adjacent databases, music licensing verification. *Decision logic*: hard block on any real-person likeness without clear parody/commentary framing or consent context, per the Screen Culture/KH Studio case (demonetized for undisclosed fake AI trailers) — this is exactly the failure mode to design against.

**Policy/Monetization Compliance Agent** — *Inputs*: final video + metadata + all agent decision logs. *Outputs*: monetization-risk verdict mapped explicitly to YouTube's named categories (inauthentic, reused, low-value, limited-ads triggers) from Section 1.1. *Decision logic*: this agent's prompt is literally built from YouTube's own policy language, checked as a structured rubric, not a vibe check — including whether the "Altered or synthetic content" disclosure toggle should be set. *Memory*: maintains a running log of every decision, because if a channel is ever audited/appealed, you want an evidentiary trail showing genuine editorial process, not just "the AI said it's fine."

### 4.6 Distribution layer

**Cross-Platform Repurposing Agent** *(new)* — *Inputs*: long-form final cut + transcript. *Outputs*: 3–6 short-form clips per long-form video, reformatted per platform (9:16, caption style, hook-first trim). *Decision logic*: selects clip boundaries using the retention/completion-rate curve from Analytics (cut where long-form retention is highest), not arbitrary timestamps.

**Publishing/Scheduling Agent** — *Inputs*: final assets per platform. *Outputs*: scheduled/published posts. *Tools*: YouTube Data API v3 (prefer official API — now cheap at ~100 quota units/upload) for YouTube; TikTok Content Posting API; Playwright/browser-use only as a fallback for anything without a stable API, and never for the primary publish path (write actions via browser automation are fragile and more ToS-sensitive than official APIs). *Decision logic*: staggers cross-platform posting (not simultaneous identical drops) and randomizes posting windows within a target range rather than a fixed cron minute — both because it matches real-creator behavior and because rigid timing is itself a template signal.

### 4.7 Growth loop

**Analytics Agent** — *Inputs*: platform analytics APIs (YouTube Analytics, TikTok, IG). *Outputs*: structured performance dataset joined back to the video's full agent-decision trail (which topics, angles, hooks, thumbnails worked).

**A/B Testing Agent** *(new)* — *Inputs*: thumbnail/title variant sets. *Outputs*: statistically-gated winner selection (not "first one that looks good") using YouTube's native A/B test tools where available.

**Learning/Optimization Agent** — *Inputs*: Analytics + A/B results over a rolling window. *Outputs*: prompt/weight adjustments fed back to Strategy-layer and Creation-layer agents (e.g., "hooks framed as questions are outperforming statement hooks by 22% this month, adjust Storytelling Agent's default"). *Decision logic*: requires a minimum sample size before acting on a signal — explicitly guards against overfitting to noise on a small channel.

---

## 5. System architecture

### 5.1 Orchestration & durability
- **LangGraph** as the agent state machine — production default in 2026 (checkpointing, typed state, human-in-the-loop interrupts, used in production at Klarna/Uber/LinkedIn). Each agent above is a node; conditional edges implement the retry/escalation logic described per-agent.
- **Temporal** as the durable workflow layer wrapping the whole per-video pipeline — because a single video's lifecycle spans hours to days, needs to survive restarts, and needs to *wait* on human-approval signals (MVP stage) without holding compute. Temporal's signal/wait model maps directly onto your "human review gate."
- Lightweight, independent fan-out jobs (e.g., generating 5 thumbnail variants in parallel) can go through a simple Redis+BullMQ queue rather than full Temporal workflows — don't over-engineer the small stuff.

### 5.2 Data layer
- **Postgres** (Neon or Supabase to start) — channels, videos, agent run logs, decision audit trail, performance metrics. The audit trail matters concretely: if a channel gets flagged, you want to show real editorial process.
- **Vector DB — Qdrant (self-hosted)**: past scripts (structural embeddings for the Originality Agent), research citations, competitor content, audience comment sentiment. Chosen over Pinecone because at your scale (single operator, low double-digit millions of vectors at most for years) self-hosted Qdrant's cost and native hybrid search (vector + metadata filtering) beat paying for managed simplicity you don't need yet. Revisit Pinecone only if you outsource ops entirely.
- **Object storage — Cloudflare R2** for video/audio assets — S3-compatible API, zero egress fees (materially cheaper than S3 at video-file scale).

### 5.3 LLM routing (don't commit to one vendor)
| Task class | Model | Why |
|---|---|---|
| Script writing, fact-checking, compliance judgment, originality scoring | Claude Opus 4.8 | Best human-preference/factual-grounding ranking, SWE/reasoning benchmarks lead |
| Bulk/high-volume (trend scanning, competitor summarization), video/vision understanding, long-context transcript analysis | Gemini 3.1 Pro | ~7x cheaper per request, native video understanding, strong long-context |
| Agentic/tool-use heavy steps (browser automation reasoning, multi-step API orchestration) | GPT-5.5 | Leads CLI/agentic-autonomy benchmarks |

This tiered routing (research finding: "routing each task to its best-and-cheapest fit... often beats committing to a single provider") is also your cost-control mechanism — reserve the expensive model for the handful of steps where judgment quality directly protects monetization (Fact Checker, Originality Agent, Compliance Agent), and use the cheap model everywhere else.

### 5.4 Media models (all behind swappable interfaces — see Section 0.5)
- **Video generation**: Veo 3.1 (hero shots, native 48kHz audio, strongest prompt adherence) + Kling 3.0 (bulk B-roll at ~$0.10/s, multilingual lip-sync for future dubbing). Never hard-code a single vendor — Sora 2's 6-month deprecation is the cautionary tale, not a hypothetical.
- **Voice**: ElevenLabs primary (quality benchmark, most expressive), Fish Audio / Chatterbox (open-source, outperformed ElevenLabs in blind tests per research) as cost fallback for high-volume/lower-tier content.
- **Vision/OCR**: Gemini 3.1 Pro vision for thumbnail QA and competitor-thumbnail pattern analysis; dedicated OCR (PaddleOCR or a cloud OCR API) for reading on-screen text in competitor research and verifying subtitle burn-in accuracy.
- **Subtitles/alignment**: WhisperX or Deepgram for forced word-level alignment feeding the Subtitle Agent.

### 5.5 Search & research APIs
YouTube Data API v3 (trends/search/upload), Google Trends API, Exa or Tavily (LLM-oriented web search/grounding), Reddit API via PRAW (community sentiment), SerpAPI (SERP-level competitive intel).

### 5.6 Browser automation
Playwright as the base automation layer; browser-use (LLM-driven, ~89% success on WebVoyager per research) for read-only competitive-intelligence tasks without clean APIs. **Do not route primary publishing through browser automation** — official APIs are cheaper and more reliable now that YouTube's upload quota cost dropped ~16x (Dec 2025 change), and write-path browser automation is both more fragile and more ToS-exposed than an official, sanctioned API call.

### 5.7 Cost optimization
- Prompt caching on Claude/Gemini for repeated system-prompt/context (agent instructions, style guides).
- Tiered model routing (5.3) — cheap model for bulk/draft, expensive model only where judgment quality protects revenue.
- Tiered video-gen routing (5.4) — Kling for bulk B-roll, Veo reserved for hero shots.
- Self-hosted open-source TTS fallback (Chatterbox) to cap voice cost at scale without sacrificing the ElevenLabs quality bar on flagship content.
- Batch video-gen requests where the vendor supports it; cache/reuse generated B-roll across topically-related videos rather than regenerating near-identical shots.

---

## 6. Recommended stack

| Layer | Choice | Rationale |
|---|---|---|
| Agent orchestration | LangGraph (Python) | Production default, checkpointing, human-in-loop interrupts |
| Durable workflow | Temporal | Multi-day durability, signal-based human approval, retries |
| Light job queue | Redis + BullMQ | Only for small, stateless fan-out jobs |
| Primary DB | Postgres (Neon/Supabase) | Relational integrity for audit trail + metrics |
| Vector DB | Qdrant (self-hosted) | Fastest OSS option, native hybrid search, cost control at your scale |
| Object storage | Cloudflare R2 | S3-compatible, zero egress fees |
| LLMs | Claude Opus 4.8 / Gemini 3.1 Pro / GPT-5.5 (routed) | Best-fit-per-task beats single-vendor lock-in |
| Video generation | Veo 3.1 + Kling 3.0 (abstracted) | Quality + cost tiering, vendor churn protection |
| Voice | ElevenLabs + Fish Audio/Chatterbox | Quality primary, cost fallback |
| Subtitles | WhisperX / Deepgram | Forced alignment accuracy |
| Video assembly | ffmpeg + Remotion | Code-driven, fits your full-stack background |
| Search/research | YouTube Data API, Google Trends, Exa/Tavily, Reddit API, SerpAPI | Coverage across trend/competitor/research needs |
| Browser automation | Playwright + browser-use (fallback only) | Reliability-first; APIs preferred for writes |
| Agent observability | LangSmith or Langfuse | Trace every agent decision (also your compliance audit trail) |
| App monitoring | Sentry + Grafana/Prometheus | Standard |
| Ops dashboard | Next.js + shadcn/ui | Your own full-stack skillset, fastest to build |
| Deployment | Docker Compose → single VPS (Hetzner/Fly.io) initially | Don't build Kubernetes for a one-operator system; revisit only at genuine multi-tenant scale |

---

## 7. Roadmap

### Phase 1 — MVP (Months 0–3)
- **Single channel**, one niche from Section 3 chosen by your own domain fluency (recommend finance, true-crime/legal, or English-learning).
- Pipeline runs **with a mandatory human approval gate** at Quality Review and Compliance stages — not fully autonomous yet, deliberately, per Section 0.2.
- Core agent set only: Trend Research, Deep Research, Fact Checker, Originality & Angle, Script Writer, Voice Synthesis, Video/Visual Generation (Kling only to start — cheap), Video Assembly, Subtitle, Quality Review, Compliance, Publishing (YouTube only).
- Stack: LangGraph + Postgres + Claude (single model to start, add routing in Phase 2) + ElevenLabs + Kling + ffmpeg, single VPS.
- Target: 2–3 videos/week, reach Tier-1 YPP eligibility, validate that the format holds up against real audience response before adding automation surface area.

### Phase 2 — Autonomy + distribution (Months 3–6)
- Loosen the human-approval threshold based on accumulated Quality Review Agent accuracy (track false-pass rate explicitly — don't loosen on a hunch).
- Add: Storytelling Structure, SEO/Metadata, Thumbnail, Humanization, Sound Design, Cross-Platform Repurposing, Analytics, A/B Testing.
- Add TikTok as a distribution channel (short-form repurposing) — hold Instagram per Section 0.3.
- Introduce full LLM tiered routing and Temporal for durable multi-day workflows.
- Target: 5–7 videos/week long-form + daily short-form repurposing.

### Phase 3 — Multi-channel scale (Months 6–12)
- Add Competitor Intelligence, Portfolio Strategy, Learning/Optimization, Copyright/Content-ID Risk.
- Expand to 2–4 channels, **deliberately differentiated** production pipelines per Section 0.4 (different niches, voices, editing styles, posting cadence — not a template clone).
- Reduce human-sampling rate as Compliance Agent's audit-trail track record builds confidence.
- Add cost-optimization routing (Section 5.7) as volume makes it worth the engineering time.

### Phase 4 — Production-grade content company (12+ months)
- Full Portfolio Strategy-driven niche allocation across N channels.
- Multi-language dubbing (Kling multilingual lip-sync, Chatterbox 23-language cloning) for international expansion beyond English.
- Revisit Instagram only if IG's stated 2026 direction shifts or you're willing to build genuinely non-automated-feeling IG-native execution as its own workstream.
- Consider productizing the platform for other creators — a natural extension, not a requirement, given your "not for public users yet" framing.

---

## 8. Phase 1 MVP — concrete build plan

### Channel angle & identity

**Format thesis: "The Turning Point."** Each video reconstructs a closed court case in strict chronological order from public record, built around the single piece of evidence, testimony, or decision that flipped the outcome — teased in the cold open, earned by the reconstruction, paid off at the verdict.

Why this specific angle instead of a generic "true crime channel":
- Gives the Storytelling Agent a genuine, non-templated hook mechanism instead of a generic "here's a crime" open.
- Gives the Fact Checker a well-defined sourcing discipline: trial transcripts, appellate opinions, court filings, contemporaneous news — not tabloid recaps.
- Naturally produces topic variety (different jurisdictions, eras, evidence types) for the Originality Agent to work with, instead of one repeatable template.
- Constrained to closed cases only (verdict already on public record) — sidesteps defamation exposure and the "misleading about current events" Limited-Ads trigger that live cases carry.

**Working name: "The Turning Point."** Backups if taken: "Verdict Line," "The Record."

### Cut-down agent list (revised for this niche, not the generic Phase 1 list)

Two changes from the generic MVP roadmap in Section 7, both niche-specific:
- **Storytelling Structure pulled forward from Phase 2** — the beat sheet *is* the format's identity here, not a Phase 2 nicety.
- **Copyright/Content-ID risk folded into Compliance as a checklist, not deferred to Phase 3** — real names, mugshots, and archival news footage are the core asset type in this niche, so the real-person/consent check can't wait.

Phase 1 set (12 nodes + orchestrator):

1. Case Sourcing (Trend Research, retargeted — see below)
2. Deep Research
3. Fact Checker
4. Originality & Angle
5. Storytelling Structure
6. Script Writer
7. Voice Synthesis
8. Video Generation (Kling only)
9. Video Assembly
10. Subtitle
11. Quality Review (human gate)
12. Compliance (policy rubric + real-person/copyright checklist)
13. Publishing (YouTube only — manual upload in week 1, see build order)

**Case Sourcing retargeting**: closed cases aren't trend-driven the way news is, so this agent isn't chasing Google Trends in week 1 — it's building and scoring a curated backlog. Tools: CourtListener/public court-record APIs, a Wikipedia "notable court cases" category crawl, news-archive search for cases with an anniversary or pop-culture reference reviving interest. Output: a scored backlog of 30+ candidate cases before automation is worth building on top of it.

### First week — build order

Goal for the week: **one full manually-run video, published, with every pipeline stage exercised at least once.** Not automation — proof the chain works end to end.

| Day | Build |
|---|---|
| 1 | Infra: repo scaffold, Postgres schema (channels / videos / agent_runs / decisions), LangGraph skeleton, secrets (Claude, ElevenLabs, Kling, YouTube OAuth), Cloudflare R2 bucket |
| 2 | Case Sourcing backlog (30 candidate cases, manually seeded + scored) + Deep Research agent producing a structured brief on case #1 |
| 3 | Fact Checker (claim-verification loop against the brief) + Originality & Angle (wire the embedding pipeline now, even against an empty corpus — it needs to exist before video #2) |
| 4 | Storytelling Structure (Turning-Point beat sheet template) + Script Writer, with WPM/pacing validation |
| 5 | Voice Synthesis (ElevenLabs) → Video Generation (Kling, B-roll only) → Video Assembly (ffmpeg/Remotion) → Subtitle, all writing to R2 |
| 6 | Quality Review (you, watching it against the rubric) + Compliance checklist pass; fix whatever the first full run exposes |
| 7 | Publish video #1 **manually** through YouTube Studio, not the API yet — validate the human workflow and the video itself before automating the write path. Write down every step that broke or felt fragile; that list becomes week 2's priority order, not a pre-written plan |

Deliberately **not** in week 1: TikTok repurposing, multi-model LLM routing, Temporal (a single manual LangGraph run doesn't need durable workflow yet), a second case in flight simultaneously. One case, one full pass, end to end — the point is finding out where the pipeline actually breaks before adding volume.

---

## Sources

**YouTube policy**
- [YouTube Inauthentic Content Policy: AI Enforcement Wave 2026](https://flocker.tv/posts/youtube-inauthentic-content-ai-enforcement/)
- [YouTube channel monetization policies — YouTube Help](https://support.google.com/youtube/answer/1311392?hl=en)
- [YouTube Targets Mass-Produced Content in Monetization Update](https://www.searchenginejournal.com/youtube-targets-mass-produced-content-in-monetization-update/550337/)
- [YouTube Clarifies Changes to Monetization Rules Around Inauthentic Content](https://www.socialmediatoday.com/news/youtube-clarifies-monetization-update-inauthentic-repeated-content/752892/)
- [YouTube AI Content Monetization Policy 2026 — ScaleLab](https://scalelab.com/en/why-youtube-is-cracking-down-on-ai-generated-content-in-2026)
- [YouTube Reused Content Policy: How to Stay Monetized in 2026 — vidIQ](https://vidiq.com/blog/post/youtube-reused-content-policy-guide/)
- [YouTube bans two popular channels for fake AI movie trailers](https://tagteam.harvard.edu/hub_feeds/3415/feed_items/17131601/content)
- [YouTube AI Copyright Supreme Court Ruling 2026 — OutlierKit](https://outlierkit.com/resources/ai-copyright-supreme-court-ruling-youtube-2026/)
- [YouTube Data API Quota Limits 2026 — getphyllo](https://www.getphyllo.com/post/youtube-api-limits-how-to-calculate-api-usage-cost-and-fix-exceeded-api-quota)
- [YouTube Partner Program overview & eligibility — YouTube Help](https://support.google.com/youtube/answer/72851)

**Case studies / economics**
- [The Faceless YouTube Channel Explosion 2026 — Miraflow](https://miraflow.ai/blog/faceless-youtube-channel-explosion-ai-million-subscriber-creators-2026)
- [Faceless Creators Take a Hit As YouTube Cracks Down on AI Slop — Hollywood Reporter](https://www.hollywoodreporter.com/business/digital/faceless-creators-youtube-ai-damage-1236617586/)
- [How Much Do Faceless YouTube Channels Make in 2026 — Korpi AI](https://korpi.ai/blog/how-much-do-faceless-youtube-channels-make)
- [19 Most Profitable YouTube Niches 2026 — OutlierKit](https://outlierkit.com/blog/most-profitable-youtube-niches)
- [25 Highest RPM YouTube Niches — Virlo](https://virlo.ai/blog/highest-rpm-niches-on-youtube)

**Instagram**
- [How the Instagram Algorithm Works — Buffer 2026 Guide](https://buffer.com/resources/instagram-algorithms/)
- [Instagram Algorithm 2026: What Changed — CreatorFlow](https://creatorflow.so/blog/instagram-algorithm-2026/)
- [The State of Instagram in 2026: Reach Is Not a Posting Strategy — ListenFirst](https://www.listenfirstmedia.com/the-state-of-instagram-in-2026-reach-is-not-a-posting-strategy/)
- [Instagram Reels Statistics 2026 — AutoFaceless](https://autofaceless.ai/blog/instagram-reels-statistics-2026)
- [About bonuses on Instagram — Meta Business Help Center](https://www.facebook.com/business/help/543274486958120)

**TikTok**
- [TikTok Creator Rewards Requirements 2026 — PostLink](https://postlinkapp.com/blog/tiktok-creator-rewards-program)
- [TikTok Support — Creator Rewards Program](https://support.tiktok.com/en/business-and-creator/creator-rewards-program/creator-rewards-program)
- [TikTok Algorithm 2026: How to Win With Rewatches — Darkroom](https://www.darkroomagency.com/observatory/how-tiktok%E2%80%99s-algorithm-works-in-2026-and-15-tactics-to-go-viral)
- [TikTok AI Content Policy 2026: 4-Tier Labels & Penalties — AuditSocials](https://www.auditsocials.com/blog/tiktok-ai-content-disclosure-rules-2026)
- [TikTok AI Statistics: 1.3B Videos Labeled — Dynamoi](https://dynamoi.com/learn/ai-music-distribution/tiktok-ai-content-statistics)

**Tech stack**
- [Best AI Video Generator 2026: Sora 2 vs Veo 3.1 vs Kling — LaoZhang AI](https://blog.laozhang.ai/en/posts/best-ai-video-model)
- [Best TTS Model 2026 — Befreed](https://www.befreed.ai/blog/best-tts-model-2026)
- [LangGraph vs CrewAI vs AutoGen 2026 — Pooya Golchian](https://pooya.blog/blog/crewai-vs-langgraph-autogen-comparison-2026/)
- [Best Vector Database 2026 — Iternal](https://iternal.ai/insights/best-vector-databases-2026)
- [pgvector vs Pinecone vs Qdrant vs Weaviate 2026 — Kalvium Labs](https://www.kalviumlabs.ai/blog/vector-databases-compared-pgvector-pinecone-qdrant-weaviate/)
- [AI Model Benchmarks Jul 2026 — LM Council](https://lmcouncil.ai/benchmarks)
- [Orchestrating AI Tasks with Celery vs Temporal](https://dasroot.net/posts/2026/02/orchestrating-ai-tasks-celery-temporal/)
- [11 Best AI Browser Agents in 2026 — Firecrawl](https://www.firecrawl.dev/blog/best-browser-agents)
