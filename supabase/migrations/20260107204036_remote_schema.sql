

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_user') THEN
        CREATE ROLE ai_user NOLOGIN;
    END IF;
END $$;


CREATE SCHEMA IF NOT EXISTS "Admin";


ALTER SCHEMA "Admin" OWNER TO "postgres";


CREATE SCHEMA IF NOT EXISTS "Relational";


ALTER SCHEMA "Relational" OWNER TO "postgres";


CREATE EXTENSION IF NOT EXISTS "pg_net" WITH SCHEMA "extensions";






COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgmq";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE OR REPLACE FUNCTION "Relational"."update_updated_at_column"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'Relational', 'pg_temp'
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION "Relational"."update_updated_at_column"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."custom_access_token"("claims" "jsonb") RETURNS "jsonb"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
begin
  -- Check if the user has the 'ai_user' role
  if exists (
    select 1 
    from public.user_roles 
    where user_id = (select auth.uid()) 
      and role = 'ai_user'
  ) then
    return claims || jsonb_build_object('role', 'ai_user');
  end if;
  
  -- Return original claims if not an AI user
  return claims;
end;
$$;


ALTER FUNCTION "public"."custom_access_token"("claims" "jsonb") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."get_user_role"() RETURNS "text"
    LANGUAGE "sql" STABLE SECURITY DEFINER
    AS $$
  SELECT COALESCE(
    (current_setting('request.jwt.claims', true)::jsonb->>'user_role')::text,
    ''
  );
$$;


ALTER FUNCTION "public"."get_user_role"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."update_updated_at_column"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" TO 'public', 'pg_temp'
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."update_updated_at_column"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."agent_subtasks" (
    "Sub Task ID" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "parent_task_id" "uuid" NOT NULL,
    "agent_name" "text" NOT NULL,
    "status" "text" NOT NULL,
    "input" "jsonb" NOT NULL,
    "output" "jsonb",
    "error" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "agent_subtasks_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'running'::"text", 'completed'::"text", 'failed'::"text"])))
);


ALTER TABLE "public"."agent_subtasks" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."agent_tasks" (
    "Task id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid" NOT NULL,
    "status" "text" NOT NULL,
    "input" "jsonb" NOT NULL,
    "output" "jsonb",
    "error" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "workflow_id" "text" DEFAULT ''::"text" NOT NULL,
    "Metadata" "jsonb",
    CONSTRAINT "agent_tasks_status_check" CHECK (("status" = ANY (ARRAY['pending'::"text", 'running'::"text", 'completed'::"text", 'failed'::"text"])))
);


ALTER TABLE "public"."agent_tasks" OWNER TO "postgres";


COMMENT ON COLUMN "public"."agent_tasks"."workflow_id" IS 'Name of the Module preforming Task I.e. Core Logic, Re-engagement etc.';



CREATE TABLE IF NOT EXISTS "public"."audit_log" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid" NOT NULL,
    "user_or_agent" "text" NOT NULL,
    "action" "text" NOT NULL,
    "target_table" "text" NOT NULL,
    "target_id" "uuid",
    "metadata" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"()
);

ALTER TABLE ONLY "public"."audit_log" FORCE ROW LEVEL SECURITY;


ALTER TABLE "public"."audit_log" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."campaigns" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "campaign_name" "text" DEFAULT ''::"text" NOT NULL,
    "campaign_type" "text" NOT NULL,
    "status" "text" NOT NULL,
    "sequence_id" "uuid" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"()
);

ALTER TABLE ONLY "public"."campaigns" FORCE ROW LEVEL SECURITY;


ALTER TABLE "public"."campaigns" OWNER TO "postgres";


COMMENT ON TABLE "public"."campaigns" IS 'This stores the high-level configuration and status of each campaign my clients run.';



CREATE TABLE IF NOT EXISTS "public"."clients" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "name" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone NOT NULL
);


ALTER TABLE "public"."clients" OWNER TO "postgres";


COMMENT ON TABLE "public"."clients" IS 'This table tracks actual clients, allowing a to link all their data in a multi-tenant setup.';



