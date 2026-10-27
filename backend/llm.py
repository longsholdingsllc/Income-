"""LLM layer for the Income (Autopilot) backend.

Provider order:
1. Anthropic API directly, when ANTHROPIC_API_KEY is set.
2. Emergent's integration library, when EMERGENT_LLM_KEY is set and the
   package is installed (original Emergent deployment behavior).
3. A built-in local generator that produces real, input-driven output with
   no external key — ideas, content drafts, and coach replies built from the
   user's actual profile, streams, and goals. Output is never labeled as
   coming from an external model.
"""

import hashlib
import json
import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
MODEL = os.environ.get("LLM_MODEL", "claude-sonnet-4-5-20250929")


async def chat(kind: str, system: str, prompt: str, history=None, meta=None) -> str:
    """Return the assistant's raw text reply for one call.

    kind is "ideas", "content", or "coach". For ideas/content the reply is a
    JSON string matching the schema described in `system`.
    """
    history = history or []
    if ANTHROPIC_API_KEY:
        try:
            return await _anthropic(system, prompt, history)
        except Exception:
            pass  # fall through to local generation rather than failing the request
    if EMERGENT_LLM_KEY:
        try:
            return await _emergent(system, prompt)
        except Exception:
            pass
    return _local(kind, prompt, history, meta or {})


async def _anthropic(system: str, prompt: str, history) -> str:
    import httpx

    messages = [{"role": m["role"], "content": m["content"]} for m in history]
    messages.append({"role": "user", "content": prompt})
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": 4000,
                "system": system,
                "messages": messages,
            },
        )
        resp.raise_for_status()
        data = resp.json()
    return "".join(
        block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
    )


async def _emergent(system: str, prompt: str) -> str:
    from emergentintegrations.llm.chat import LlmChat, UserMessage

    chat_client = LlmChat(
        api_key=EMERGENT_LLM_KEY, session_id="income-backend", system_message=system
    ).with_model("anthropic", MODEL)
    return await chat_client.send_message(UserMessage(text=prompt))


# ---------------- Local generation (no external key) ----------------

