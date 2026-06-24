---
name: hdb:linkedin-profile-fixer
description: Use when a user wants to revamp, audit, or rewrite their LinkedIn profile to attract recruiters — runs a sequenced, one-section-at-a-time rewrite anchored to real target job descriptions, never inventing metrics. Triggers on "fix my LinkedIn", "rewrite my profile/headline/About section", "LinkedIn audit", "optimize my profile for recruiters".
---

# hdb-linkedin-profile-fixer

Rewrite a LinkedIn profile so it reads specific, scoped, and numbers-driven — the kind of profile that pulls inbound recruiter DMs without applying to anything.

## Usage

```
/hdb:linkedin-profile-fixer
```

Optionally pass the profile export path and/or target-role notes inline.

## Core principles (do not violate)

1. **Sequence beats stacking.** Rewrite **one section per step**. Never audit + rewrite headline, About, experience, skills, and featured in a single response — output quality collapses and every section comes out in the same generic ghostwriter voice. One brilliant section beats six shallow ones.
2. **A target role is mandatory.** You cannot optimize for "a better job." You need the actual text of 3–5 real job descriptions the user wants. Without them, refuse to proceed and ask for them.
3. **Never invent metrics.** Numbers ("4M+ creators monthly", "2.7B users") are what make a profile evaluable. You do **not** have the user's real numbers — ask for them. If the user has none for a claim, rewrite without a fabricated figure; do not guess, estimate, or insert a placeholder that reads as fact.
4. **Kill generic filler.** Ban "passionate", "delight users", "results-driven", "cross-functional initiatives", "leverage", "synergy", and verbs-and-vibes bullets with zero substance. Every line must be something a recruiter can actually evaluate.
5. **PDF export, not scraping.** Tell the user to export their profile (LinkedIn → "Resources" panel on the right → "Save to PDF") and upload it. Do not suggest Apify or live-scraping connectors — they break on private profiles, mobile sessions, and rate limits.

## Setup gate

Before writing anything, confirm you have **both** inputs:

- **The profile.** A LinkedIn PDF export (preferred), or pasted profile text. If missing, give the export instructions above and stop.
- **Targets.** 3–5 full job descriptions for roles the user actually wants, as raw text. For emerging roles (AI PM, agentic-workflows lead) the closest real JDs are fine. If missing, stop and ask for them. Vague targeting → vague output.

Once both are in hand, extract from the JDs: the recurring keywords, required skills, seniority signals, and the 2–3 outcomes these roles most reward. You will anchor every rewrite to these.

## The sequence — run these steps in order, one response each

Run each step, present the rewrite, and **wait for the user's reaction / real numbers before moving to the next**. Do not batch.

### Step 1 — Tear it apart (diagnosis only)
Read the whole profile against the target JDs. Output a blunt critique, not a rewrite: what the headline buries, where the About section opens generically, which experience bullets are "verbs and vibes" with no numbers, and which JD keywords are missing entirely. End by naming **the single section that will move the needle most** — usually the headline or the About opener — and start there.

### Step 2 — The headline
Rewrite the headline. It must lead with the most interesting, specific thing the user does, scoped and quantified. Model the form: *"I help [org] ship [specific thing] that [number/scale] [audience]. Previously [specific prior scope]."* Offer 2–3 variants. Ask the user for any scale/number you don't have rather than inventing one.

### Step 3 — The About section
Rewrite the About. The first sentence is everything — it must be specific and scoped, never "I'm a [title] passionate about…". Weave in JD keywords naturally, front-load concrete outcomes with real numbers (ask for them), and keep it in the user's voice, not LinkedIn-poetry. Surface every place you need a real metric as an explicit `[NEED: …]` question.

### Step 4 — Experience bullets
Rewrite experience bullets for the most recent / most relevant 1–2 roles. Every bullet = action + scope + measurable outcome. Convert "Led cross-functional initiatives" into "Shipped X, now used by Y, cutting Z by N%". Mark each missing figure as `[NEED: …]`. Do not fabricate.

### Step 5 — Skills, Featured, and consistency pass
Align the Skills section to the JD keywords (drop stale ones, add the ones recruiters filter on). Recommend what to pin in Featured. Then do a final read-through for voice consistency and any remaining filler or unverified numbers.

## Closing checklist

Before declaring done, verify:

- [ ] Every section was rewritten in its own step (no stacking)
- [ ] Every number in the final copy is one the **user supplied** — zero invented figures, zero unresolved `[NEED: …]` left as fact
- [ ] Headline and About both open specific and scoped — no banned filler words remain
- [ ] Rewrites are anchored to the supplied JDs' keywords and rewarded outcomes
- [ ] The copy still sounds like the user, not a ghostwriter
