{# The manifest's timestamp, not `current_timestamp`, so two builds of one snapshot compare equal. #}
{% macro snapshot_processed_at() -%}
    (
        select cast(snapshot_timestamp as timestamptz)
        from read_json(
            '{{ var("manifest_path", "data/snapshots/manifest.json") }}',
            columns = {snapshot_timestamp: 'varchar'}
        )
    )
{%- endmacro %}