_IDEA_BANK = [
    {
        "title": "Digital product bundle in {interest}",
        "category": "digital_products",
        "tags": ["writing", "design", "teaching", "marketing", "business", "finance", "tech", "productivity"],
        "summary": "Package what you already know about {interest} into a practical template/checklist bundle and sell it on Gumroad. Digital products have near-zero marginal cost, so every sale after the first is close to pure margin.",
        "income": "$200-$1,500/mo once you have 3-5 products and steady traffic",
        "cost": "$0-$50 (Gumroad is free to start; optional design tools)",
        "ttfd": "1-3 weeks",
        "risk": "low",
        "plan": [
            "List the 10 questions people most often ask you about {interest}",
            "Turn the answers into a checklist/template pack (10-20 pages)",
            "Price the first product at $19-$29 and list it on Gumroad",
            "Post one helpful short video or thread per day pointing to it",
            "Bundle products together at a discount once you have three",
        ],
        "tools": ["Gumroad", "Google Docs or Canva", "Your phone for short-form video"],
    },
    {
        "title": "Faceless content channel about {interest}",
        "category": "ads",
        "tags": ["video", "writing", "social", "media", "marketing"],
        "summary": "Start a faceless YouTube/social channel in {interest} using stock footage and AI voiceover. Revenue comes from ad share plus affiliate links in every description — the catalog keeps earning while you sleep.",
        "income": "$100-$2,000/mo after 6-12 months of consistent uploads",
        "cost": "$0-$100 (stock footage and voiceover tools)",
        "ttfd": "2-6 months (ad revenue), affiliate income can start in weeks",
        "risk": "low",
        "plan": [
            "Pick one narrow sub-topic inside {interest} with proven search demand",
            "Batch-produce 4 videos in a weekend using stock footage + AI voice",
            "Put one relevant affiliate link in every description",
            "Publish 3x per week for 90 days before judging results",
            "Repurpose the best videos as shorts on two more platforms",
        ],
        "tools": ["YouTube", "CapCut or Descript", "Pexels/Pixabay stock footage"],
    },
    {
        "title": "Print-on-demand designs for the {interest} niche",
        "category": "print_on_demand",
        "tags": ["design", "art", "ecommerce", "creative"],
        "summary": "Upload text/quote designs aimed at {interest} fans to a print-on-demand platform. The platform prints, ships, and handles support — you keep the margin on every order with no inventory.",
        "income": "$50-$800/mo with 30+ live designs",
        "cost": "$0 (Printify free plan)",
        "ttfd": "2-8 weeks",
        "risk": "low",
        "plan": [
            "Research the 20 best-selling shirt/poster phrases in {interest}",
            "Create 10 simple, original designs (avoid trademarked phrases)",
            "Publish on one product type first (tees or posters)",
            "Add 2-3 designs per week until you reach 30+",
            "Double down on any design that gets its first organic sale",
        ],
        "tools": ["Printify", "Canva", "Etsy or a Shopify storefront"],
    },
    {
        "title": "Dividend ladder with automatic reinvestment",
        "category": "dividends",
        "tags": ["finance", "investing", "money"],
        "summary": "Automate a monthly contribution into a basket of dividend ETFs and reinvest every payout. It is slow, boring, and one of the most reliable paths to income that truly requires no ongoing work.",
        "income": "Roughly $35-$45/mo per $10,000 invested at a ~4-5% yield, growing with contributions",
        "cost": "Whatever you can auto-invest monthly — start with $50-$100/mo",
        "ttfd": "First dividend within one quarter",
        "risk": "medium",
        "plan": [
            "Open a brokerage account with fractional shares and DRIP enabled",
            "Pick 2-3 diversified dividend ETFs rather than single stocks",
            "Set an automatic monthly buy you can sustain in bad months too",
            "Reinvest 100% of dividends for the first two years",
            "Review once a year; never chase yield into single-name risk",
        ],
        "tools": ["Any major brokerage app", "ETF research (e.g. issuer fact sheets)"],
    },
    {
        "title": "Affiliate review site for {interest} gear",
        "category": "affiliate",
        "tags": ["writing", "seo", "blogging", "marketing", "tech"],
        "summary": "Build a small review/comparison site in {interest} and monetize with affiliate programs. 'Best X for Y' articles rank for years and earn commissions on products you never touch.",
        "income": "$100-$1,000/mo after 10-15 ranking articles",
        "cost": "$0-$60/yr (domain; free hosting tiers exist)",
        "ttfd": "1-4 months",
        "risk": "low",
        "plan": [
            "List 15 'best ___ for ___' searches inside {interest} with buying intent",
            "Apply to the top 3 affiliate programs in the niche",
            "Publish 2 genuinely useful comparison articles per week",
            "Add real pros/cons and a comparison table to every article",
            "Update the top articles quarterly to hold rankings",
        ],
        "tools": ["WordPress or a static site", "Amazon Associates + niche programs", "Google Search Console"],
    },
    {
        "title": "Notion/template pack for {interest} workflows",
        "category": "digital_products",
        "tags": ["productivity", "organization", "business", "systems", "tech"],
        "summary": "Turn a repeatable {interest} workflow into a polished template pack. Templates sell well because buyers pay to skip setup time, and one build can sell for years.",
        "income": "$100-$900/mo with an audience or marketplace traffic",
        "cost": "$0 (free Notion/tools tiers)",
        "ttfd": "1-3 weeks",
        "risk": "low",
        "plan": [
            "Document one workflow you repeat every week, step by step",
            "Rebuild it as a clean template with instructions and examples",
            "Record a 3-minute walkthrough video as the sales page demo",
            "Launch at $19-$39 on Gumroad with a launch-week discount",
            "Collect testimonials and add a second, deeper template as the upsell",
        ],
        "tools": ["Notion", "Gumroad", "Loom for the demo video"],
    },
    {
        "title": "Stock media portfolio ({interest} photos/footage)",
        "category": "royalties",
        "tags": ["photography", "video", "art", "creative", "design"],
        "summary": "Upload your best {interest} photos or clips to stock agencies. Each accepted asset earns royalties for years; portfolios of 500+ assets produce steady trickle income.",
        "income": "$25-$500/mo at 300-800 accepted assets",
        "cost": "$0 (phone camera is enough to start)",
        "ttfd": "2-6 weeks",
        "risk": "low",
        "plan": [
            "Shoot 50 assets around one buyer-friendly theme (business, food, lifestyle)",
            "Keyword every upload with buyer search terms, not artistic ones",
            "Upload to two agencies to start; add more once accepted",
            "Add 25 new assets a week until you pass 300",
            "Reinvest early royalties in props/locations for higher-value shoots",
        ],
        "tools": ["Phone or camera", "Shutterstock/Adobe Stock contributor accounts"],
    },
    {
        "title": "High-yield cash + T-bill ladder for idle money",
        "category": "interest",
        "tags": ["finance", "investing", "money", "saving"],
        "summary": "Move idle cash into a high-yield savings account and a simple Treasury bill ladder. Zero skill required — this is about stopping your cash from losing to inflation.",
        "income": "Roughly $40/mo per $10,000 at ~4.8% APY",
        "cost": "$0 — uses money you already have",
        "ttfd": "Interest starts accruing immediately",
        "risk": "low",
        "plan": [
            "Total up every idle account balance you have today",
            "Open a high-yield savings account and move the emergency fund there",
            "Ladder any cash beyond 6 months of expenses into 4/8/13-week T-bills",
            "Automate a monthly sweep of leftover checking balance",
            "Re-check rates twice a year and move if the gap exceeds 0.5%",
        ],
        "tools": ["High-yield savings account", "TreasuryDirect or a brokerage"],
    },
]


