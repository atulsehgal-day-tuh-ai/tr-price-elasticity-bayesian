# Bayesian Price Elasticity (Brand-Level) — What We’re Modeling and Why

## The business goal (in one paragraph)
We want to quantify **how Sparkling Ice demand changes when price changes**, while separating out other forces that also move sales (promotions, competitor/private label price, seasonality, and long-term trends). The result is a decision-ready answer like: *“If we raise base price 3%, what’s the probability revenue goes up vs down?”*—with an honest measure of uncertainty.

---

## 1) Why Bayesian vs “classical” stats (with a simple analogy, then our data)

### Simple analogy
Think of **classical statistics** like taking **one photo** of a moving object: you get a single estimate (plus a confidence interval that people often misinterpret).  
Think of **Bayesian statistics** like making a **short video**: you see a *range of plausible positions over time* and can directly answer “how likely is X?”

- **Classical** (common output): “Elasticity is -2.0, 95% CI [-2.6, -1.4]”
- **Bayesian** (what we can say): “There’s an **87% probability** elasticity is below -1.8, and a **65% probability** a 5% price increase reduces revenue.”

### Why Bayesian fits *our* data
Our Circana data is **weekly**, **noisy**, and affected by multiple overlapping drivers:
- **Base price** moves slowly (strategic decisions)
- **Promotions** create short spikes (tactical actions)
- **Private label price** moves the market basket
- **Seasonality** and time trends shift baseline demand