CREATE TABLE IF NOT EXISTS "public"."conversations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "lead_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "channel" "text" NOT NULL,
    "status" "text" NOT NULL,
    "summary" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "thread_id" "text",
    "subject" "text"
);


ALTER TABLE "public"."conversations" OWNER TO "postgres";


COMMENT ON TABLE "public"."conversations" IS 'Conversational Summary and Metadata with the lead.';



CREATE TABLE IF NOT EXISTS "public"."leads" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid" NOT NULL,
    "campaign_id" "uuid" NOT NULL,
    "email" "text" DEFAULT ''::"text" NOT NULL,
    "first_name" "text" NOT NULL,
    "last_name" "text" NOT NULL,
    "company_name" "text" NOT NULL,
    "job_title" "text" NOT NULL,
    "phone_number" "text" NOT NULL,
    "current_status" "text" NOT NULL,
    "sequence_step" bigint NOT NULL,
    "sequence_active" boolean NOT NULL,
    "next_action_date" timestamp with time zone NOT NULL,
    "last_contact_date" timestamp with time zone NOT NULL,
    "sent_timestamps" "jsonb"[],
    "reply_timestamps" "jsonb"[],
    "booking_status" "text" NOT NULL,
    "re_engagement_date" timestamp with time zone NOT NULL,
    "generated_copy_subject" "text",
    "generated_copy_body" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone NOT NULL,
    "crm_id" "text",
    "last_reply_sentiment" "text",
    "lead_score" bigint,
    "qualification_status" "text"
);

ALTER TABLE ONLY "public"."leads" FORCE ROW LEVEL SECURITY;


ALTER TABLE "public"."leads" OWNER TO "postgres";


COMMENT ON TABLE "public"."leads" IS 'This is the core operational table for all lead-specific data.';



CREATE TABLE IF NOT EXISTS "public"."messages" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "conversation_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "sender_type" "text" NOT NULL,
    "text_content" "text" NOT NULL,
    "metadata" "text" NOT NULL,
    "sent_at" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "message_id" "text"
);


ALTER TABLE "public"."messages" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."sequences" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "sequence_name" "text" NOT NULL,
    "steps" "jsonb"[],
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);

ALTER TABLE ONLY "public"."sequences" FORCE ROW LEVEL SECURITY;


ALTER TABLE "public"."sequences" OWNER TO "postgres";


COMMENT ON TABLE "public"."sequences" IS 'This defines the steps and delays for  multi-step campaigns.';



CREATE TABLE IF NOT EXISTS "public"."staging_conversations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "staging_lead_id" "uuid" NOT NULL,
    "status" character varying(50) DEFAULT 'active'::character varying NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "archived_at" timestamp with time zone,
    "thread_id" "text",
    "subject" "text",
    "channel" "text" DEFAULT 'email'::"text"
);


ALTER TABLE "public"."staging_conversations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."staging_leads" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "client_id" "uuid" NOT NULL,
    "campaign_id" "uuid" NOT NULL,
    "source" "text" NOT NULL,
    "email" "text",
    "first_name" "text",
    "last_name" "text",
    "company_name" "text",
    "job_title" "text",
    "phone_number" "text",
    "linkedin_url" "text",
    "website_url" "text",
    "location" "text",
    "industry" "text",
    "company_size" "text",
    "revenue_range" "text",
    "raw_data" "jsonb",
    "duplicate_check_hash" "text",
    "error_log" "text",
    "enrichment_status" "text" DEFAULT 'pending'::"text",
    "qualification_status" "text" DEFAULT 'unqualified'::"text",
    "promotion_ready" boolean DEFAULT false,
    "created_at" timestamp with time zone DEFAULT "now"(),
    "updated_at" timestamp with time zone DEFAULT "now"(),
    "archived_at" timestamp with time zone
);


ALTER TABLE "public"."staging_leads" OWNER TO "postgres";


COMMENT ON TABLE "public"."staging_leads" IS 'Where All Potential Leads are stored until Qualfied';



CREATE TABLE IF NOT EXISTS "public"."staging_messages" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "staging_conversation_id" "uuid" NOT NULL,
    "sender" character varying(255) NOT NULL,
    "receiver" character varying(255) NOT NULL,
    "content" "text" NOT NULL,
    "sent_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "metadata" "jsonb" DEFAULT '{}'::"jsonb" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "archived_at" timestamp with time zone,
    "message_id" "text"
);