def _local(kind: str, prompt: str, history, meta: dict) -> str:
    if kind == "ideas":
        return json.dumps({"ideas": _local_ideas(meta)})
    if kind == "content":
        return json.dumps(_local_content(meta))
    return _local_coach(prompt, history, meta)


def _local_ideas(meta: dict) -> list:
    skills = (meta.get("skills") or "").lower()
    interests = (meta.get("interests") or "").strip()
    budget = float(meta.get("budget_usd") or 0)
    risk_pref = (meta.get("risk_tolerance") or "medium").lower()
    interest_label = interests if interests else "your niche"
    haystack = f"{skills} {interests.lower()}"

    def score(item):
        hits = sum(1 for t in item["tags"] if t in haystack)
        return hits

    ranked = sorted(_IDEA_BANK, key=score, reverse=True)
    chosen = []
    for item in ranked:
        if risk_pref == "low" and item["risk"] not in ("low",):
            continue
        chosen.append(item)
        if len(chosen) == 5:
            break
    if len(chosen) < 5:
        for item in ranked:
            if item not in chosen:
                chosen.append(item)
            if len(chosen) == 5:
                break

    out = []
    for item in chosen:
        fill = {"interest": interest_label}
        out.append(
            {
                "title": item["title"].format(**fill),
                "category": item["category"],
                "summary": item["summary"].format(**fill),
                "estimated_monthly_income": item["income"],
                "startup_cost": item["cost"],
                "time_to_first_dollar": item["ttfd"],
                "risk": item["risk"],
                "action_plan": [p.format(**fill) for p in item["plan"]],
                "tools_needed": item["tools"],
            }
        )
    return out


def _local_content(meta: dict) -> dict:
    niche = (meta.get("niche") or "your niche").strip()
    keywords = (meta.get("keywords") or niche).strip()
    audience = (meta.get("target_audience") or "beginners").strip() or "beginners"
    product = (meta.get("affiliate_product") or "").strip()
    primary_kw = keywords.split(",")[0].strip()
    title_kw = primary_kw[:1].upper() + primary_kw[1:]
    product_line = (
        f"One tool that keeps coming up in reader feedback is {product} — details and current pricing are here: [AFFILIATE_LINK]."
        if product
        else "Throughout this guide you'll find the exact tools referenced linked inline, like this one: [AFFILIATE_LINK]."
    )
    outline = [
        f"Why {primary_kw} matters for {audience}",
        f"The basics of {primary_kw}, explained simply",
        f"Step-by-step: getting started with {primary_kw}",
        f"Common {primary_kw} mistakes (and how to avoid them)",
        f"Tools and resources that make {primary_kw} easier",
        f"Realistic timelines and what results to expect",
        f"Final verdict: is {primary_kw} worth it for {audience}?",
    ]
    article = f"""# {title_kw}: A Practical Guide for {audience[:1].upper() + audience[1:]}

If you're exploring **{primary_kw}** in the {niche} space, you don't need more hype — you need a clear order of operations. This guide breaks {primary_kw} down into what it is, who it actually works for, and the exact steps to get started without wasting money on the wrong things first.

## Why {primary_kw} matters

Most {audience} stall on {primary_kw} for the same reason: they try to copy advanced tactics before the basics are in place. The basics are unglamorous — a clear goal, the right order of steps, and consistency for longer than feels exciting. Get those right and {primary_kw} becomes a system instead of a gamble.

## The basics, explained simply

At its core, {primary_kw} is about matching effort to payoff. Start by defining what success looks like in one measurable sentence (a number and a date, not a feeling). Then work backwards: what weekly actions actually move that number? Everything else is decoration until those actions are happening reliably.

{product_line}

## Step-by-step: getting started

1. **Set the target.** Write down the specific result you want from {primary_kw} in the next 90 days.
2. **Audit where you stand.** List what you already have — skills, audience, tools, budget — before buying anything new.
3. **Do the smallest useful version first.** A rough version shipped this week beats a perfect version planned for next month.
4. **Measure weekly.** Track the one or two numbers that matter and ignore vanity metrics.
5. **Fix the bottleneck, not everything.** Each week, improve only the weakest step in the chain.

## Common mistakes to avoid

- **Buying tools before having a process.** Tools amplify a working system; they don't create one.
- **Copying someone five years ahead of you.** Their tactics assume resources you don't have yet.
- **Quitting at week three.** {primary_kw} results compound — most people stop right before the curve bends.
- **Tracking everything.** Ten metrics means zero priorities. Pick two.

## Tools and resources

Keep the stack boring and cheap at the start: one place to plan, one place to publish or execute, and one place to measure. Upgrade only when a free tier genuinely blocks you. The current reader-favorite option in this category is linked here: [AFFILIATE_LINK].

## Realistic timelines

Expect the first small result in 2-6 weeks of consistent work, meaningful traction in 3-6 months, and compounding results after that — provided you keep publishing/iterating weekly. Anyone promising faster is selling you the exception, not the rule.

## Final verdict

{title_kw} is worth it for {audience} who will commit to a simple system for at least 90 days. Start with step one this week, keep the stack cheap, and let consistency do the heavy lifting.
"""
    return {
        "title": f"{title_kw}: The Complete Beginner-Friendly Guide ({niche})",
        "meta_description": f"A practical, no-hype guide to {primary_kw} for {audience}: the basics, a step-by-step starter plan, common mistakes, tools, and realistic timelines.",
        "outline": outline,
        "article_markdown": article,
        "cta_suggestions": [
            f"Download the free {primary_kw} starter checklist",
            f"Try the reader-favorite {niche} tool linked in this guide",
            "Join the newsletter for one practical income idea every week",
        ],
    }


