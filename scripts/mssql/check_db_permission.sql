-- View the effective permissions of wwi_extract on the database
SELECT
    dp.name AS UserName,
    dp.type_desc AS UserType,
    o.name AS ObjectName,
    p.permission_name AS PermissionName,
    p.state_desc AS PermissionState
FROM
    sys.database_principals dp
LEFT JOIN
    sys.database_permissions p ON dp.principal_id = p.grantee_principal_id
LEFT JOIN
    sys.objects o ON o.object_id = p.major_id
WHERE
    dp.name = 'wwi_extract';

-- Verify schema permissions for 'Sales' and other schemas
SELECT
    dp.name AS UserName,
    dp.type_desc AS UserType,
    s.name AS SchemaName,
    p.permission_name AS PermissionName,
    p.state_desc AS PermissionState
FROM
    sys.database_principals dp
LEFT JOIN
    sys.database_permissions p ON dp.principal_id = p.grantee_principal_id
LEFT JOIN
    sys.schemas s ON s.schema_id = p.major_id
WHERE
    dp.name = 'wwi_extract';


SELECT
    dp.name AS UserName,
    o.name AS ObjectName,
    p.permission_name AS PermissionName,
    p.state_desc AS PermissionState
FROM
    sys.database_principals dp
LEFT JOIN
    sys.database_permissions p ON dp.principal_id = p.grantee_principal_id
LEFT JOIN
    sys.objects o ON o.object_id = p.major_id
WHERE
    dp.name = 'wwi_extract' AND p.state_desc = 'DENY';

SELECT
    schemas.name AS SchemaName,
    objects.name AS TableName,
    security_policies.name AS PolicyName
FROM
    sys.security_policies
JOIN
    sys.objects ON security_policies.parent_object_id = objects.object_id
JOIN
    sys.schemas ON objects.schema_id = schemas.schema_id;

SELECT
    c.name AS ColumnName,
    t.name AS TableName,
    m.is_masked,
    m.masking_function
FROM
    sys.masked_columns m
JOIN
    sys.columns c ON m.column_id = c.column_id AND m.object_id = c.object_id
JOIN
    sys.tables t ON c.object_id = t.object_id
WHERE
    m.is_masked = 1;

-- Diagnostic only: this lists masked columns, it does not change them.
-- A previous version ended with GRANT UNMASK. Do not add it back — ingest masked
-- values and unmask at the serving layer instead.

