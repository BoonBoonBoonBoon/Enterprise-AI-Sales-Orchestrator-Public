-- Migration: Force auth signup trigger to AFTER INSERT
-- Date: 2026-02-03
-- Purpose: Ensure membership insert runs after auth.users row exists

-- Recreate trigger with correct timing
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW
    EXECUTE FUNCTION public.create_client_on_signup();