def _local_coach(message: str, history, meta: dict) -> str:
    streams = meta.get("streams") or []
    target = float(meta.get("monthly_target") or 0)
    msg = (message or "").lower()
    digest = hashlib.md5((message or "").encode()).hexdigest()
    variant = int(digest[:2], 16) % 3

    lines = []
    if streams:
        est = sum(float(s.get("monthly_estimate") or 0) for s in streams)
        names = ", ".join(s.get("name", "stream") for s in streams[:3])
        lines.append(
            f"Looking at your setup: you have {len(streams)} stream(s) tracked ({names}) "
            f"with about ${est:,.0f}/mo in estimates"
            + (f" against a ${target:,.0f}/mo target." if target else ".")
        )
    else:
        lines.append(
            "You don't have any income streams tracked yet — that's step zero, because we can't grow what we aren't measuring."
        )

    if any(w in msg for w in ["start", "begin", "first", "new", "idea"]):
        lines.append(
            "Here's how I'd start, in order:\n"
            "- Pick ONE stream you can launch for under $100 and 5 hours a week — digital products or print-on-demand are the fastest first dollar.\n"
            "- Give it a 90-day runway with a weekly ship target (one product, one video, or one article per week).\n"
            "- Track every dollar as an entry in that stream from day one, even the $3 ones — the habit matters more than the amount."
        )
    elif any(w in msg for w in ["grow", "scale", "more", "increase"]):
        lines.append(
            "To grow from here:\n"
            "- Find your best-performing stream from your tracked entries and put 70% of your effort there for the next month — concentration beats spreading thin.\n"
            "- Add one traffic source you don't control yet (search, shorts, or partnerships) so growth isn't rented from one algorithm.\n"
            "- Raise prices or add a bundle before adding a brand-new stream; revenue per customer is the cheapest growth lever."
        )
    elif any(w in msg for w in ["debt", "quit", "job", "freedom", "enough"]):
        lines.append(
            "On the freedom math:\n"
            "- Your freedom number is the monthly passive income that covers your non-negotiables — set it in Goals if you haven't.\n"
            "- Compare it honestly against what your streams earned in the last 30 days (check the dashboard), not against estimates.\n"
            "- The gap closes fastest by stacking one new stream every quarter, not by trying to 10x a single small one."
        )
    else:
        openers = [
            "Good question. Here's the practical version:",
            "Let's make this concrete:",
            "Here's how I'd approach it:",
        ]
        lines.append(
            openers[variant]
            + "\n- Anchor on your tracked numbers first: open the dashboard and look at the last 30 days of actual entries versus your monthly target.\n"
            "- Pick the single smallest action that moves that number this week, and schedule it — vague goals don't compound, calendar entries do.\n"
            "- Log the result as an entry either way; a month of honest data will tell us exactly what to do next."
        )

    lines.append(
        "Tell me a bit more about where you're stuck — is it picking a stream, finding traffic, or staying consistent? I'll get more specific. "
        "(Note: this is general education, not personalized financial advice.)"
    )
    return "\n\n".join(lines)
