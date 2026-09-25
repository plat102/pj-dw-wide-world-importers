{# Attributes that appear in more than one place -- dim_date and dim_person are role-played.
   Described once so the obt and the dimension cannot drift apart in wording. #}

{% docs date__full_date %}The calendar date itself.{% enddocs %}
{% docs date__year %}Calendar year.{% enddocs %}
{% docs date__year_week %}ISO year and week as `yyyyww`. The ISO year, so the last days of December can belong to the next one.{% enddocs %}
{% docs date__year_day %}Calendar year and day-of-year as `yyyyddd`.{% enddocs %}
{% docs date__fiscal_year %}Fiscal year. Wide World Importers starts its year in April, so April 2024 falls in FY2025.{% enddocs %}
{% docs date__fiscal_qtr %}Fiscal quarter as `Q1`–`Q4`, counted from April.{% enddocs %}
{% docs date__month %}Calendar month, 1–12.{% enddocs %}
{% docs date__month_name %}Month name in English.{% enddocs %}
{% docs date__week_day %}Day of week, 1 = Sunday through 7 = Saturday.{% enddocs %}
{% docs date__day_name %}Day name in English.{% enddocs %}
{% docs date__day_is_weekday %}1 on Monday–Friday, 0 on Saturday and Sunday.{% enddocs %}

{% docs person__full_name %}The person's full name as the source holds it.{% enddocs %}
{% docs customer__name %}The customer's trading name.{% enddocs %}