ALTER TABLE "public"."staging_messages" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."user_roles" (
    "user_id" "uuid" NOT NULL,
    "role" "text" NOT NULL,
    CONSTRAINT "user_roles_role_check" CHECK (("role" = ANY (ARRAY['ai_user'::"text", 'admin'::"text", 'user'::"text"])))
);


ALTER TABLE "public"."user_roles" OWNER TO "postgres";


ALTER TABLE ONLY "public"."conversations"
    ADD CONSTRAINT "Conversations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."agent_subtasks"
    ADD CONSTRAINT "agent_subtasks_pkey" PRIMARY KEY ("Sub Task ID");



ALTER TABLE ONLY "public"."agent_tasks"
    ADD CONSTRAINT "agent_tasks_pkey" PRIMARY KEY ("Task id");



ALTER TABLE ONLY "public"."audit_log"
    ADD CONSTRAINT "audit_log_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."campaigns"
    ADD CONSTRAINT "campaigns_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."clients"
    ADD CONSTRAINT "clients_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."leads"
    ADD CONSTRAINT "leads_email_key" UNIQUE ("email");



ALTER TABLE ONLY "public"."leads"
    ADD CONSTRAINT "leads_id_key" UNIQUE ("id");



ALTER TABLE ONLY "public"."leads"
    ADD CONSTRAINT "leads_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."sequences"
    ADD CONSTRAINT "sequences_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."staging_conversations"
    ADD CONSTRAINT "staging_conversations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."staging_leads"
    ADD CONSTRAINT "staging_leads_duplicate_check_hash_key" UNIQUE ("duplicate_check_hash");



ALTER TABLE ONLY "public"."staging_leads"
    ADD CONSTRAINT "staging_leads_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."staging_messages"
    ADD CONSTRAINT "staging_messages_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."user_roles"
    ADD CONSTRAINT "user_roles_pkey" PRIMARY KEY ("user_id", "role");



CREATE INDEX "idx_agent_tasks_orchestrator_id" ON "public"."agent_tasks" USING "btree" ("client_id");



CREATE INDEX "idx_leads_client_id" ON "public"."leads" USING "btree" ("client_id");



CREATE INDEX "idx_staging_conversations_lead" ON "public"."staging_conversations" USING "btree" ("staging_lead_id");



CREATE INDEX "idx_staging_conversations_thread" ON "public"."staging_conversations" USING "btree" ("staging_lead_id", "thread_id");



CREATE INDEX "idx_staging_leads_email" ON "public"."staging_leads" USING "btree" ("email");



CREATE INDEX "idx_staging_messages_conv" ON "public"."staging_messages" USING "btree" ("staging_conversation_id");



CREATE INDEX "idx_staging_messages_message" ON "public"."staging_messages" USING "btree" ("staging_conversation_id", "message_id");



CREATE INDEX "idx_user_roles_user_id" ON "public"."user_roles" USING "btree" ("user_id");



CREATE INDEX "ix_staging_conversations_active" ON "public"."staging_conversations" USING "btree" ("archived_at");



CREATE INDEX "ix_staging_conversations_archived_at" ON "public"."staging_conversations" USING "btree" ("archived_at");



CREATE INDEX "ix_staging_leads_active" ON "public"."staging_leads" USING "btree" ("archived_at");



CREATE INDEX "ix_staging_leads_archived_at" ON "public"."staging_leads" USING "btree" ("archived_at");



CREATE INDEX "ix_staging_messages_active" ON "public"."staging_messages" USING "btree" ("archived_at");



CREATE INDEX "ix_staging_messages_archived_at" ON "public"."staging_messages" USING "btree" ("archived_at");



CREATE UNIQUE INDEX "ux_conversations_lead_thread" ON "public"."conversations" USING "btree" ("lead_id", "thread_id") WHERE ("thread_id" IS NOT NULL);



CREATE UNIQUE INDEX "ux_messages_conversation_message_id" ON "public"."messages" USING "btree" ("conversation_id", "message_id") WHERE ("message_id" IS NOT NULL);



