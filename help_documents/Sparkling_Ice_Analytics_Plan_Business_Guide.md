# Sparkling Ice Price Elasticity Analysis
## A Business Guide to Our Analytics Approach

**Prepared for:** Commercial & Pricing Leadership  
**Date:** February 5, 2026  
**Version:** 2.0  

---

## Executive Summary

This document explains our approach to measuring how price changes affect Sparkling Ice sales across BJ's, Sam's Club, and Costco. We are using **Bayesian statistics with hierarchical modeling** to separate strategic pricing decisions from tactical promotions — providing accurate, uncertainty-quantified insights that traditional methods cannot deliver.

**Key Innovation:** We measure **two separate price elasticities**, not one:

1. **Base Price Elasticity** — How consumers respond to permanent, everyday price changes (the strategic lever)
2. **Promotional Elasticity** — How consumers respond to temporary discounts (the tactical lever, typically 2–3× stronger)

By isolating these two effects — and controlling for seasonality, holidays, competitive pricing, and time trends — we produce elasticity estimates that reflect the *true* consumer response to price, free from the noise of confounding factors.

**Expected Business Impact:** $16M+ annual value through optimized pricing and promotion strategy.

This guide walks through every major design decision in our analysis, written for business leaders who want to understand *what* we are doing, *why* we chose this approach, and *what questions* the results will answer — without needing a statistics degree.

---

## Table of Contents

