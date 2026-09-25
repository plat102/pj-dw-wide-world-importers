{# No `main_` prefix: dbt's default prepends target.schema, which added nothing here. Its reason
   for keeping one -- separating developers in a shared warehouse -- does not apply to one lake. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
