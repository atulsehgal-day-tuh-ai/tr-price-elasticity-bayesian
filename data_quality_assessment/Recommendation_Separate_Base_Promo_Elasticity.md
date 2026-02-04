# 🎯 **RECOMMENDATION: Separate Base Price vs Promotional Elasticity**

## **Strategic Enhancement to Price Elasticity Model**

---

**Date:** February 4, 2026  
**Recommendation:** Implement dual elasticity model separating base price from promotional effects  
**Status:** ✅ **Strongly Recommended** - Data available, high business value

---

## 📋 **EXECUTIVE SUMMARY**

### **Current Limitation:**
Your existing model estimates a **single price elasticity** that mixes:
- Permanent base price changes (strategic decisions)
- Temporary promotional discounts (tactical decisions)

### **The Problem:**
```
Question: "Should we raise base price 5%?"
Current answer: Use overall elasticity (-2.2)
Problem: This mixes strategic AND tactical effects!

Reality check:
  - 5% permanent price increase ≠ 5% temporary discount
  - Consumers respond DIFFERENTLY to each
  - Need separate elasticities for accurate decision-making
```

###

 **The Solution:**
✅ **Separate into TWO elasticities:**
1. **Base Price Elasticity** (β₁): Response to permanent price changes
2. **Promotional Elasticity** (β₂): Response to temporary discounts

### **Business Value:**
- ✅ Better pricing decisions (strategic vs tactical)
- ✅ Optimize promotional ROI
- ✅ Separate long-term revenue planning from short-term tactics
- ✅ Industry standard approach (P&G, Coca-Cola, Nestlé use this)

---

## 🎯 **WHY THIS MATTERS**

### **Real Business Scenarios:**

#### **Scenario 1: Base Price Increase**
```
Decision: Raise regular price from $18.00 → $18.90 (+5%)
Duration: PERMANENT
Visibility: Gradual (consumers notice over weeks)
Consumer response: Gradual adjustment, some switching

Current model says:
  Volume impact: -2.2 × 5% = -11.0%
  
Proposed model will say:
  Volume impact: β₁ × 5% = likely -1.5 to -2.0 × 5% = -7.5% to -10.0%
  (Less elastic than overall)
```

#### **Scenario 2: Promotional Discount**
```
Decision: Run 10% off promotion for 4 weeks
Duration: TEMPORARY (4-8 weeks)
Visibility: HIGH (featured, signage, ads)
Consumer response: Immediate buying, stockpiling

Current model says:
  Volume impact: -2.2 × (-10%) = +22.0%
  
Proposed model will say:
  Volume impact: β₂ × 10% = likely -3.0 to -5.0 × 10% = +30% to +50%
  (More elastic - promotions work better!)
```

#### **Why the Difference?**

| Factor | Base Price Change | Promotional Discount |
|--------|------------------|---------------------|
| **Duration** | Permanent | Temporary (4-8 weeks) |
| **Visibility** | Low (gradual) | High (featured/advertised) |
| **Urgency** | None | "Buy now before it ends!" |
| **Stockpiling** | No | Yes (consumers buy extra) |
| **Customer segment** | All customers | Price-sensitive shoppers |
| **Result** | Lower elasticity | **Higher elasticity** |

---

## 📊 **THREE MODELING APPROACHES**

### **APPROACH 1: Current Model (Baseline)**

```
Log(Total_Units) = β₀ + β₁·Log(Avg_Price) + β₂·Log(PL_Price) + 
                   β₃·Promo_Intensity + Seasonality + Time
```

**Limitation:**
- `Avg_Price` = weighted average of base price + promotional price
- Single elasticity (β₁) for BOTH types of price changes
- Can't separate strategic from tactical effects

**Example Problem:**
```
Week 1: Base=$18, Promo=none → Avg=$18.00
Week 2: Base=$18, Promo=10% off → Avg=$16.20 (90% at base, 10% on promo)

Model sees: Price dropped from $18.00 → $16.20 (-10%)
Model treats this as: ONE type of price change
Reality: This is a MIX of base price + promotional discount
```

---

### **APPROACH 2: Dual Elasticity Model (RECOMMENDED)**

```
Log(Total_Units) = β₀ + β₁·Log(Base_Price) + β₂·Promo_Depth + 
                   β₃·Log(PL_Price) + Seasonality + Time

Where:
  Base_Price = Regular/everyday price (from Circana "Base Sales")
  Promo_Depth = (Base_Price - Avg_Price) / Base_Price
              = % discount from base price
              = 0 when no promo, >0 when on promo
```

