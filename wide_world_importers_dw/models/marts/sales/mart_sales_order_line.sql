{{ config(materialized='table', schema='mart') }}

-- The column list is written out rather than generated. It used to come from six
-- get_filtered_columns_in_relation calls, three of which were dead -- the person, stock item
-- and package type lists were computed and never used, so the columns they were meant to
-- produce were hand-written a few lines below anyway. Worse, a generated list means an
-- upstream column arrives here silently: the mart is the published surface, so a new column
-- should be a decision, not a side effect. `contract: enforced` in schema.yml holds this
-- list to what is declared there.

select
    -- Fact measures and degenerate dimensions. Every foreign key is deliberately absent:
    -- the mart carries the attribute, so a consumer never needs to join back.
    fsol.sales_order_line_key
    , fsol.sales_order_key
    , fsol.quantity
    , fsol.unit_price
    , fsol.tax_rate
    , fsol.picked_quantity
    , fsol.backorder_order_key
    , fsol.is_undersupply_backordered
    , fsol.sales_order_line_processed_at

    -- Customer
    , dim_customer.customer_name as customer_customer_name
    , dim_customer.customer_category_name as customer_customer_category_name
    , dim_customer.buying_group_name as customer_buying_group_name
    , dim_customer.primary_contact_full_name as customer_primary_contact_full_name
    , dim_customer.primary_contact_is_system_user as customer_primary_contact_is_system_user
    , dim_customer.primary_contact_is_employee as customer_primary_contact_is_employee
    , dim_customer.primary_contact_is_salesperson as customer_primary_contact_is_salesperson
    , dim_customer.primary_contact_phone_number as customer_primary_contact_phone_number
    , dim_customer.primary_contact_email_address as customer_primary_contact_email_address
    , dim_customer.alternate_contact_full_name as customer_alternate_contact_full_name
    , dim_customer.delivery_method_name as customer_delivery_method_name
    , dim_customer.delivery_city_name as customer_delivery_city_name
    , dim_customer.delivery_state_province_name as customer_delivery_state_province_name
    , dim_customer.delivery_state_province_population as customer_delivery_state_province_population
    , dim_customer.delivery_country_name as customer_delivery_country_name
    , dim_customer.delivery_country_formal_name as customer_delivery_country_formal_name
    , dim_customer.delivery_country_type as customer_delivery_country_type
    , dim_customer.delivery_country_population as customer_delivery_country_population
    , dim_customer.credit_limit as customer_credit_limit
    , dim_customer.standard_discount_percentage as customer_standard_discount_percentage
    , dim_customer.is_on_credit_hold as customer_is_on_credit_hold
    , dim_customer.payment_term_days as customer_payment_term_days
    , dim_customer.phone_number as customer_phone_number
    , dim_customer.website_url as customer_website_url
    , dim_customer.delivery_address as customer_delivery_address
    , dim_customer.delivery_postal_code as customer_delivery_postal_code
    , dim_customer.postal_address as customer_postal_address
    , dim_customer.postal_postal_code as customer_postal_postal_code

    -- Bill-to customer, resolved from the fact's own key
    , dim_bill_to_customer.customer_name as bill_to_customer_name

    -- People, in their three roles
    , dim_salesperson.person_full_name as salesperson_person_full_name
    , dim_picked_by_person.person_full_name as picked_by_person_person_full_name
    , dim_contact_person.person_full_name as contact_person_person_full_name

    -- Stock item
    , dim_stock_item.stock_item_name
    , dim_stock_item.color_name
    , dim_stock_item.supplier_name
    , dim_stock_item.is_chiller_stock

    -- Package type
    , dim_package_type.package_type_name as package_type_package_type_name

    -- Dates. Order date and expected delivery date get the full calendar; the two
    -- picking-completed dates get only the date itself, because nothing asks for more.
    , dim_order_date.full_date as order_date_full_date
    , dim_expected_delivery_date.full_date as expected_delivery_date_full_date
    , dim_order_date.year as order_date_year
    , dim_expected_delivery_date.year as expected_delivery_date_year
    , dim_order_date.year_week as order_date_year_week
    , dim_expected_delivery_date.year_week as expected_delivery_date_year_week
    , dim_order_date.year_day as order_date_year_day
    , dim_expected_delivery_date.year_day as expected_delivery_date_year_day
    , dim_order_date.fiscal_year as order_date_fiscal_year
    , dim_expected_delivery_date.fiscal_year as expected_delivery_date_fiscal_year
    , dim_order_date.fiscal_qtr as order_date_fiscal_qtr
    , dim_expected_delivery_date.fiscal_qtr as expected_delivery_date_fiscal_qtr
    , dim_order_date.month as order_date_month
    , dim_expected_delivery_date.month as expected_delivery_date_month
    , dim_order_date.month_name as order_date_month_name
    , dim_expected_delivery_date.month_name as expected_delivery_date_month_name
    , dim_order_date.week_day as order_date_week_day
    , dim_expected_delivery_date.week_day as expected_delivery_date_week_day
    , dim_order_date.day_name as order_date_day_name
    , dim_expected_delivery_date.day_name as expected_delivery_date_day_name
    , dim_order_date.day_is_weekday as order_date_day_is_weekday
    , dim_expected_delivery_date.day_is_weekday as expected_delivery_date_day_is_weekday
    , dim_sales_order_picking_completed_date.full_date as sales_order_picking_completed_date_full_date
    , dim_sales_order_line_picking_completed_date.full_date as sales_order_line_picking_completed_date_full_date

from {{ ref('fact_sales_order_line') }} as fsol
left join {{ ref('dim_customer') }}
    on fsol.customer_key = dim_customer.customer_key
left join {{ ref('dim_customer') }} as dim_bill_to_customer
    on fsol.bill_to_customer_key = dim_bill_to_customer.customer_key
left join {{ ref('dim_person') }} as dim_salesperson
    on fsol.salesperson_key = dim_salesperson.person_key
left join {{ ref('dim_person') }} as dim_picked_by_person
    on fsol.picked_by_person_key = dim_picked_by_person.person_key
left join {{ ref('dim_person') }} as dim_contact_person
    on fsol.contact_person_key = dim_contact_person.person_key
left join {{ ref('dim_stock_item') }}
    on fsol.stock_item_key = dim_stock_item.stock_item_key
left join {{ ref('dim_package_type') }}
    on fsol.package_type_key = dim_package_type.package_type_key
left join {{ ref('dim_date') }} as dim_order_date
    on fsol.order_date_key = dim_order_date.date_key
left join {{ ref('dim_date') }} as dim_expected_delivery_date
    on fsol.expected_delivery_date_key = dim_expected_delivery_date.date_key
left join {{ ref('dim_date') }} as dim_sales_order_picking_completed_date
    on fsol.sales_order_picking_completed_date_key = dim_sales_order_picking_completed_date.date_key
left join {{ ref('dim_date') }} as dim_sales_order_line_picking_completed_date
    on fsol.sales_order_line_picking_completed_date_key = dim_sales_order_line_picking_completed_date.date_key
