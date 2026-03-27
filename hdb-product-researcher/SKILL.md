---
name: hdb:product-researcher
description: Use when given a product idea or existing products to research — analyzes functionality, market positioning, competitive landscape, feature desirability, and community sentiment from Reddit
---

# hdb-product-researcher

Research products and their market to produce a competitive analysis grounded in functionality, feature desirability, and real user sentiment.

## Usage

```
/hdb:product-researcher <product idea or product names/URLs>
```

## Description

Performs deep product research given either a product idea (to find existing players) or pointers to specific products (to analyze them directly). Produces a structured research document covering what each product does, what the category has in common, which features users love most, how difficult it would be to build a competitor, and what Reddit users actually say about these products. The output is a reference document for product strategy decisions.

## Instructions

When the user invokes `/hdb-product-researcher <input>`:

### Phase 1: Scope the research

1. **Determine the input type:**
   - **Product idea** — The user has a concept and wants to know who else is doing it. Proceed to step 2.
   - **Specific products** — The user names products or provides URLs. Skip to step 3.
   - **Both** — The user has specific products AND wants to see who else is in the space. Do both steps 2 and 3.

2. **Discover the competitive landscape.** Search the web to identify:
   - The product category name (what users call this space)
   - The top 5-10 products in this category (both commercial and open source)
   - Any notable newcomers or recently shut-down products
   - Adjacent categories that partially overlap
   - **If the product is software**, search GitHub for top open-source alternatives (see Phase 2a)

   Present the discovered products to the user and ask: "Are these the right products to analyze? Should I add or remove any?"

3. **Confirm the product list.** State the products that will be researched and the category definition. If the user provided products, ask if they want the broader landscape included or just the named products.

### Phase 2: Research each product

4. **For each product, gather:**

   **Core functionality:**
   - What does it do? One-paragraph summary of the product's purpose
   - What is the primary use case? Who is the target user?
   - What is the pricing model? (Free, freemium, subscription, one-time, usage-based)
   - What platforms does it run on? (Web, desktop, mobile, CLI, API)

   **Feature inventory:**
   - List all major features visible from the product's marketing site, documentation, and changelog
   - Categorize features as: core (essential to the product category), differentiating (unique to this product), or table-stakes (expected but not differentiating)
   - Note any features that are prominently marketed (what the company thinks matters most)

   **Technical characteristics:**
   - Open source or proprietary?
   - Self-hostable or cloud-only?
   - API available? What kind? (REST, GraphQL, SDK)
   - Integrations with other tools
   - Data portability — can users export their data easily?

   **Market signals:**
   - Approximate user base or traction indicators (funding raised, employees, customer logos, app store ratings)
   - How long has the product existed?
   - Recent trajectory — growing, stable, declining, pivoting?

5. **Use web search and scraping** to gather this information from:
   - The product's own website and documentation
   - Review sites (G2, Capterra, Product Hunt, AlternativeTo)
   - Tech press coverage
   - App store listings if applicable

### Phase 2a: Open-source landscape (software products only)

6. **Search GitHub for open-source alternatives** in the product category:
   - Search GitHub by topic, description, and category keywords
   - Sort by stars to find the most popular projects
   - For each significant open-source project (1000+ stars, or fewer if the category is niche), gather:

   **Repository health:**
   - Stars, forks, and open issues count
   - Last commit date and commit frequency (active / maintained / abandoned?)
   - Number of contributors
   - Release cadence — how often are new versions published?

   **Project maturity:**
   - Is it production-ready or experimental?
   - Does it have documentation, tests, and CI?
   - What license? (MIT, GPL, AGPL, etc. — this affects commercial viability)
   - Is there a company or foundation behind it, or is it community-driven?

   **Feature comparison to commercial products:**
   - Which commercial features does the open-source project replicate?
   - What is missing compared to the paid alternatives?
   - Are there features unique to the open-source version? (Self-hosting, extensibility, plugin systems)

   **Community signals:**
   - What do GitHub issues and discussions reveal about pain points?
   - Are there forks that address specific gaps? (Indicates unmet needs)
   - How responsive are maintainers to issues and PRs?

7. **Assess the open-source threat/opportunity:**
   - Could an open-source project be the foundation for a competitive product?
   - Which open-source projects could a new entrant build on top of instead of starting from scratch?
   - Are commercial products at risk of being displaced by open-source alternatives?

### Phase 3: Reddit sentiment analysis

8. **Search Reddit for discussions** about each product and the product category. Use targeted searches:
   - `site:reddit.com "<product name>" review`
   - `site:reddit.com "<product name>" vs`
   - `site:reddit.com "<product name>" alternative`
   - `site:reddit.com "looking for" OR "recommend" <category keywords>`
   - `site:reddit.com "<product name>" switched from OR switched to`
   - `site:reddit.com "<product name>" open source OR self-hosted` (for software products)

9. **For each product, extract from Reddit discussions:**

   **Loved features** — Which specific features do commenters praise? Quote representative comments. Rank by frequency of mention.

   **Pain points** — What do users complain about? Common frustrations, missing features, broken workflows. Quote representative comments.

   **Deal-breakers** — Which products have users explicitly turned away from, and why? Capture the specific reason: "I tried X but left because it didn't have Y."

   **Unmet needs** — What do users say they wish existed? Capture requests like "I just need something that does X without all the bloat of Y."

   **Switching patterns** — Who switches from what to what, and why? Capture migration paths: "I moved from X to Y because..."