Bayesian modeling is ideal here because it:
- Produces **full uncertainty distributions** (not just one point estimate)
- Supports **hierarchical pooling** across retailers (see #8)
- Lets us make **probability statements** that business teams can use for risk-managed decisions

---

## 10) MCMC in plain English (chains, sampling, and why it’s needed)
Bayesian models don’t usually have a simple “plug-in formula” that spits out the answer. Instead, we approximate the answer by simulation using **Markov Chain Monte Carlo (MCMC)**.

- **Posterior distribution**: the “video” of plausible parameter values after seeing our data.
- **A chain**: one independent “explorer” walking around the landscape of plausible values.
- **Sampling within a chain**: each step is one plausible set of parameters (elasticities, seasonal effects, noise, etc.).
- **Why multiple chains**: like sending **multiple hikers** into the same valley from different starting points. If they all spend time in the same good areas, we trust the result more.
- **Burn-in / tuning**: early steps are used to find stable movement; we don’t count them as final evidence.

We run (by default) **multiple chains** with **thousands of samples** so we can:
- Ensure the result is stable (chains “agree”)
- Quantify uncertainty reliably (credible intervals, probabilities)

---

## What models are we running (the short version)
We fit one of two Bayesian demand models on weekly data:

### Model A — “Simple” (pooled) Bayesian model
Use when you want one overall elasticity across retailers (or you’re analyzing a single retailer).

### Model B — Hierarchical Bayesian model (partial pooling)
Use when multiple retailers differ (BJ’s vs Sam’s), but we still want stable estimates even when one retailer has fewer informative weeks.

Both models are built as **log-demand** models so elasticities are directly interpretable.

---

## 2) Why we estimate **two price elasticities** (base vs promo)
In Version 2 of this project, we separate:
- **Base Price Elasticity** (strategic): response to *permanent/regular* price moves  
- **Promotional Elasticity** (tactical): response to *temporary discounting*

Why this matters:
- Promotions typically generate **bigger short-term lifts** than base price moves (urgency, stock-up, visibility).
- If you mix them, you can overstate “pricing power” or understate promo ROI.

How we do it with our data:
- Circana provides **Base Dollar Sales / Base Unit Sales** (regular-price behavior) and total sales.
- We compute:
  - **Base price** = Base $ / Base Units  
  - **Average paid price** = Total $ / Total Units  
  - **Promo depth** = (Avg / Base) − 1  
    - 0 means no discount; negative means discounted (e.g., -0.10 ≈ 10% off on average)

This yields two clean decision levers: **base price** and **discount depth**.

---

## 4) Our promotion approach (and why we don’t split Feature vs Display vs Feature+Display)
Circana includes merchandising breakdowns (Feature Only, Display Only, Feature+Display). We *could* model each separately, but we intentionally start simpler:

### Our current approach
We model promotion primarily as **promo depth derived from base vs average price** (and/or a promo intensity proxy when needed). This:
- Captures **all price reductions**, including TPR-like effects (not just “merch-tagged” promos)
- Produces a **single, interpretable promotional elasticity**
- Reduces multicollinearity and overfitting risk (feature/display variables often overlap and are sparse)

### Why not split them (for now)
Separating “visibility” (display/feature) from “price discount” is valuable, but it requires:
- Stronger data coverage (enough weeks in each promo type)
- Careful identification (feature/display often coincide with price cuts)
- More model complexity (more parameters → more compute + more uncertainty)

**Upgrade path** (if needed): add explicit Feature/Display variables later to answer trade-spend allocation questions like “display vs price cut ROI.”

---

## 5) How seasonality is factored
Seasonality is included as **season dummy variables** derived from the week’s month:
- Spring (Mar–May), Summer (Jun–Aug), Fall (Sep–Nov)  
(Winter becomes the implicit baseline)

This removes predictable seasonal demand swings so price elasticity isn’t accidentally “crediting” a seasonal lift/drop.

---

## 6) How holidays are factored (current state + best practice)
**Current baseline:** we do **not** add explicit holiday flags in the core pipeline.  
However, holiday effects are partially absorbed by:
- **Promotions** (holiday weeks often coincide with discounting)
- **Seasonality** and **time trend**
- The model’s error term (unexplained demand shocks)

**Best practice / recommended next step:** add a small set of holiday indicators (e.g., week-of Thanksgiving, Christmas/New Year, July 4) or a “holiday period” feature. That would further isolate holiday-driven spikes from true price response.

---

## 3) Why not modeling UPC-level within a brand is still OK
We’re modeling **brand-level demand** (Sparkling Ice total) rather than every UPC. That is appropriate when the decisions are brand-level:
- Annual base price strategy
- Promo depth planning
- Retailer comparisons
- Competitive/private label positioning

Why it’s acceptable statistically:
- UPC mix shifts mostly change the **intercept / baseline level**, while our elasticity is identified from **week-to-week variation** in price and promotions.
- If UPC mix shifts are not extreme or are correlated with promotions (which we explicitly model), the remaining elasticity estimate is still meaningful at the brand level.
- Brand-level modeling is also more robust when the number of weeks is limited relative to the number of UPCs.

If UPC-level questions become important (“which pack size is most sensitive?”), we can extend to a UPC hierarchy later.

---

## 7) Why our elasticity is “closer to real”
In practice, “naïve” elasticity is biased because price changes coincide with other drivers. Our approach explicitly removes major confounders:

- **Promo depth**: separates temporary discount effects from base pricing
- **Private label price**: controls for competitor pressure and category price umbrella
- **Seasonality**: removes recurring calendar-driven changes
- **Time trend**: accounts for gradual demand changes (distribution, awareness, macro effects)

This doesn’t make the estimate perfect (no model can), but it makes it **far closer to causal price response** than a simple price-vs-sales correlation.

---

## 8) Why hierarchical models (partial pooling)?
Retailers differ: shoppers, pack mix, promo cadence, and competitive dynamics vary by club.

Hierarchical modeling gives us the best of both worlds:
- **Retailer-specific elasticities** (BJ’s vs Sam’s)
- **Stability** when one retailer has fewer informative weeks  
  (estimates “borrow strength” from the overall pattern instead of becoming noisy)

Business translation: it prevents overreacting to limited data while still respecting real retailer differences.

---

## 11) Why this work needs better parallel compute
Bayesian MCMC is compute-intensive because:
- We run **multiple chains** (each is a full model fit)
- We generate **thousands of samples** per chain for stable uncertainty estimates
- Hierarchical + dual-elasticity models have **more parameters**, increasing compute

Good news: chains are naturally parallelizable. More cores allow:
- Running chains simultaneously
- Faster turnaround on “what-if” scenarios and sensitivity runs
- More robust diagnostics without waiting hours

---

## 9) What business questions this analysis will answer
This system is designed to answer questions like:

### Strategic pricing (Base Price Elasticity)
- “If we raise base price by 3–5%, what’s the expected volume and revenue impact?”
- “How much pricing power do we have at each retailer?”
- “What’s the downside risk (probability revenue declines) for a proposed increase?”

### Promotional planning (Promotional Elasticity)
- “What is the ROI of a 10% discount vs 15% discount?”
- “Are we more promo-responsive at BJ’s or Sam’s?”
- “How much incremental volume do promos generate, net of seasonality and trend?”

### Competitive positioning (Cross-price vs Private Label)
- “When private label price changes, how much does Sparkling Ice demand shift?”
- “Which retailer is more vulnerable to PL pricing moves?”

### Forecasting and risk management (Bayesian advantage)
- “What’s the probability elasticity is more negative than -2.0?”
- “What’s the probability a promo plan hits a volume target?”

---

## Summary: the “story” in one line
We’re using **Bayesian (MCMC) demand models** to estimate **two clean elasticities (base vs promo)**, control for **competitor price, seasonality, and trend**, and (when needed) **hierarchically pool across retailers**—so leadership gets **decision-grade** answers with transparent uncertainty and risk.

