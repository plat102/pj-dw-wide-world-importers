{# Most data tests pass on an empty table: no row breaks `not_null`, `unique` or `relationships`.
   One row when the model holds none. #}
{% test not_empty(model) %}

select 1 as no_rows
where not exists (select 1 from {{ model }})

{% endtest %}
