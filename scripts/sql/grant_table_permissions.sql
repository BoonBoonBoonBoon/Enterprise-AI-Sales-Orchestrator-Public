-- Grant full permissions to authenticated and anon roles
-- This is in addition to RLS policies

GRANT ALL ON clients TO authenticated, anon;
GRANT ALL ON staging_leads TO authenticated, anon;
GRANT ALL ON lead_outreach TO authenticated, anon;
GRANT ALL ON conversations TO authenticated, anon;

-- Also grant usage on sequences if they exist
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO authenticated, anon;

-- Verify grants
SELECT 
    table_name,
    grantee,
    privilege_type
FROM information_schema.table_privileges
WHERE table_name IN ('clients', 'staging_leads', 'lead_outreach', 'conversations')
ORDER BY table_name, grantee, privilege_type;
