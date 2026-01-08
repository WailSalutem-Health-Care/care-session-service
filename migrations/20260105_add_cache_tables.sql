-- Create cache tables and new columns in all tenant schemas (org_%).

DO $$
DECLARE
    tenant_schema TEXT;
BEGIN
    FOR tenant_schema IN
        SELECT nspname
        FROM pg_namespace
        WHERE nspname LIKE 'org\_%' ESCAPE '\'
    LOOP
        EXECUTE format('SET search_path TO %I', tenant_schema);

        -- Users cache table (caregivers and other staff)
        EXECUTE '
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                first_name VARCHAR(255) NOT NULL,
                last_name VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                role VARCHAR(50),
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                deleted_at TIMESTAMP
            )
        ';

        -- Add careplan fields to patients cache table
        EXECUTE '
            ALTER TABLE patients
                ADD COLUMN IF NOT EXISTS careplan_type VARCHAR(50),
                ADD COLUMN IF NOT EXISTS careplan_frequency VARCHAR(50)
        ';
    END LOOP;
END $$;
