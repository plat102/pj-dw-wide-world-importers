// Cube reads the lake in place, as the read-only identity. No credential lives here: every value comes
// from the container environment, which docker-compose.yml fills from .env.
const { DuckDBDriver } = require('@cubejs-backend/duckdb-driver');

const env = (name) => {
  const value = process.env[name];
  if (!value) throw new Error(`cube.js: ${name} is not set`);
  return value;
};
// SQL string literal; the values never reach a log through this file.
const lit = (value) => `'${String(value).replace(/'/g, "''")}'`;

// The same attach the warehouse uses (src/connectors/ducklake.py), but READ_ONLY. The catalog
// password is not in the DSN: libpq reads PGPASSWORD, so no error message can echo it.
const initSql = [
  `CREATE OR REPLACE SECRET lake_store (TYPE s3, KEY_ID ${lit(env('LAKE_S3_ACCESS_KEY'))}, ` +
    `SECRET ${lit(env('LAKE_S3_SECRET_KEY'))}, ENDPOINT ${lit(env('LAKE_S3_ENDPOINT'))}, ` +
    `URL_STYLE 'path', USE_SSL false, REGION 'us-east-1')`,
  `ATTACH ${lit(
    `ducklake:postgres:dbname=${env('LAKE_CATALOG_DB')} host=${env('LAKE_CATALOG_HOST')} ` +
      `port=${env('LAKE_CATALOG_PORT')} user=${env('LAKE_CATALOG_USER')}`,
  )} AS lake (DATA_PATH ${lit(env('LAKE_DATA_PATH'))}, METADATA_SCHEMA 'public', READ_ONLY)`,
].join(';\n');

// The stock driver's `initSql` option swallows errors ("error on init sql (skipping)"): /readyz
// stays green and every query then fails with `Catalog "lake" does not exist`. So the attach runs
// here instead, and throws; then one real fact row is read, because a `WHERE false` probe passes
// with a wrong S3 key. `configureConnection` is internal to the driver: re-run `make bi_check`
// after bumping the image.
class StrictDuckDBDriver extends DuckDBDriver {
  async configureConnection(connection) {
    await super.configureConnection(connection);
    try {
      await connection.run(initSql);
      const canary = await connection.runAndReadAll(
        'SELECT 1 FROM lake.core.fct_sales_order_line LIMIT 1',
      );
      if (canary.getRows().length === 0) throw new Error('lake.core.fct_sales_order_line is empty');
    } catch (error) {
      // DuckDB messages do not echo the SQL text, so no secret is in error.message.
      throw new Error(`DuckLake attach failed: ${error.message}`);
    }
  }
}

module.exports = {
  driverFactory: () => new StrictDuckDBDriver({}),
};
