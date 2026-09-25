{# Staging only renames and casts, so a count differing from its raw table means a silent
   filter or a source pointed at the wrong schema. One row when the two disagree. #}
{% test matches_source_rowcount(model, source_relation) %}

with counts as (
    select
        (select count(*) from {{ model }}) as model_rows,
        (select count(*) from {{ source_relation }}) as source_rows
)

select model_rows, source_rows, model_rows - source_rows as difference
from counts
where model_rows <> source_rows

{% endtest %}