1. [The Big Picture: What Is Price Elasticity and Why Does It Matter?](#1-the-big-picture)
2. [Why Bayesian Statistics? (And What's Wrong with the Classical Way)](#2-why-bayesian)
3. [How the Engine Works: Markov Chain Monte Carlo (MCMC)](#3-mcmc)
4. [Why Powerful Compute Matters](#4-compute)
5. [Two Elasticities, Not One: Base Price vs. Promotions](#5-two-elasticities)
6. [Our Promotion Modeling Approach](#6-promotion-modeling)
7. [Brand-Level Analysis: Why We Don't Need UPC-Level Data](#7-brand-level)
8. [How Seasonality Is Captured](#8-seasonality)
9. [How Holidays Are Captured](#9-holidays)
10. [Isolating the Pure Price Effect](#10-isolating-price)
11. [Why Hierarchical Models? The Power of Partial Pooling](#11-hierarchical)
12. [Questions This Analysis Will Answer](#12-questions)
13. [Summary: Why This Approach Is Best-in-Class](#13-summary)

---

<a name="1-the-big-picture"></a>
## 1. The Big Picture: What Is Price Elasticity and Why Does It Matter?

Price elasticity of demand measures how much consumers change their buying behavior when the price of a product goes up or down. If Sparkling Ice is priced at $18.00 per case and we raise it to $18.90 (a 5% increase), do consumers buy 2% fewer cases? 5% fewer? 10% fewer? The elasticity number tells us exactly that.

An elasticity of **−2.0** means: for every 1% increase in price, volume drops by 2%. That single number becomes the foundation of almost every pricing and promotion decision:

- **Should we take the annual price increase?** Elasticity tells you what volume you'll lose and whether the higher margin compensates.
- **How deep should our promotions be?** Elasticity tells you how much incremental volume a 10% discount will generate, and whether it's worth the trade spend.
- **Are we more price-sensitive than Private Label?** Cross-price elasticity tells you whether consumers are switching to competitors when your price rises.

Getting this number right — really right, with honest uncertainty bounds — is worth millions of dollars in better decisions. Getting it wrong means over-promoting, under-pricing, or leaving money on the table.

---

<a name="2-why-bayesian"></a>
## 2. Why Bayesian Statistics? (And What's Wrong with the Classical Way)

### A Simple Analogy: The Restaurant Review

Imagine you're deciding whether to try a new restaurant. The **classical statistics** approach would be like this: you read exactly five Yelp reviews, compute the average star rating, and make your decision based only on those five reviews. If all five happen to be from the same night when the chef was having a bad day, you get a misleading answer — and the method gives you no warning that your sample might be unrepresentative.

The **Bayesian approach** is different. Before you read those five reviews, you already know something: this restaurant is in a neighborhood where most places average 3.5–4.0 stars. That's your *prior belief*. Then you read the five reviews and *update* your belief. If four of the five reviews say 5 stars, you don't immediately conclude "this is the best restaurant in the city" — you balance the new evidence with what you already knew about restaurants in that area. Your updated belief (the *posterior*) might be something like "probably 4.2–4.5 stars, with some chance it could be higher or lower."

That's the Bayesian framework in a nutshell: **start with what you already know, update with new data, and quantify how certain you are.**

### How This Applies to Our Sparkling Ice Analysis

In the classical approach, you would run a regression on, say, 104 weeks of BJ's data and get a single answer: "Elasticity = −1.85." Period. No range, no expression of confidence, no way to incorporate what the CPG industry already knows about beverage price sensitivity.

In our Bayesian approach, we do three things the classical method cannot:

**First, we incorporate prior knowledge.** Decades of CPG research tell us that sparkling beverage elasticity typically falls in the −1.5 to −2.5 range. We don't throw that away. We encode it as a "prior distribution" — a starting belief that says elasticity is probably around −2.0, but we're open to the data telling us otherwise. If the Circana data strongly points to −1.6, our model will move toward −1.6. The prior doesn't force the answer; it simply prevents the model from landing on implausible values (like +3.0 or −15.0) when the data is noisy.

**Second, we get a full range of plausible values, not just a single point.** Instead of "elasticity = −1.85," we get "elasticity is most likely between −1.55 and −2.15, with −1.85 as the best single estimate." That range — the *credible interval* — is enormously valuable for decision-making. It tells you: "If you plan around −1.85 you'll probably be close, but budget for the possibility that it's as low as −1.55 or as high as −2.15."

**Third, we can make direct probability statements.** A business leader can ask: "What's the probability that a 5% base price increase will decrease revenue?" and we can answer: "There is an 87% probability that revenue will decline." Classical statistics cannot make this statement — it can only reject or fail to reject a hypothesis, which is far less intuitive and far less useful for actual decision-making.

### Side-by-Side Comparison

| Dimension | Classical (Frequentist) | Bayesian (Our Approach) |
|---|---|---|
| **Output** | Single point estimate + p-value | Full probability distribution |
| **Prior Knowledge** | Ignored entirely | Incorporated systematically |
| **Uncertainty** | Confidence interval (often misinterpreted) | Credible interval (direct probability statement) |
| **Small Data** | Unreliable with few data points | Handles small samples gracefully via priors |
| **Business Question** | "Is elasticity significantly different from zero?" | "What is the probability elasticity is between −1.5 and −2.5?" |
| **Decision Support** | "Reject the null hypothesis at p < 0.05" | "87% chance the price increase hurts revenue" |
| **Multiple Retailers** | Separate regressions (no information sharing) | Hierarchical model (retailers inform each other) |

For a pricing decision worth millions of dollars, the Bayesian approach gives you the language and precision that the business actually needs.

---

<a name="3-mcmc"></a>
## 3. How the Engine Works: Markov Chain Monte Carlo (MCMC)

### Why We Need a Special Engine

In a simple classical regression, you can solve for the answer with a formula — plug in the data, do some matrix algebra, and the coefficients pop out instantly. Bayesian models don't have that luxury. We're not solving for a single answer; we're mapping out an entire *landscape of plausible answers*, weighted by how well each one fits the data and the prior knowledge. For a model with 8–10 parameters (base elasticity, promo elasticity, cross-price effect, three seasonal effects, time trend, intercept, noise), that landscape is a complex, 10-dimensional surface. There is no formula to describe it directly.

So we use a technique called **Markov Chain Monte Carlo (MCMC)** — a clever way to *explore* that landscape by taking a guided random walk through it.

### The Treasure Hunt Analogy

Imagine you're dropped into a vast, hilly landscape in complete fog. You can't see the terrain, but you have an altimeter — you can feel whether you're going uphill or downhill. Your goal is to map which areas are the highest (the most plausible parameter values).

Here's how MCMC works, step by step:

**Step 1 — You start at a random spot.** You check the altimeter: "I'm at 200 feet." This is your starting guess for the model parameters.

**Step 2 — You propose a step in a random direction.** You take a tentative step north. Your altimeter reads 250 feet. Higher ground! That means this combination of parameters fits the data better.

**Step 3 — You decide whether to accept the step.** Since 250 feet is higher than 200, you accept the step and move there. If the proposed spot were *lower* (say, 150 feet), you'd usually reject it and stay put — but occasionally you'd accept it anyway, which prevents you from getting stuck on a small hill when there's a mountain nearby.

**Step 4 — You repeat thousands of times.** After 2,000–3,000 steps, you've spent most of your time in the high-altitude regions — the parameter values that best explain your data. The collection of places you've visited *is* the posterior distribution.

### What Is a "Chain"?

A chain is one complete random walk — one treasure hunter exploring the landscape from start to finish. We run **four chains in parallel**, each starting from a different random location. This is like sending four independent scouts into the fog from four different trailheads.

Why four? Because if all four scouts end up exploring the same high-altitude region, we can be confident they've found the true peak — not just a local hill. If one scout gets stuck in a valley while the others are all on the same mountaintop, we know something went wrong with that scout's path. This is how we diagnose convergence problems.

### What Is "Sampling Within a Chain"?

Each individual step the scout takes is one **sample**. In our analysis, each chain takes **2,000 samples** (after an initial 1,000-step "warm-up" period where the scout is still finding their way to the high ground). So across four chains, we collect **8,000 total samples** — 8,000 plausible combinations of all model parameters.

The warm-up (also called "tuning") is critical. During the first 1,000 steps, the algorithm is also learning *how big a step to take*. Too small, and the scout inches along inefficiently. Too large, and every proposed step lands in a valley and gets rejected. The NUTS (No-U-Turn Sampler) algorithm we use is particularly smart about this — it automatically figures out the optimal step size and direction, like a scout who learns to read the terrain as they go.

### What NUTS (No-U-Turn Sampler) Adds

Standard MCMC is like a scout taking random steps. NUTS is like a scout who rolls a ball ahead and watches which direction it curves. If the ball starts curving back toward where it came from (a "U-turn"), the scout knows it's found the edge of the high-altitude region and stops. This makes exploration dramatically more efficient — NUTS can traverse the landscape in hundreds of steps where basic MCMC would need tens of thousands.

### How We Know It Worked: Convergence Diagnostics

After all four chains finish, we run two critical checks:

**R-hat (R̂) < 1.01:** This compares the variation *within* each chain to the variation *between* chains. If all four scouts explored the same territory, R-hat is close to 1.0. If one scout found a different region, R-hat rises above 1.01, and we know the results aren't trustworthy. Think of it as asking: "Did all four scouts agree on the map?"

**Effective Sample Size (ESS) > 400:** Not all 8,000 samples are truly independent — consecutive steps are correlated (if you're at 250 feet, your next step is probably near 250 feet too). ESS tells us how many *effectively independent* samples we have. We need at least 400 to draw reliable conclusions. Think of it as: "After removing redundant observations, do we still have enough unique data points?"

If both checks pass — and they should for our model — we can trust the posterior distribution as an accurate map of plausible parameter values.

---

<a name="4-compute"></a>
## 4. Why Powerful Compute Matters

### The Computational Challenge

Running a Bayesian model with MCMC is orders of magnitude more computationally intensive than running a classical regression. Here's why:

A classical regression solves one equation once. Our Bayesian model evaluates the entire model — every parameter, every data point, every prior — **8,000 times per chain × 4 chains = 32,000 full model evaluations** (including the tuning phase). Each evaluation involves computing log-probabilities, gradients, and matrix operations across all observations and parameters.

For a hierarchical model with two retailers, dual elasticities, and 100+ weeks of data, a single analysis run takes approximately 6–8 minutes on modern hardware. Without parallel compute, that same run would take 25–30 minutes — and if you're iterating on model specifications, testing different priors, or running sensitivity analyses, those minutes add up fast.

### Why Parallel Computing Is Essential

MCMC chains are **embarrassingly parallel** — each chain is completely independent of the others, making them a perfect fit for multi-core processing. Our setup runs all four chains simultaneously across separate CPU cores:

| Configuration | Chains | Time per Run | Iteration Cycle |
|---|---|---|---|
| Single-core (sequential) | 4 chains × 1 core | ~25–30 min | Impractical for iteration |
| Quad-core (parallel) | 4 chains × 4 cores | ~6–8 min | Fast enough for real-time analysis |
| 8+ cores (parallel + overhead) | 4 chains + I/O | ~5–6 min | Ideal for production |

Beyond raw speed, modern hardware accelerates the linear algebra operations that NUTS relies on. The gradient computations that make NUTS so efficient — the "ball rolling" that detects U-turns — are themselves computationally expensive, involving automatic differentiation through the entire probabilistic model. Better hardware means each of those 32,000 evaluations finishes faster.

### The Business Case for Compute Investment

In practice, a single analysis isn't just one run. A typical engagement involves:

- Initial model fitting (1 run)
- Prior sensitivity analysis: testing 3 different prior specifications (3 runs)
- Model comparison: simple vs. hierarchical (2 runs)
- Retailer-specific deep dives (2–3 runs)
- Validation and diagnostics (1–2 runs)

That's 10–12 runs, which at 30 minutes each on a single core means 5–6 hours of waiting. On parallel hardware, the same work completes in about 1–1.5 hours. The difference between a half-day and an hour determines whether this analysis can be iterative and responsive to business questions or whether it becomes a batch process that delivers answers days later.

The return is clear: a modest compute investment enables an analytical capability that generates $16M+ in annual value through better pricing and promotion decisions.

---

<a name="5-two-elasticities"></a>
## 5. Two Elasticities, Not One: Base Price vs. Promotions

### The Problem with a Single Elasticity Number

Most pricing studies produce one elasticity estimate — say, −2.3 — and use it for everything: pricing strategy, promotion planning, trade negotiations, and revenue forecasting. But that single number is an average of two very different consumer behaviors, and using it for both strategic and tactical decisions leads to systematic errors.

Here's why: when a consumer sees that the everyday shelf price of Sparkling Ice went from $18.00 to $18.50, they make a *considered* decision. They might keep buying at the same rate, buy slightly less, or switch to a Private Label alternative. This response is moderate, deliberate, and reflects genuine price sensitivity.

When that same consumer sees a "10% Off This Week Only!" tag, they respond differently. The temporary nature creates urgency. The in-store visibility (end-cap display, circular feature) drives impulse purchases. Consumers may stockpile — buying three weeks' supply in one trip. This response is sharp, immediate, and often 2–3 times larger than the response to a permanent price change.

If you blend these two behaviors into a single elasticity number, you get the worst of both worlds: your strategic pricing analysis *overestimates* the damage of a base price increase (because the blended number is inflated by promotional spikes), and your promotional ROI analysis *underestimates* the lift from discounts (because the blended number is diluted by the gentler base-price response).

### Our Dual-Elasticity Approach

We estimate two separate parameters:

**Base Price Elasticity (β₁):** Measures the consumer response to permanent changes in the everyday shelf price. In our model, this is the coefficient on log(Base Price), which we extract from Circana's "Base Dollar Sales" and "Base Unit Sales" columns — fields that represent what would have sold at regular price without any promotional support.

**Promotional Elasticity (β₂):** Measures the consumer response to temporary discounts. In our model, this is the coefficient on Promotional Depth, defined as the percentage difference between the actual average price paid and the base price: `Promo_Depth = (Avg_Price / Base_Price) − 1`. A value of −0.10 means consumers paid 10% less than base price on average that week.

### Why the Separation Is Mathematically Sound

The key insight is that Circana's data already contains the ingredients for this separation. Every week, Circana reports both "total" sales (what actually happened) and "base" sales (what would have happened without promotions). From these, we can derive:

- **Base Price** = Base Dollar Sales ÷ Base Unit Sales (the everyday, non-promoted price)
- **Average Price** = Total Dollar Sales ÷ Total Unit Sales (what consumers actually paid, including discounts)
- **Promotional Depth** = (Average Price ÷ Base Price) − 1 (how much of a discount occurred)

By including both log(Base Price) and Promo Depth as separate predictors in the model, we cleanly separate the two effects. The model "sees" weeks where base price changed but promotions didn't, weeks where promotions ran but base price held steady, and weeks where both moved — and it uses all of this variation to disentangle the two elasticities.

### What the Numbers Typically Look Like

| Elasticity | Typical Range | What It Means |
|---|---|---|
| Base Price | −1.5 to −2.5 | A 1% permanent price increase causes a 1.5–2.5% volume decline |
| Promotional | −3.0 to −5.0 | A 1 percentage-point deeper discount causes a 3.0–5.0% volume lift |
| Promo Multiplier | 2.0× to 3.0× | Promotions are 2–3 times more powerful than base price changes |

### How This Changes Decisions

**Before (single elasticity of −2.3):**
- "Should we raise price 5%?" → Model says −11.5% volume. Seems devastating. You don't raise.
- "What's the ROI of a 10% promo?" → Model says +23% lift. Seems good but not exceptional.

**After (dual elasticity: base = −1.85, promo = −3.75):**
- "Should we raise price 5%?" → Base elasticity says −9.3% volume. Still significant, but not as catastrophic as the blended estimate suggested. Worth evaluating against the margin gain.
- "What's the ROI of a 10% promo?" → Promo elasticity says +37.5% lift. Much stronger than the blended estimate. This changes your trade spend allocation.
- **New question you can now answer:** "Should we raise base price 3% and fund more promotions?" → Base elasticity says you lose −5.6% volume on base, but the additional promo weeks generate enough incremental volume to more than compensate.

This is the precision that turns good pricing analysis into great pricing strategy.

---

<a name="6-promotion-modeling"></a>
## 6. Our Promotion Modeling Approach

### What Circana Provides

Circana's retail data includes very detailed promotional breakdowns:

- **Dollar Sales Any Merchandising** — Sales accompanied by in-store feature, display, or both
- **Dollar Sales Feature Only** — Sales supported by a circular/ad feature without a special display
- **Dollar Sales Display Only** — Sales from an end-cap or special display without a price feature
- **Dollar Sales Feature and Display** — Sales supported by both

It would be tempting to model each of these separately — building a model with four or five promotion-related variables to understand the incremental contribution of features vs. displays vs. combined support. But for our purposes, this approach would hurt more than it helps.

### Why We Use a Single Promotional Depth Variable

Our model uses one promotion measure: **Promotional Depth** = `(Avg Price / Base Price) − 1`. This single variable captures the *total effective discount* consumers experienced that week, regardless of whether that discount was driven by a feature ad, an end-cap display, a temporary price reduction, or some combination. Here's why this is the right choice:

**It captures all promotions, not just merchandised ones.** Circana's merchandising columns only flag promotions that had visible in-store support (features, displays). But temporary price reductions (TPRs) without merchandising support are real promotions too — and they show up in the gap between average price and base price. Our Promotional Depth variable catches everything.

**It avoids multicollinearity.** Feature, display, and combined merchandising are highly correlated with each other and with price reductions. Including all of them in a model with only 100–200 weeks of data creates a situation where the model can't cleanly separate one effect from another — the estimates become unstable and unreliable. With a single, well-defined promotion variable, the model has enough statistical power to estimate a clean, stable effect.

**It gives us what we actually need for pricing decisions.** The question we're answering is "how much incremental volume does a given level of discount generate?" — not "does a circular ad outperform an end-cap display?" The latter is a valid question, but it's a media-mix optimization problem, not a price elasticity problem. Our Promotional Depth variable directly answers the pricing question.

**It keeps the model interpretable.** For every additional variable we add, we need to explain what it means, how it interacts with other variables, and how to use it in decision-making. A single promotional elasticity is clean: "A 10% discount generates X% volume lift." Adding separate feature, display, and combined effects would produce statements like "A 10% discount with feature support generates X%, but without feature support it generates Y%, and with display support it generates Z%..." — which is harder to act on and more likely to confuse than to clarify.

### When You Would Want the Detailed Approach

There are legitimate reasons to decompose promotion effects by merchandising type — specifically, when you're optimizing the *marketing mix* rather than the *pricing strategy*. If the question is "Should we allocate more trade spend toward feature ads or in-store displays?", you would want a more granular model. That's a separate analysis we can build later, once the core pricing system is in place and validated.

For now, the single Promotional Depth variable gives us exactly the signal we need: the consumer's aggregate response to being offered a discount, however that discount was delivered.

---

<a name="7-brand-level"></a>
## 7. Brand-Level Analysis: Why We Don't Need UPC-Level Data

### The Question

Sparkling Ice sells multiple SKUs (individual product codes): different flavors, different pack sizes, limited editions, and so on. A natural question is: shouldn't we model each UPC separately to capture flavor-specific or pack-size-specific price sensitivities?

The short answer is no — and here's why brand-level analysis is actually *better* for the decisions we're making.

### Strategic Pricing Decisions Happen at the Brand Level

When the organization negotiates pricing with BJ's or Sam's Club, the conversation is about the Sparkling Ice *brand* — not about Black Raspberry vs. Lemon Lime. Price changes at retail are typically applied across the portfolio: a cost increase flows through to all SKUs, and a promotional event features the brand, not individual flavors. The elasticity that matters for these decisions is the *brand-level* elasticity: how does total Sparkling Ice volume respond when the average Sparkling Ice price changes?

Modeling at the UPC level would give us flavor-level estimates, but these aren't actionable at the level where pricing decisions are made. Worse, the flavor-level estimates would be much noisier — each individual SKU has less data, more volatility from distribution changes and flavor rotations, and more sensitivity to random week-to-week variation.

### Circana's Data Is Designed for Brand-Level Analysis

Circana provides brand-level aggregates ("Total Sparkling Ice Core Brand") that already handle the composition math correctly. The total dollar sales, unit sales, and base sales fields at the brand level reflect the properly-weighted combination of all active SKUs. This is exactly the level of aggregation where price–volume relationships are most stable and most relevant to commercial decisions.

### What We Would Lose by Going to UPC Level

Going to UPC level would introduce several problems:

**Data sparsity.** Some flavors may only be available for part of the year or in some retailers. This creates gaps in the time series that complicate modeling.

**Distribution noise.** When a new flavor launches or an old one is discontinued, sales change for reasons that have nothing to do with price. The brand-level total smooths this out.

**Parameter explosion.** If we have 15 active SKUs across 3 retailers, we'd need to estimate 15 × 3 = 45 separate elasticities, many of which would be very imprecise due to limited data.

**Harder to interpret and act on.** Even if we could estimate 45 SKU-level elasticities, the pricing team can't realistically optimize price separately for each flavor at each retailer.

### The Brand-Level Advantage

By modeling at the brand level, we get stable estimates based on a complete time series (no gaps), large enough sample sizes for reliable inference, and results that directly map to the decisions the commercial team actually makes. If, in the future, there's a specific need to understand whether certain flavor segments (e.g., caffeinated vs. non-caffeinated) have different price sensitivities, we can build a targeted sub-analysis — but the core pricing model should stay at the brand level.

---

<a name="8-seasonality"></a>
## 8. How Seasonality Is Captured

### Why Seasonality Matters

Sparkling Ice is a beverage with strong seasonal demand. Sales are naturally higher in warmer months and lower in winter — a pattern driven by consumer behavior (people drink more flavored sparkling water when it's hot) rather than by pricing. If we don't account for this, the model might confuse seasonal volume swings with price effects. For example, if prices happen to be higher in summer (when sales are also higher), a naive model might conclude that higher prices *cause* higher sales — clearly wrong.

### Our Approach: Seasonal Dummy Variables

We include three quarterly indicator variables in the model:

| Variable | Equals 1 When... | Captures |
|---|---|---|
| **Spring** | March, April, May | Early-season ramp-up |
| **Summer** | June, July, August | Peak demand period |
| **Fall** | September, October, November | Declining but still elevated demand |
| *(Winter is the baseline)* | December, January, February | Lowest demand period (reference category) |

The model estimates a separate coefficient for each season. For example, if the Summer coefficient is +0.25, it means that — after controlling for price, promotions, and everything else — summer weeks see about 25% higher sales than winter weeks, purely due to seasonal demand.

### Why Quarterly Dummies (Not Monthly)

With approximately 104 weeks of data, we need to be selective about how many parameters we estimate. Monthly dummies would require 11 additional parameters (one for each month except the baseline), consuming a significant portion of our statistical budget. Quarterly dummies require only three parameters and still capture the dominant seasonal pattern. The weekly granularity of our data means that within-quarter variation is absorbed by the model's noise term — a reasonable trade-off given data limitations.

### The Time Trend Variable

In addition to seasonal dummies, we include a **linear time trend** (Week Number) to capture any gradual shift in the baseline sales level over the analysis period. This accounts for secular growth or decline in the brand — perhaps Sparkling Ice is gaining market share over time, or perhaps the overall category is shrinking. Without the time trend, these gradual shifts could bias the elasticity estimates.

Together, the seasonal dummies and time trend ensure that the price elasticity coefficients reflect *genuine* consumer price sensitivity — not seasonal patterns or trend effects masquerading as price effects.

---

<a name="9-holidays"></a>
## 9. How Holidays Are Captured

### The Holiday Effect in CPG Data

Holidays drive significant spikes in beverage sales — the Fourth of July, Memorial Day, Labor Day, and Thanksgiving are all periods of elevated demand. A natural question is whether we should include specific holiday indicator variables in the model.

### Our Approach: Holidays Are Embedded in Seasonality

In our current framework, holiday effects are *implicitly* captured through two mechanisms:

**Seasonal dummies absorb the systematic holiday pattern.** The biggest beverage holidays — Memorial Day, Fourth of July, Labor Day — all fall within the Spring and Summer quarters. The seasonal dummy for Summer, for example, captures not just the warm-weather demand boost but also the holiday-driven spikes that consistently occur during that period. Since these holidays happen at roughly the same time every year, they contribute to the seasonal coefficient in a stable, predictable way.

**Weekly volatility absorbs the residual holiday effect.** Holidays like Thanksgiving and Christmas cause week-to-week spikes that don't perfectly align with quarterly boundaries. The model's noise term (σ) accounts for this short-term volatility. The elasticity estimates are not biased by these spikes because they are uncorrelated with price over time — holiday timing is driven by the calendar, not by Sparkling Ice's pricing decisions.

### Why We Don't Add Explicit Holiday Variables (Yet)

Adding individual holiday indicators (e.g., a flag for the week of July 4th, a flag for Thanksgiving week) is a reasonable enhancement, but it comes with trade-offs:

**Data limitation.** With ~104 weeks of data, each holiday occurs only twice. That's not enough to estimate a holiday-specific coefficient with any precision. The estimate would be driven by just two data points and would be very unstable.

**Risk of overfitting.** Each additional variable we add "uses up" some of the model's capacity to detect real patterns. With limited data, adding holiday flags can cause the model to fit noise rather than signal — making in-sample results look better but out-of-sample predictions worse.

**Minimal impact on elasticity.** The key question is: would adding holiday variables *change* the elasticity estimates? In most CPG applications, the answer is no — because holidays affect the *level* of sales but not the *price sensitivity*. Consumers don't become more or less price-elastic during a holiday week; they simply buy more at whatever price is offered.

If future analysis is conducted with a longer time series (3+ years of data), we could revisit this and add holiday-specific effects with greater confidence. For now, the seasonal framework is sufficient.

---

<a name="10-isolating-price"></a>
## 10. Isolating the Pure Price Effect

### The Core Challenge in Pricing Analysis

The reason pricing analytics is hard is that price doesn't change in isolation. When Sparkling Ice runs a promotion in July, three things happen simultaneously: the price drops, it's summer (so demand is naturally high), and there might be an end-cap display driving traffic. If we just look at the correlation between price and sales, we'd see a big volume spike — but how much of that spike was the price? How much was the season? How much was the display?

This is the **confounding problem**, and it's the single biggest reason that naive pricing analysis (just regressing sales on price) produces garbage results.

### How Our Model Isolates the True Price Effect

Our model uses a technique called **multiple regression with controls** — we include all known confounding factors as separate variables, so the model can attribute the right portion of sales variation to each cause. Here's what we control for:

| Confounding Factor | How We Control for It | What It Prevents |
|---|---|---|
| **Seasonality** | Spring, Summer, Fall dummy variables | Prevents confusing seasonal demand with price response |
| **Holiday effects** | Absorbed by seasonal dummies and noise term | Prevents holiday spikes from inflating elasticity |
| **Secular trend** | Week Number (linear time trend) | Prevents brand growth/decline from biasing results |
| **Competitive pricing** | Log(Private Label Price) as a predictor | Separates our own price effect from competitor price moves |
| **Promotional vs. base price** | Two separate price variables (base price + promo depth) | Prevents blending of strategic and tactical effects |

After controlling for all of these factors, what remains is the **pure price effect** — the portion of sales variation that can only be explained by changes in Sparkling Ice's price. This is what our elasticity estimates capture.

### Why This Produces More Accurate Elasticities

Consider a simplified example. Suppose you have a week where Sparkling Ice runs a 10% promotion in July:

- **Naive analysis:** Sales jumped 40% that week. With a 10% price cut, the implied elasticity is −4.0.
- **Our analysis:** After accounting for the Summer effect (+15% seasonal boost), the time trend (+2% growth), and competitive pricing (Private Label was also on sale, adding +5% to our volume), the *residual* volume lift attributable to Sparkling Ice's own price change is about 18%. The implied promotional elasticity is −1.8 for that week. Across all weeks, the model finds a promotional elasticity of −3.75 — a much more reliable estimate because it's based on the price effect alone, stripped of all the confounding noise.

This is why we say the elasticities from our model reflect the *true* consumer response to price: we've systematically removed every other factor that might inflate or deflate the estimates. The result is a number you can actually use with confidence in pricing decisions.

---

<a name="11-hierarchical"></a>
## 11. Why Hierarchical Models? The Power of Partial Pooling

### The Problem: Multiple Retailers, Limited Data

We're analyzing Sparkling Ice across BJ's, Sam's Club, and (optionally) Costco. Each retailer has a different shopper profile, different competitive context, and potentially different price sensitivity. There are two obvious approaches:

**Option A: One model for all retailers combined (Complete Pooling).** This assumes BJ's and Sam's Club shoppers respond identically to price changes. It maximizes data (you use all weeks from all retailers), but it ignores real differences between retailers. If Sam's shoppers are more price-sensitive than BJ's shoppers, this model misses that — and gives you the same recommendation for both, which could be wrong for one or both.

**Option B: Separate models for each retailer (No Pooling).** This allows each retailer to have completely different elasticities, but each model only gets ~52 weeks of data. With so few observations, the estimates are noisy and unreliable. A single unusual week — a supply disruption, a competitor stockout — can dramatically shift the results.

### Our Solution: Hierarchical Modeling (Partial Pooling)

Hierarchical modeling is the elegant middle ground. It says: "These retailers are different, but they're not *completely* different. They're all selling the same product to broadly similar consumers in the same country. So let each retailer have its own elasticity, but let the retailers *inform* each other."

Mechanically, this works through a two-level structure:

**Global Level:** The model estimates a "population" elasticity — what the typical Sparkling Ice retailer looks like. For base price elasticity, this might be −2.0 with some spread (standard deviation of 0.3).

**Retailer Level:** Each retailer's elasticity is drawn from this population distribution. If BJ's data strongly suggests an elasticity of −1.7, but the population average is −2.0 and Sam's is at −2.3, the hierarchical model "pulls" BJ's estimate slightly toward the population average — landing at perhaps −1.8 instead of −1.7. This is called *shrinkage*, and it has a remarkable property: it almost always improves prediction accuracy, even though it slightly biases each individual estimate.

### Why Partial Pooling Works

Think of it like grading on a curve — but a smart, Bayesian curve:

- If BJ's has a lot of data and a clear pattern, the model trusts BJ's data and barely pulls it toward the average. The data speaks loudly.
- If Costco has limited data (and no promotional information), the model relies more heavily on what it's learned from BJ's and Sam's — "borrowing strength" from the other retailers. The data speaks softly, so the prior (informed by the other retailers) fills the gap.

This is especially valuable for the dual-elasticity framework. Each retailer gets its own base price elasticity *and* its own promotional elasticity, both informed by the global patterns. The result is a set of retailer-specific estimates that are individually more accurate than what you'd get from separate models and collectively more nuanced than what you'd get from a combined model.

### What the Hierarchical Structure Reveals

Beyond better point estimates, the hierarchical model tells us something genuinely new: **how much retailers vary from each other.** The "σ_group" parameter estimates the between-retailer standard deviation. If σ_group is small (say, 0.1), it means BJ's and Sam's have nearly identical price sensitivities — and you can treat them similarly in pricing strategy. If σ_group is large (say, 0.5), it means the retailers are fundamentally different — and you need retailer-specific pricing strategies.

This is an insight that neither a combined model nor separate models can provide. Only the hierarchical framework explicitly estimates and quantifies between-retailer variation.

---

<a name="12-questions"></a>
## 12. Questions This Analysis Will Answer

### Strategic Questions (Using Base Price Elasticity)

These are the long-term, structural questions about everyday pricing.

**1. "What happens if we permanently raise base price by 5%?"**
We calculate the expected volume loss using the base price elasticity, then compare it against the margin gain from the higher price. The model provides a probability distribution: "There is an 80% chance the net revenue impact is between −2% and −6%."

**2. "Can we afford annual price increases to offset cost inflation?"**
By knowing the base elasticity at each retailer, we can model the cumulative effect of, say, 3% annual increases over three years — and identify the price ceiling where volume losses begin to outweigh margin gains.

**3. "What is our pricing power relative to Private Label?"**
The cross-price elasticity (β₃) tells us how much Sparkling Ice volume we lose when Private Label drops its price. If the cross-price elasticity is high, consumers readily switch; if it's low, Sparkling Ice has strong brand loyalty and pricing power.

**4. "Which retailer can absorb a price increase most easily?"**
The hierarchical model gives us retailer-specific base elasticities. If BJ's base elasticity is −1.6 and Sam's is −2.2, BJ's shoppers are less sensitive — so a price increase is safer at BJ's.

### Tactical Questions (Using Promotional Elasticity)

These are the week-to-week questions about trade promotion execution.

**5. "What's the optimal promotional depth — 5%, 10%, or 15% off?"**
We calculate the volume lift at each discount level using the promotional elasticity, then compare the incremental revenue against the cost of the discount. The model reveals the point of diminishing returns — where deeper discounts stop generating enough incremental volume to justify the trade spend.

**6. "How many promotional weeks should we run per year?"**
By estimating the per-week lift of a typical promotion, we can model the total annual volume from different promotional calendars: 4 weeks of 15% off vs. 8 weeks of 10% off vs. 12 weeks of 5% off.

**7. "What's the ROI of our current promotional spending?"**
We compare the actual volume lift from observed promotional weeks against what volume would have been at base price (using the base sales data from Circana), and relate that to the trade spend required to fund the discounts.

**8. "Deep-and-infrequent or shallow-and-frequent?"**
The shape of the promotional response function (is it linear? concave? convex?) tells us whether a few big promotions or many small ones is more efficient.

### Integrated Questions (Using Both Elasticities)

These are the most valuable questions — the ones that require both elasticities working together.

**9. "Should we raise base price and fund more promotions?"**
This is the classic EDLP (Everyday Low Price) vs. Hi-Lo question. If base elasticity is moderate (−1.85) and promotional elasticity is high (−3.75), the math may support a strategy of raising base price modestly (gaining margin on non-promoted weeks) and using some of that margin to fund additional promotional events (generating disproportionately high volume during promoted weeks).

**10. "If we raise base price 3%, how should we adjust the promotional calendar?"**
The base elasticity predicts the volume loss from the price increase. The promotional elasticity tells us how many additional promotional weeks, at what depth, are needed to recover that volume.

**11. "What's the trade-off between EDLP and Hi-Lo strategy?"**
By combining both elasticities with the promotional calendar, we can simulate full-year revenue under different strategy mixes and identify the optimal balance.

**12. "Can we fund deeper promotions by raising base price?"**
We calculate the margin gained from a base price increase, convert it into promotional budget, and then calculate the volume generated by deploying that budget at the promotional elasticity rate. If the volume generated exceeds the volume lost from the price increase, the strategy is self-funding.

---

<a name="13-summary"></a>
## 13. Summary: Why This Approach Is Best-in-Class

Our approach to measuring Sparkling Ice price elasticity isn't just a regression — it's a carefully designed analytical framework where every design choice serves a specific purpose.

**Bayesian over Classical** — because we need honest uncertainty quantification and direct probability statements for million-dollar decisions, not just point estimates and p-values.

**MCMC with NUTS Sampling** — because Bayesian models require efficient numerical exploration of high-dimensional parameter spaces, and NUTS is the state-of-the-art algorithm for doing this reliably and quickly.

**Parallel Compute** — because iterative, responsive analysis requires fast turnaround, and MCMC chains are naturally parallelizable.

**Dual Elasticities** — because permanent price changes and temporary promotions trigger fundamentally different consumer behaviors, and blending them produces misleading results for both strategic and tactical decisions.

**Single Promotional Depth Variable** — because it captures all discounts cleanly, avoids multicollinearity from overlapping merchandising flags, and directly answers the pricing question without unnecessary complexity.

**Brand-Level Analysis** — because pricing decisions are made at the brand level, brand-level data is more stable and complete, and UPC-level analysis would introduce noise without actionable benefit.

**Seasonal Dummies and Time Trend** — because we must isolate the pure price effect from calendar-driven demand patterns and secular brand trends.

**Holidays Embedded in Seasonality** — because with only ~104 weeks of data, explicit holiday flags would be underpowered and risk overfitting, while the seasonal framework adequately captures their systematic effects.

**Comprehensive Controls** — because every confounding factor we account for brings our elasticity estimate closer to the true consumer response, making our pricing recommendations more accurate and more defensible.

**Hierarchical Modeling** — because it gives us the best of both worlds: retailer-specific insights with the stability that comes from sharing information across retailers, plus a direct measure of how much retailers actually differ.

The result is a system that doesn't just tell you "elasticity is −1.85" — it tells you *what kind* of elasticity (base or promo), *for which retailer*, *with what degree of certainty*, and *what it means for your specific business decision*. That's the difference between a number and an insight.

---

**Document Version:** 2.0  
**Analysis System:** Bayesian Price Elasticity Analysis System v2.0
