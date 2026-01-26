# Finance Overview, Forecast, and Variance Suite

A lightweight **interactive** finance dashboard built with **Streamlit**.  
It’s designed to be **repeatable**: update the input CSVs, refresh the app, and re-use the same views for monthly/quarterly/yearly reviews.

<img src="doc/home1.png" width="900" />

From the Home page, you can click the three buttons to jump directly to:
- **Overview**
- **Forecast**
- **Variance**

---

## Overview

The **Overview** page helps you quickly understand business performance at different time granularities.

What you can do:
- Choose a **View** level: **Month / Quarter / Year**
- Switch between **KPIs** and **Trends** to see summary metrics or time-series patterns
- Use the page navigation to move between sections easily

<img src="doc/overview1.png" width="900" />
<img src="doc/overview2.png" width="900" />

---

## Forecast

The **Forecast** page focuses on scenario-based planning for new products.

Modes:
- **Single Scenario**: deep dive into one scenario
- **Compare Scenarios**: compare multiple scenarios side-by-side
- **Monte Carlo**: simulate uncertainty based on input distributions

Scenarios available:
- **Base**
- **Downside**
- **Upside**

You can also:
- Choose a **View** level: **Month / Quarter / Year**
- Switch between **KPIs** and **Trends** to view summary numbers or trends

<img src="doc/forecast1.png" width="900" />
<img src="doc/forecast2.png" width="900" />
<img src="doc/forecast3.png" width="900" />
<img src="doc/forecast4.png" width="900" />

---

## Variance

The **Variance** page explains cost variance drivers and helps you drill down from high-level variance to detailed contributors.

Filters:
- **Product**: select **All** or a specific product
- **Driver**: select **All** or a specific driver
- **View** level: **Month / Quarter / Year**

This page is useful for understanding:
- Which drivers explain the variance
- How variance decomposes (e.g., price vs volume)
- Which accounts contribute the most

<img src="doc/variance1.png" width="900" />
<img src="doc/variance2.png" width="900" />