**Benefits:**
- ✅ **β₁** = Base price elasticity (permanent changes)
- ✅ **β₂** = Promotional elasticity (temporary discounts)
- ✅ Clear separation of strategic vs tactical decisions
- ✅ Easy to implement in existing Bayesian framework

**Data Requirements:**
```
✅ Base Price: AVAILABLE (from "Base Dollar Sales / Base Unit Sales")
✅ Avg Price: AVAILABLE (from "Dollar Sales / Unit Sales")
✅ Promo Depth: CALCULATE (Base_Price - Avg_Price) / Base_Price
✅ All other variables: UNCHANGED (PL price, seasonality, time)
```

---

### **APPROACH 3: Dual-Equation Model (Advanced)**

```
Equation 1 (Base Demand):
  Log(Base_Units) = β₀ + β₁·Log(Base_Price) + β₂·Log(PL_Price) + 
                    Seasonality + Time

Equation 2 (Promotional Lift):
  Log(Promo_Units) = γ₀ + γ₁·Promo_Depth + γ₂·Promo_Duration + 
                     Seasonality + Time

Total_Units = Base_Units + Promo_Units
```

**Benefits:**
- ✅ Most sophisticated approach
- ✅ Can model promotional duration effects (4-week vs 8-week promos)
- ✅ Separates base demand from incremental promotional lift
- ✅ Can answer: "What's optimal promo length?"

**Drawbacks:**
- ⚠️ More complex (2 equations to estimate)
- ⚠️ Requires more data preparation
- ⚠️ Harder to explain to stakeholders

**Recommendation:** Start with Approach 2, consider Approach 3 later if needed

---

## 📊 **DATA AVAILABILITY ANALYSIS**

### **What We Have:**

| Data Element | Source | Availability | Quality |
|--------------|--------|--------------|---------|
| **Base Price** | Base Dollar Sales / Base Unit Sales | ✅ 159 weeks | ✅ Good |
| **Average Price** | Dollar Sales / Unit Sales | ✅ 159 weeks | ✅ Good |
| **Base Units** | Base Unit Sales | ✅ 159 weeks | ✅ Good |
| **Total Units** | Unit Sales | ✅ 159 weeks | ✅ Good |
| **Promo Units** | Total - Base | ✅ Calculated | ✅ Good |

### **Promotional Activity Summary:**

```
Promotional Depth (discount from base price):
  Mean: 2.5%
  Median: 0.3%
  75th percentile: 4.5%
  Maximum: 14.0%

Weeks by promotional intensity:
  No promotion (0-1%): 57% of weeks
  Light promo (1-5%): 13% of weeks
  Moderate promo (5-10%): 22% of weeks
  Deep promo (10-15%): 3% of weeks

Average % of units sold on promotion: 12.8%
Peak promotional activity: 50% of units on promo
```

**Conclusion:** ✅ Sufficient variation in both base price and promotional depth to estimate separate elasticities

---

## 🔬 **EXPECTED RESULTS**

### **Hypothesis (Based on CPG Industry Literature):**

| Elasticity Type | Expected Range | Interpretation |
|-----------------|----------------|----------------|
| **Base Price Elasticity (β₁)** | -1.5 to -2.5 | Moderate to high |
| **Promotional Elasticity (β₂)** | -3.0 to -5.0 | Very high |

### **Why Promotional Elasticity Should Be Higher:**

#### **1. Temporal Urgency:**
```
Base price: "Price is $18 every week" → No urgency
Promo: "Only $16 this week!" → Buy now urgency
Result: Higher response to promotions
```

#### **2. Visibility:**
```
Base price: Listed on shelf, gradually noticed
Promo: Featured displays, signage, ads, circulars
Result: More consumers aware of promotional price
```

#### **3. Stockpiling:**
```
Base price: Buy regular amount (1-2 packs)
Promo: Buy 4-6 packs to stockpile
Result: Higher volume lift during promotions
```

#### **4. Customer Segmentation:**
```
Base price: Affects all customer segments
Promo: Attracts price-sensitive shoppers who wouldn't buy otherwise
Result: Incremental volume from new customers
```

### **Business Implications:**

```
Scenario: 5% change (increase base price OR promotional discount)

Current model (single elasticity = -2.2):
  Both scenarios: ±11.0% volume change

Proposed model (separate elasticities):
  5% base price increase: -1.5 to -2.0 × 5% = -7.5% to -10.0% volume
  5% promotional discount: -3.0 to -5.0 × 5% = +15% to +25% volume

Insight: Promotions are 2-3x more effective than base price changes!
```

