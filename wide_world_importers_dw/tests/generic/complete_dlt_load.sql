{# dlt replaces a table by emptying it first, then loads the tables one commit at a time, and a
   package only reaches _dlt_loads with status 0 once all of them are in. So a raw table belongs
   to one complete load when it is non-empty, carries a single _dlt_load_id, and that id is the
   newest complete load. A load that died halfway fails here: empty tables, or tables from a
   load that never completed. `make build` runs these on their own before `dbt build`, because
   inside `dbt build` a failing source test does not skip the models that read the source. #}
{% test complete_dlt_load(model) %}

with this_table as (
    select
        count(*) as row_count,
        count(distinct _dlt_load_id) as load_ids,
        max(_dlt_load_id) as load_id
    from {{ model }}
),

last_complete_load as (
    select max(load_id) as load_id
    from {{ source('dlt', 'loads') }}
    where status = 0
)

select
    this_table.row_count,
    this_table.load_ids,
    this_table.load_id,
    last_complete_load.load_id as last_complete_load_id
from this_table
cross join last_complete_load
where this_table.row_count = 0
   or this_table.load_ids <> 1
   or this_table.load_id is distinct from last_complete_load.load_id

{% endtest %}
