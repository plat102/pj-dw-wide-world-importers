{# dlt stamps every bronze row with the load that wrote it, as a unix timestamp in a varchar.
   Not current_timestamp: it must be constant so two builds of one load compare equal. #}
{% macro processed_at() -%}
    to_timestamp(cast(_dlt_load_id as double))
{%- endmacro %}
