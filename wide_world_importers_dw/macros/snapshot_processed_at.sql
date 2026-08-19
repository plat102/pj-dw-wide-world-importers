{#
    The timestamp a row was processed, taken from the snapshot manifest rather than the clock.
    `current_timestamp` made every staging view change on every build, so no two builds of the
    same snapshot could be compared. One snapshot now has exactly one processed_at.
#}
{% macro snapshot_processed_at() -%}
    (
        select cast(snapshot_timestamp as timestamptz)
        from read_json(
            '{{ var("manifest_path", "data/snapshots/manifest.json") }}',
            columns = {snapshot_timestamp: 'varchar'}
        )
    )
{%- endmacro %}