CREATE UNIQUE INDEX "ux_staging_conversations_lead_thread" ON "public"."staging_conversations" USING "btree" ("staging_lead_id", "thread_id") WHERE ("thread_id" IS NOT NULL);



CREATE UNIQUE INDEX "ux_staging_messages_conversation_message_id" ON "public"."staging_messages" USING "btree" ("staging_conversation_id", "message_id") WHERE ("message_id" IS NOT NULL);



CREATE OR REPLACE TRIGGER "update_campaigns_updated_at" BEFORE UPDATE ON "public"."campaigns" FOR EACH ROW EXECUTE FUNCTION "public"."update_updated_at_column"();



CREATE OR REPLACE TRIGGER "update_updated_at_column" BEFORE INSERT OR UPDATE ON "public"."campaigns" FOR EACH ROW EXECUTE FUNCTION "Relational"."update_updated_at_column"();



CREATE OR REPLACE TRIGGER "update_updated_at_column" BEFORE INSERT OR UPDATE ON "public"."clients" FOR EACH ROW EXECUTE FUNCTION "Relational"."update_updated_at_column"();



CREATE OR REPLACE TRIGGER "update_updated_at_column" BEFORE INSERT OR UPDATE ON "public"."leads" FOR EACH ROW EXECUTE FUNCTION "Relational"."update_updated_at_column"();



CREATE OR REPLACE TRIGGER "update_updated_at_column" BEFORE INSERT OR UPDATE ON "public"."sequences" FOR EACH ROW EXECUTE FUNCTION "Relational"."update_updated_at_column"();



ALTER TABLE ONLY "public"."conversations"
    ADD CONSTRAINT "Conversations_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id");



ALTER TABLE ONLY "public"."conversations"
    ADD CONSTRAINT "Conversations_lead_id_fkey" FOREIGN KEY ("lead_id") REFERENCES "public"."leads"("id");



ALTER TABLE ONLY "public"."agent_subtasks"
    ADD CONSTRAINT "agent_subtasks_parent_task_id_fkey" FOREIGN KEY ("parent_task_id") REFERENCES "public"."agent_tasks"("Task id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."campaigns"
    ADD CONSTRAINT "campaigns_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id");



ALTER TABLE ONLY "public"."campaigns"
    ADD CONSTRAINT "campaigns_sequence_id_fkey" FOREIGN KEY ("sequence_id") REFERENCES "public"."sequences"("id");



ALTER TABLE ONLY "public"."agent_tasks"
    ADD CONSTRAINT "fk_agent_tasks_client_id" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE RESTRICT;



ALTER TABLE ONLY "public"."leads"
    ADD CONSTRAINT "leads_campaign_id_fkey" FOREIGN KEY ("campaign_id") REFERENCES "public"."campaigns"("id");



ALTER TABLE ONLY "public"."leads"
    ADD CONSTRAINT "leads_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id");



ALTER TABLE ONLY "public"."messages"
    ADD CONSTRAINT "messages_conversation_id_fkey" FOREIGN KEY ("conversation_id") REFERENCES "public"."conversations"("id");



ALTER TABLE ONLY "public"."sequences"
    ADD CONSTRAINT "sequences_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id");



ALTER TABLE ONLY "public"."staging_conversations"
    ADD CONSTRAINT "staging_conversations_staging_lead_id_fkey" FOREIGN KEY ("staging_lead_id") REFERENCES "public"."staging_leads"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."staging_leads"
    ADD CONSTRAINT "staging_leads_campaign_id_fkey" FOREIGN KEY ("campaign_id") REFERENCES "public"."campaigns"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."staging_leads"
    ADD CONSTRAINT "staging_leads_client_id_fkey" FOREIGN KEY ("client_id") REFERENCES "public"."clients"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."staging_messages"
    ADD CONSTRAINT "staging_messages_staging_conversation_id_fkey" FOREIGN KEY ("staging_conversation_id") REFERENCES "public"."staging_conversations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."user_roles"
    ADD CONSTRAINT "user_roles_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



CREATE POLICY "AI user can read active leads" ON "public"."leads" FOR SELECT TO "ai_user" USING (true);