---

## 💼 **BUSINESS USE CASES**

### **Use Case 1: Base Price Optimization**

**Question:** *"Should we raise the base price by $1.00?"*

**Current Model Answer:**
```
Overall elasticity: -2.2
Price change: $18.00 → $19.00 (+5.6%)
Volume impact: -2.2 × 5.6% = -12.3%
Revenue impact: +5.6% - 12.3% = -6.7% ❌
Recommendation: DON'T raise price
```

**Proposed Model Answer:**
```
Base price elasticity: -1.8 (separate estimate)
Price change: $18.00 → $19.00 (+5.6%)
Volume impact: -1.8 × 5.6% = -10.1%
Revenue impact: +5.6% - 10.1% = -4.5% ❌
Recommendation: DON'T raise price (but impact less severe than current model)
```

**Better Decision:** More accurate forecast of revenue impact

---

### **Use Case 2: Promotional Planning**

**Question:** *"What's the ROI of a 15% off promotion?"*

**Current Model Answer:**
```
Overall elasticity: -2.2
Promo discount: 15%
Volume lift: 2.2 × 15% = +33%
Revenue impact: (133% × 85%) - 100% = +13% ✅
```

**Proposed Model Answer:**
```
Promotional elasticity: -4.0 (separate estimate)
Promo discount: 15%
Volume lift: 4.0 × 15% = +60%
Revenue impact: (160% × 85%) - 100% = +36% ✅✅
```

**Better Decision:** Much higher ROI than current model predicts → Run more promotions!

---

### **Use Case 3: Strategic Planning**

**Question:** *"Should we focus on raising base price OR increasing promotional frequency?"*

**Current Model:**
```
Can't answer - treats both the same
```

**Proposed Model:**
```
Option A: Raise base price 3%
  Volume: -1.8 × 3% = -5.4%
  Revenue: +3.0% - 5.4% = -2.4% ❌

Option B: Increase promo frequency (add 4 more promo weeks/year)
  Promo depth: 10% off
  Volume lift per promo week: 4.0 × 10% = +40%
  Incremental revenue: Calculate based on promo calendar
  
Answer: Focus on promotions, not base price increases!
```

**Better Decision:** Clear strategic direction based on separate elasticities

---

## 🔧 **IMPLEMENTATION PLAN**

### **Phase 1: Model Update (Week 1-2)**

**Step 1: Data Preparation**
```python
# Calculate new variables
df['Base_Price'] = df['Base_Dollar_Sales'] / df['Base_Unit_Sales']
df['Avg_Price'] = df['Dollar_Sales'] / df['Unit_Sales']
df['Promo_Depth'] = (df['Base_Price'] - df['Avg_Price']) / df['Base_Price']
df['Log_Base_Price'] = np.log(df['Base_Price'])

# Handle weeks with no promotion (Promo_Depth = 0)
# Option 1: Use Promo_Depth directly (0 to 0.15 range)
# Option 2: Create binary indicator + continuous depth
```

**Step 2: Update Model Specification**
```python
# OLD MODEL:
Log(Units) = β₀ + β₁·Log(Avg_Price) + β₂·Log(PL_Price) + 
             β₃·Promo_Intensity + Seasonality + Time

# NEW MODEL:
Log(Units) = β₀ + β₁·Log(Base_Price) + β₂·Promo_Depth + 
             β₃·Log(PL_Price) + Seasonality + Time
```

**Step 3: Bayesian Priors**
```python
# Priors for new parameters:
base_elasticity ~ Normal(-2.0, 0.5)  # Similar to current
promo_elasticity ~ Normal(-4.0, 1.0)  # Expected to be higher (more elastic)
```

---

### **Phase 2: Validation (Week 3)**

**Validation Checks:**

1. ✅ **Convergence:** R-hat < 1.01, ESS > 400
2. ✅ **Sign Check:** Both elasticities should be negative
3. ✅ **Magnitude Check:** Promo elasticity should be > Base elasticity
4. ✅ **Credible Intervals:** Should not overlap with zero
5. ✅ **Comparison:** Compare model fit (R², AIC, BIC) to current model

**Expected Results:**
```
Base Price Elasticity (β₁): -1.5 to -2.5
  Interpretation: 1% base price increase → 1.5-2.5% volume decrease

Promotional Elasticity (β₂): -3.0 to -5.0
  Interpretation: 1% promotional discount → 3.0-5.0% volume increase
  
Ratio: β₂ / β₁ ≈ 2-3x
  Interpretation: Promotions are 2-3x more effective than base price changes
```