10. **Assess overall Reddit sentiment volume:**
    - How many distinct Reddit threads discuss this product category?
    - How many users express a need for a product like this?
    - Which subreddits have the most discussion? (This reveals the user community)
    - Is discussion volume growing, stable, or declining over time?

### Phase 4: Competitive analysis

11. **Identify category commonalities:**
   - What features does every product in the category share? (These are table-stakes)
   - What is the standard pricing model?
   - What is the typical platform coverage?
   - What technical approach do most products take?

12. **Identify differentiators:**
    - What makes each product unique?
    - Which differentiators actually matter to users (based on Reddit sentiment)?
    - Which differentiators are marketing-speak that users don't mention?

13. **Map feature desirability** by combining the feature inventory with Reddit sentiment:
    - **Must-have features** — Users leave products that lack these
    - **Delight features** — Users praise products that have these, but don't leave over their absence
    - **Indifferent features** — Present in products but rarely mentioned by users
    - **Anti-features** — Features users actively complain about (bloat, complexity, privacy concerns)

### Phase 5: Build-difficulty assessment

14. **For each product, estimate the difficulty of building a competitive alternative:**

    **Technical complexity:**
    - What are the hardest technical problems to solve? (e.g., real-time sync, ML models, data pipelines)
    - Are there open-source libraries or frameworks that solve the hard parts?
    - What infrastructure is required? (Simple web server? GPU clusters? Edge network?)

    **Data and network effects:**
    - Does the product benefit from network effects? (More users = more value?)
    - Does it require a large dataset to function? (Training data, content library, marketplace inventory?)
    - How hard is the cold-start problem?

    **Moat assessment:**
    - What makes this product hard to copy? (Brand, data, integrations, patents, community?)
    - What is easily copyable? (UI patterns, feature set, pricing model?)
    - Are there regulatory or compliance barriers?

    **Estimated effort:** Classify as:
    - **Weekend project** — Core functionality achievable by one developer in days
    - **Side project** — Core functionality achievable by one developer in 1-3 months
    - **Startup** — Requires a small team and months of focused work
    - **Major undertaking** — Requires significant investment, specialized expertise, or data acquisition
    - **Extremely difficult** — Strong moats (network effects, data, regulation) make competition impractical without substantial resources

### Phase 6: Synthesize

15. **Produce the research document** with these sections:

    **Executive Summary** — 3-5 sentences: what is this product category, how many players exist, what do users care about most, and how hard is it to compete.

    **Product Evaluations** — For each product:
    - One-paragraph summary
    - Strengths (with Reddit evidence)
    - Weaknesses (with Reddit evidence)
    - Who is this product best for?
    - Overall rating: strong / adequate / weak / declining

    **Comparison Matrix** — A table comparing all products across key dimensions:
    - Core features (present/absent/partial)
    - Pricing
    - Platforms
    - Open source / self-hostable
    - API availability
    - GitHub stars (for open-source projects)
    - Reddit sentiment (positive/mixed/negative)

    **Feature Desirability Map** — The must-have / delight / indifferent / anti-feature breakdown with evidence.

    **Reddit Sentiment Summary:**
    - Total discussion volume and trend
    - Top 5 most-loved features across the category (with quotes)
    - Top 5 most-requested missing features (with quotes)
    - Top 5 reasons users leave products (with quotes)
    - Subreddits where this category is discussed

    **Market Assessment:**
    - Is this market growing, stable, or shrinking?
    - Is there an underserved segment?
    - What would a new entrant need to offer to win users?
    - What is the minimum viable feature set based on user sentiment?

    **Open-Source Landscape** (software products only):
    - Top open-source alternatives with GitHub stats (stars, contributors, last activity)
    - Feature gap analysis vs. commercial products
    - Viability as a foundation for a new product
    - License implications for commercial use

    **Build-Difficulty Summary** — For each product, the effort estimate and key moats. Note which open-source projects reduce build difficulty. Overall assessment: is there room for a new competitor?

    **Opportunities** — Based on all research, where are the gaps? What could a new product do that nobody is doing well? Can any existing open-source project be extended to fill the gap?

    **Sources** — URLs for all product pages, Reddit threads, review sites, and articles consulted.

16. **Write the research document** to a file. Suggest: `research/<category-slug>-product-research.md`

## Guidelines

- **Let users speak for themselves.** Quote Reddit comments directly rather than paraphrasing. Attribute to subreddit and approximate date when possible.
- **Distinguish marketing from reality.** What a product's website says and what users experience are often different. Note discrepancies.
- **Be opinionated where evidence supports it.** "Product X dominates this category because..." is more useful than "there are several products." Ground opinions in data.
- **Flag uncertainty.** If information cannot be verified (user counts, revenue, private companies), mark it as `[ESTIMATED]` or `[UNVERIFIED]`.
- **Prioritize recency.** A Reddit thread from 6 months ago is more relevant than a blog post from 3 years ago. Note dates on all evidence.
- **Don't over-research niche products.** If a product has minimal Reddit discussion and limited market presence, a brief evaluation is sufficient. Spend depth on the products users actually discuss.
- **Think like a founder.** The person reading this research is deciding whether to build something. Every section should help them make that decision.
