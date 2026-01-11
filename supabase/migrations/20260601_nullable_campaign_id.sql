-- Migration: Allow nullable campaign_id for inbound/unsolicited leads
-- Problem: Inbound emails create staging_leads without a campaign context,
-- but campaign_id was NOT NULL with a FK constraint to campaigns.
-- Solution: Make campaign_id nullable and keep the FK for when a campaign exists.
--
-- Run this migration in Supabase SQL Editor or via CLI:
--   supabase db push (if using local dev)
--   OR paste into SQL Editor in Supabase Dashboard

-- Step 1: Drop the foreign key constraints (they enforce NOT NULL implicitly via referential integrity)
ALTER TABLE "public"."staging_leads" 
    DROP CONSTRAINT IF EXISTS "staging_leads_campaign_id_fkey";

ALTER TABLE "public"."leads" 
    DROP CONSTRAINT IF EXISTS "leads_campaign_id_fkey";

-- Step 2: Make campaign_id nullable
ALTER TABLE "public"."staging_leads" 
    ALTER COLUMN "campaign_id" DROP NOT NULL;

ALTER TABLE "public"."leads" 
    ALTER COLUMN "campaign_id" DROP NOT NULL;

-- Step 3: Re-add foreign key constraints (but now allowing NULL)
-- ON DELETE SET NULL: if campaign is deleted, lead's campaign_id becomes NULL
ALTER TABLE "public"."staging_leads" 
    ADD CONSTRAINT "staging_leads_campaign_id_fkey" 
    FOREIGN KEY ("campaign_id") 
    REFERENCES "public"."campaigns"("id") 
    ON DELETE SET NULL;

ALTER TABLE "public"."leads" 
    ADD CONSTRAINT "leads_campaign_id_fkey" 
    FOREIGN KEY ("campaign_id") 
    REFERENCES "public"."campaigns"("id") 
    ON DELETE SET NULL;

-- Step 4: Add helpful index for querying leads without campaigns (inbound)
CREATE INDEX IF NOT EXISTS "idx_staging_leads_null_campaign" 
    ON "public"."staging_leads" ("id") 
    WHERE "campaign_id" IS NULL;

CREATE INDEX IF NOT EXISTS "idx_leads_null_campaign" 
    ON "public"."leads" ("id") 
    WHERE "campaign_id" IS NULL;

-- Verification query (run after migration):
-- SELECT table_name, column_name, is_nullable 
-- FROM information_schema.columns 
-- WHERE column_name = 'campaign_id' 
--   AND table_name IN ('staging_leads', 'leads');