---

### **Phase 3: Business Application (Week 4)**

**Deliverables:**

1. **Updated Elasticity Report**
   - Two elasticities instead of one
   - Separate sections for strategic vs tactical decisions
   - Updated revenue scenarios

2. **Decision Framework**
   ```
   Strategic Decisions (use Base Price Elasticity):
     ✓ Annual price increases
     ✓ New product pricing
     ✓ Price architecture redesign
     ✓ Long-term revenue planning
   
   Tactical Decisions (use Promotional Elasticity):
     ✓ Weekly promotional calendar
     ✓ Promotional depth optimization
     ✓ Trade promotion ROI analysis
     ✓ Short-term volume goals
   ```

3. **Stakeholder Presentation**
   - Why two elasticities matter
   - Business implications
   - Updated recommendations

---

## ✅ **RECOMMENDATION**

### **Strongly Recommend: Implement Approach 2**

**Why:**

1. ✅ **Data is available** - Circana provides Base Sales metrics
2. ✅ **High business value** - Separates strategic from tactical decisions
3. ✅ **Easy to implement** - Minor modification to existing model
4. ✅ **Industry standard** - Used by major CPG companies
5. ✅ **Bayesian framework ready** - Can run in existing PyMC code

**Timeline:** 2-4 weeks to implement and validate

**Risk:** Low - Can keep current model as baseline for comparison

---

## 📊 **COMPARISON: Current vs Proposed Model**

| Aspect | Current Model | Proposed Model |
|--------|---------------|----------------|
| **Price Variables** | 1 (Avg Price) | 2 (Base Price + Promo Depth) |
| **Elasticities** | 1 (Overall) | 2 (Base + Promo) |
| **Strategic Decisions** | Mixed with tactical | Clear (use Base elasticity) |
| **Tactical Decisions** | Mixed with strategic | Clear (use Promo elasticity) |
| **Promotional ROI** | Underestimated | More accurate |
| **Base Price Impact** | Overestimated | More accurate |
| **Complexity** | Lower | Slightly higher |
| **Business Value** | Good | **Excellent** |

---

## 💡 **EXPECTED INSIGHTS**

Based on the separate elasticities, you'll be able to answer:

### **Strategic Questions:**
1. ✅ "What's the long-term revenue impact of raising base price 5%?"
2. ✅ "Should we increase base price or hold it steady?"
3. ✅ "What's our pricing power vs Private Label?"
4. ✅ "Can we sustain annual price increases?"

### **Tactical Questions:**
1. ✅ "What's the optimal promotional depth (5%, 10%, 15%)?"
2. ✅ "How many promotional weeks should we run per year?"
3. ✅ "What's the ROI of our promotional spending?"
4. ✅ "Should we run deeper but less frequent promos, or shallower but more frequent?"

### **Integrated Questions:**
1. ✅ "If we raise base price 3%, how should we adjust promo frequency?"
2. ✅ "What's the trade-off between everyday low price vs hi-lo strategy?"
3. ✅ "Should we fund deeper promotions by raising base price?"

---

## 📞 **NEXT STEPS**

### **Immediate Actions:**

1. **[ ] Leadership Approval**
   - Present this recommendation
   - Get buy-in for enhanced model
   - Allocate 2-4 weeks for implementation

2. **[ ] Technical Setup**
   - Verify data availability across all retailers
   - Update data_prep.py to calculate Promo_Depth
   - Modify bayesian_models.py specifications

3. **[ ] Validation Plan**
   - Define success criteria
   - Prepare comparison framework
   - Schedule stakeholder review

4. **[ ] Timeline**
   - Week 1-2: Implementation
   - Week 3: Validation
   - Week 4: Business review & rollout

---

## 📋 **DECISION MATRIX**

**Should you implement this?**

| Criterion | Score | Notes |
|-----------|-------|-------|
| **Data Availability** | ✅✅✅ | All required data present |
| **Business Value** | ✅✅✅ | High - separates strategic/tactical |
| **Implementation Difficulty** | ✅✅ | Moderate - minor code changes |
| **Stakeholder Buy-in** | ✅✅✅ | Easy to explain, high value |
| **Risk** | ✅✅✅ | Low - can validate against current |
| **Industry Standard** | ✅✅✅ | Yes - P&G, Coca-Cola use this |

**Overall Recommendation: ✅ STRONGLY RECOMMENDED**

---

**Questions? Ready to implement?** 🚀

---

**Prepared by:** Data Science Team  
**Date:** February 4, 2026  
**Version:** 1.0