CREATE POLICY "Allow service role full access" ON "public"."leads" TO "service_role" USING (true) WITH CHECK (true);



CREATE POLICY "Copy agent can read active leads" ON "public"."leads" FOR SELECT TO "ai_user" USING (true);



CREATE POLICY "Enable read access for all users" ON "public"."leads" FOR SELECT USING (true);



CREATE POLICY "agent_reader_select" ON "public"."user_roles" FOR SELECT TO "authenticated" USING ((("auth"."jwt"() ->> 'user_role'::"text") = 'agent_reader'::"text"));



ALTER TABLE "public"."agent_subtasks" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."agent_tasks" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "agent_writer_delete" ON "public"."user_roles" FOR DELETE TO "authenticated" USING ((("auth"."jwt"() ->> 'user_role'::"text") = 'agent_writer'::"text"));



CREATE POLICY "agent_writer_insert" ON "public"."user_roles" FOR INSERT TO "authenticated" WITH CHECK ((("auth"."jwt"() ->> 'user_role'::"text") = 'agent_writer'::"text"));



CREATE POLICY "agent_writer_update" ON "public"."user_roles" FOR UPDATE TO "authenticated" USING ((("auth"."jwt"() ->> 'user_role'::"text") = 'agent_writer'::"text")) WITH CHECK ((("auth"."jwt"() ->> 'user_role'::"text") = 'agent_writer'::"text"));



CREATE POLICY "allow_service_role_inserts" ON "public"."leads" FOR INSERT TO "authenticated" WITH CHECK (("current_setting"('request.jwt.claims.role'::"text", true) = 'service_role'::"text"));



ALTER TABLE "public"."audit_log" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."campaigns" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "client_rls_policy" ON "public"."audit_log" USING ((("client_id")::"text" = "current_setting"('app.current_client'::"text", true)));



CREATE POLICY "client_rls_policy" ON "public"."campaigns" USING ((("client_id")::"text" = "current_setting"('app.current_client'::"text", true)));



CREATE POLICY "client_rls_policy" ON "public"."leads" USING ((("client_id")::"text" = "current_setting"('app.current_client'::"text", true))) WITH CHECK ((("client_id")::"text" = "current_setting"('app.current_client'::"text", true)));



CREATE POLICY "client_rls_policy" ON "public"."sequences" USING ((("client_id")::"text" = "current_setting"('app.current_client'::"text", true)));



ALTER TABLE "public"."clients" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "clients_agent_select" ON "public"."clients" FOR SELECT TO "anon" USING (("public"."get_user_role"() = ANY (ARRAY['agent_reader'::"text", 'agent_writer'::"text"])));



CREATE POLICY "clients_agent_write" ON "public"."clients" TO "anon" USING (("public"."get_user_role"() = 'agent_writer'::"text")) WITH CHECK (("public"."get_user_role"() = 'agent_writer'::"text"));



ALTER TABLE "public"."conversations" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "conversations_agent_select" ON "public"."conversations" FOR SELECT TO "anon" USING (("public"."get_user_role"() = ANY (ARRAY['agent_reader'::"text", 'agent_writer'::"text"])));



CREATE POLICY "conversations_agent_write" ON "public"."conversations" TO "anon" USING (("public"."get_user_role"() = 'agent_writer'::"text")) WITH CHECK (("public"."get_user_role"() = 'agent_writer'::"text"));



CREATE POLICY "lead_outreach_agent_select" ON "public"."leads" FOR SELECT TO "anon" USING (("public"."get_user_role"() = ANY (ARRAY['agent_reader'::"text", 'agent_writer'::"text"])));



CREATE POLICY "lead_outreach_agent_write" ON "public"."leads" TO "anon" USING (("public"."get_user_role"() = 'agent_writer'::"text")) WITH CHECK (("public"."get_user_role"() = 'agent_writer'::"text"));



ALTER TABLE "public"."leads" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."messages" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "messages_agent_select" ON "public"."messages" FOR SELECT TO "anon" USING (("public"."get_user_role"() = ANY (ARRAY['agent_reader'::"text", 'agent_writer'::"text"])));



