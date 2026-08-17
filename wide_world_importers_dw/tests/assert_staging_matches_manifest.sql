-- Every staging model must carry exactly as many rows as the manifest recorded for its
-- source table. Staging does renames and casts only, so any difference means either a
-- silent filter crept into a model or the Parquet on disk is not the snapshot the manifest
-- describes. Row count is the cheap half of the contract; verify_snapshot.py checks the
-- SHA256 that catches changes a count cannot see.

with manifest as (
    select unnest(json_keys(tables)) as source_table, tables
    from read_json(
        '{{ var("manifest_path", "data/snapshots/manifest.json") }}',
        columns = {tables: 'json'}
    )
),

declared as (
    select source_table,
           cast(json_extract_string(tables, '$."' || source_table || '".row_count') as bigint) as manifest_rows
    from manifest
),

built as (
    select 'application__cities' as source_table, count(*) as model_rows from {{ ref('stg_application_city') }}
    union all select 'application__countries', count(*) from {{ ref('stg_application_country') }}
    union all select 'application__delivery_methods', count(*) from {{ ref('stg_application_delivery_method') }}
    union all select 'application__people', count(*) from {{ ref('stg_application_person') }}
    union all select 'application__state_provinces', count(*) from {{ ref('stg_application_state_province') }}
    union all select 'purchasing__supplier_categories', count(*) from {{ ref('stg_purchasing_supplier_category') }}
    union all select 'purchasing__suppliers', count(*) from {{ ref('stg_purchasing_supplier') }}
    union all select 'sales__buying_groups', count(*) from {{ ref('stg_sales_buying_group') }}
    union all select 'sales__customer_categories', count(*) from {{ ref('stg_sales_customer_category') }}
    union all select 'sales__customers', count(*) from {{ ref('stg_sales_customer') }}
    union all select 'sales__order_lines', count(*) from {{ ref('stg_sales_order_line') }}
    union all select 'sales__orders', count(*) from {{ ref('stg_sales_order') }}
    union all select 'warehouse__colors', count(*) from {{ ref('stg_warehouse_color') }}
    union all select 'warehouse__package_types', count(*) from {{ ref('stg_warehouse_package_type') }}
    union all select 'warehouse__stock_items', count(*) from {{ ref('stg_warehouse_stock_item') }}
)

-- A missing manifest entry fails too: the inner join would hide it, so compare on the left.
select
    built.source_table,
    built.model_rows,
    declared.manifest_rows
from built
left join declared using (source_table)
where declared.manifest_rows is null
   or built.model_rows <> declared.manifest_rows
