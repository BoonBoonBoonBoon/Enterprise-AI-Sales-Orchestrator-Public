-- Diagnostic script to check JWT claims extraction
-- Run this in Supabase SQL Editor while authenticated with custom JWT

-- First, check what claims are available in the JWT
SELECT current_setting('request.jwt.claims', true) as all_jwt_claims;

-- Check specific claims
SELECT 
  (current_setting('request.jwt.claims', true)::jsonb->>'role')::text as jwt_role,
  (current_setting('request.jwt.claims', true)::jsonb->>'user_role')::text as user_role_claim,
  (current_setting('request.jwt.claims', true)::jsonb->>'sub')::text as subject;

-- Test the get_user_role function
SELECT public.get_user_role() as extracted_user_role;

-- Check current policies on clients table
SELECT policyname, permissive, roles, cmd, qual::text
FROM pg_policies
WHERE tablename = 'clients'
ORDER BY policyname;

-- Check if RLS is enabled
SELECT tablename, rowsecurity
FROM pg_tables
WHERE tablename = 'clients';