CREATE POLICY "messages_agent_write" ON "public"."messages" TO "anon" USING (("public"."get_user_role"() = 'agent_writer'::"text")) WITH CHECK (("public"."get_user_role"() = 'agent_writer'::"text"));



ALTER TABLE "public"."sequences" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."staging_leads" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "staging_leads_agent_select" ON "public"."staging_leads" FOR SELECT TO "anon" USING (("public"."get_user_role"() = ANY (ARRAY['agent_reader'::"text", 'agent_writer'::"text"])));



CREATE POLICY "staging_leads_agent_write" ON "public"."staging_leads" TO "anon" USING (("public"."get_user_role"() = 'agent_writer'::"text")) WITH CHECK (("public"."get_user_role"() = 'agent_writer'::"text"));



ALTER TABLE "public"."user_roles" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "user_select_own_roles" ON "public"."user_roles" FOR SELECT TO "authenticated" USING ((( SELECT "auth"."uid"() AS "uid") = "user_id"));





ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "Relational" TO "ai_user";






GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";

























































































































































GRANT ALL ON FUNCTION "public"."custom_access_token"("claims" "jsonb") TO "anon";
GRANT ALL ON FUNCTION "public"."custom_access_token"("claims" "jsonb") TO "authenticated";
GRANT ALL ON FUNCTION "public"."custom_access_token"("claims" "jsonb") TO "service_role";



GRANT ALL ON FUNCTION "public"."get_user_role"() TO "anon";
GRANT ALL ON FUNCTION "public"."get_user_role"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."get_user_role"() TO "service_role";



GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "anon";
GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."update_updated_at_column"() TO "service_role";


















GRANT ALL ON TABLE "public"."agent_subtasks" TO "anon";
GRANT ALL ON TABLE "public"."agent_subtasks" TO "authenticated";
GRANT ALL ON TABLE "public"."agent_subtasks" TO "service_role";



GRANT ALL ON TABLE "public"."agent_tasks" TO "anon";
GRANT ALL ON TABLE "public"."agent_tasks" TO "authenticated";
GRANT ALL ON TABLE "public"."agent_tasks" TO "service_role";



GRANT SELECT,INSERT,UPDATE ON TABLE "public"."campaigns" TO "ai_user";



GRANT SELECT,INSERT,UPDATE ON TABLE "public"."clients" TO "ai_user";
GRANT ALL ON TABLE "public"."clients" TO "authenticated";
GRANT ALL ON TABLE "public"."clients" TO "anon";



GRANT ALL ON TABLE "public"."conversations" TO "anon";
GRANT ALL ON TABLE "public"."conversations" TO "authenticated";
GRANT ALL ON TABLE "public"."conversations" TO "service_role";



GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."leads" TO "ai_user";
GRANT ALL ON TABLE "public"."leads" TO "authenticated";
GRANT ALL ON TABLE "public"."leads" TO "anon";
GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE "public"."leads" TO "service_role";



GRANT ALL ON TABLE "public"."messages" TO "anon";
GRANT ALL ON TABLE "public"."messages" TO "authenticated";
GRANT ALL ON TABLE "public"."messages" TO "service_role";



GRANT SELECT,INSERT,UPDATE ON TABLE "public"."sequences" TO "ai_user";



GRANT ALL ON TABLE "public"."staging_conversations" TO "anon";
GRANT ALL ON TABLE "public"."staging_conversations" TO "authenticated";
GRANT ALL ON TABLE "public"."staging_conversations" TO "service_role";



GRANT ALL ON TABLE "public"."staging_leads" TO "anon";
GRANT ALL ON TABLE "public"."staging_leads" TO "authenticated";
GRANT ALL ON TABLE "public"."staging_leads" TO "service_role";



GRANT ALL ON TABLE "public"."staging_messages" TO "anon";
GRANT ALL ON TABLE "public"."staging_messages" TO "authenticated";
GRANT ALL ON TABLE "public"."staging_messages" TO "service_role";



GRANT ALL ON TABLE "public"."user_roles" TO "anon";
GRANT ALL ON TABLE "public"."user_roles" TO "authenticated";
GRANT ALL ON TABLE "public"."user_roles" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";






























