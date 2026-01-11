-- Test script to check JWT claims and RLS policies
-- Run this in Supabase SQL Editor

-- 1. Check if get_user_role function exists
SELECT routine_name, routine_definition 
FROM information_schema.routines 
WHERE routine_schema = 'public' 
AND routine_name = 'get_user_role';

-- 2. Check current RLS policies on clients table
SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
FROM pg_policies
WHERE tablename = 'clients';

-- 3. Test the get_user_role function with current JWT
-- (This will only work when run from Supabase SQL Editor with authenticated session)
SELECT public.get_user_role() as user_role;

-- 4. Check if RLS is enabled on clients table
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE tablename = 'clients';

-- 5. Show what JWT claims are available
SELECT current_setting('request.jwt.claims', true) as jwt_claims;
