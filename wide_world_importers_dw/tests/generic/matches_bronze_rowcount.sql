{# Staging only renames and casts, so a count differing from its bronze table means a silent
   filter or a source pointed at the wrong schema. One row when the two disagree. #}
{% test matches_bronze_rowcount(model, bronze_relation) %}

with counts as (
    select
        (select count(*) from {{ model }}) as model_rows,
        (select count(*) from {{ bronze_relation }}) as bronze_rows
)

select model_rows, bronze_rows, model_rows - bronze_rows as difference
from counts
where model_rows <> bronze_rows

{% endtest %}
