---
title: Sales orders
---

# Sales orders

Order-line grain. Amounts are **ordered, excluding tax**: they are not revenue, which is invoiced. Every number on this page is a measure of the semantic layer in `semantic/model/`; the page names measures and never defines them.

{% dropdown
    id="brand"
    data="sales"
    value_column="brand"
    title="Brand"
/%}

{% row %}

{% line_chart
    data="sales"
    title="Ordered amount excl. tax by order month"
    x="full_date"
    date_grain="month"
    y="MEASURE(ordered_amount_excl_tax)"
    y_fmt="num1m"
    y_axis_options={title="Ordered amount excl. tax"}
    filters=["brand"]
/%}

{% bar_chart
    data="sales"
    title="In-full rate by customer category"
    x="customer_category_name"
    y="MEASURE(in_full_rate)"
    y_axis_options={title="In-full rate"}
    y_fmt="pct1"
    filters=["brand"]
/%}

{% /row %}
