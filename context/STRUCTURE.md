# Database Structure
```sql
--
-- PostgreSQL database dump
--

\restrict LZOd91KbYf6lc784IQZ8Hpi4F8yFCYFhqFkgih5UDx0OLOM4V3jKmo1kItDHU1q

-- Dumped from database version 17.6
-- Dumped by pg_dump version 17.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: device_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.device_type_enum AS ENUM (
    'blood_pressure',
    'pulse_oximeter',
    'scale',
    'thermometer'
);


--
-- Name: measurement_source_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.measurement_source_enum AS ENUM (
    'device',
    'voice',
    'manual'
);


--
-- Name: measurement_type_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.measurement_type_enum AS ENUM (
    'bp',
    'spo2',
    'weight',
    'temperature'
);


--
-- Name: resident_status_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.resident_status_enum AS ENUM (
    'active',
    'discharged',
    'deceased'
);


--
-- Name: user_role_enum; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.user_role_enum AS ENUM (
    'superadmin',
    'manager',
    'professional'
);


--
-- Name: trg_resident_bed_guard(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_resident_bed_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE bed_res uuid;
BEGIN
  -- si cambia a discharged/deceased, autollenar status_changed_at + deleted_at y quitar cama
  IF (NEW.status IN ('discharged','deceased')) THEN
    IF NEW.status_changed_at IS NULL THEN NEW.status_changed_at := now(); END IF;
    IF NEW.deleted_at IS NULL THEN NEW.deleted_at := now(); END IF;
    NEW.bed_id := NULL;
  END IF;

  -- si hay cama, debe ser de la misma residencia
  IF NEW.bed_id IS NOT NULL THEN
    SELECT residence_id INTO bed_res FROM bed WHERE id = NEW.bed_id;
    IF bed_res IS NULL THEN
      RAISE EXCEPTION 'Bed % does not exist', NEW.bed_id;
    END IF;
    IF bed_res <> NEW.residence_id THEN
      RAISE EXCEPTION 'Bed % belongs to another residence', NEW.bed_id;
    END IF;
  END IF;

  -- log de cambio de cama
  IF TG_OP = 'UPDATE' AND OLD.bed_id IS DISTINCT FROM NEW.bed_id THEN
    INSERT INTO event_log(actor_user_id, residence_id, entity, entity_id, action, meta)
    VALUES (current_setting('app.user_id', true)::uuid, NEW.residence_id, 'resident', NEW.id, 'assign_bed',
            jsonb_build_object('from', OLD.bed_id, 'to', NEW.bed_id));
  END IF;

  RETURN NEW;
END$$;


--
-- Name: trg_set_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END$$;


--
-- Name: trg_task_app_fill_status(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_task_app_fill_status() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE txt text;
BEGIN
  IF NEW.selected_status_index IS NULL THEN
    NEW.selected_status_text := NULL;
  ELSE
    SELECT
      CASE NEW.selected_status_index
        WHEN 1 THEN t.status1
        WHEN 2 THEN t.status2
        WHEN 3 THEN t.status3
        WHEN 4 THEN t.status4
        WHEN 5 THEN t.status5
        WHEN 6 THEN t.status6
      END
    INTO txt
    FROM task_template t
    WHERE t.id = NEW.task_template_id;

    NEW.selected_status_text := txt;
  END IF;
  RETURN NEW;
END$$;


--
-- Name: trg_write_history_and_event(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_write_history_and_event() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE rec jsonb; act text; idv uuid; resid uuid;
BEGIN
  IF TG_OP = 'INSERT' THEN
    rec := to_jsonb(NEW); act := 'create'; idv := NEW.id; resid := COALESCE(NEW.residence_id, NULL);
  ELSIF TG_OP = 'UPDATE' THEN
    rec := jsonb_build_object('old', to_jsonb(OLD), 'new', to_jsonb(NEW));
    act := 'update'; idv := NEW.id; resid := COALESCE(NEW.residence_id, NULL);
  ELSE
    rec := to_jsonb(OLD); act := 'delete'; idv := OLD.id; resid := COALESCE(OLD.residence_id, NULL);
  END IF;

  IF TG_TABLE_NAME = 'resident' THEN
    INSERT INTO resident_history(entity_id, record, changed_by, change_type)
    VALUES (idv, rec, current_setting('app.user_id', true)::uuid, lower(TG_OP));
  ELSIF TG_TABLE_NAME = 'device' THEN
    INSERT INTO device_history(entity_id, record, changed_by, change_type)
    VALUES (idv, rec, current_setting('app.user_id', true)::uuid, lower(TG_OP));
  ELSIF TG_TABLE_NAME = 'task_application' THEN
    INSERT INTO task_application_history(entity_id, record, changed_by, change_type)
    VALUES (idv, rec, current_setting('app.user_id', true)::uuid, lower(TG_OP));
  ELSIF TG_TABLE_NAME = 'measurement' THEN
    INSERT INTO measurement_history(entity_id, record, changed_by, change_type)
    VALUES (idv, rec, current_setting('app.user_id', true)::uuid, lower(TG_OP));
  END IF;

  INSERT INTO event_log(actor_user_id, residence_id, entity, entity_id, action, meta)
  VALUES (current_setting('app.user_id', true)::uuid, resid, TG_TABLE_NAME, idv, act, rec);

  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: bed; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bed (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    residence_id uuid NOT NULL,
    room_id uuid NOT NULL,
    name text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: device; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    residence_id uuid NOT NULL,
    type public.device_type_enum NOT NULL,
    name text NOT NULL,
    mac text NOT NULL,
    battery_percent smallint,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT device_battery_percent_check CHECK (((battery_percent >= 0) AND (battery_percent <= 100)))
);


--
-- Name: device_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.device_history (
    history_id bigint NOT NULL,
    entity_id uuid NOT NULL,
    record jsonb NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by uuid,
    change_type text NOT NULL
);


--
-- Name: device_history_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.device_history_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: device_history_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.device_history_history_id_seq OWNED BY public.device_history.history_id;


--
-- Name: event_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event_log (
    id bigint NOT NULL,
    actor_user_id uuid,
    residence_id uuid,
    entity text NOT NULL,
    entity_id uuid,
    action text NOT NULL,
    at timestamp with time zone DEFAULT now() NOT NULL,
    meta jsonb
);


--
-- Name: event_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.event_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: event_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.event_log_id_seq OWNED BY public.event_log.id;


--
-- Name: floor; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.floor (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    residence_id uuid NOT NULL,
    name text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: measurement; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.measurement (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    residence_id uuid NOT NULL,
    resident_id uuid NOT NULL,
    recorded_by uuid NOT NULL,
    source public.measurement_source_enum NOT NULL,
    device_id uuid,
    type public.measurement_type_enum NOT NULL,
    systolic integer,
    diastolic integer,
    pulse_bpm integer,
    spo2 integer,
    weight_kg numeric(5,1),
    temperature_c integer,
    taken_at timestamp with time zone NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT ck_measurement_by_type CHECK ((((type = 'bp'::public.measurement_type_enum) AND (systolic IS NOT NULL) AND (diastolic IS NOT NULL) AND (pulse_bpm IS NOT NULL) AND (spo2 IS NULL) AND (weight_kg IS NULL) AND (temperature_c IS NULL)) OR ((type = 'spo2'::public.measurement_type_enum) AND (spo2 IS NOT NULL) AND (pulse_bpm IS NOT NULL) AND (systolic IS NULL) AND (diastolic IS NULL) AND (weight_kg IS NULL) AND (temperature_c IS NULL)) OR ((type = 'weight'::public.measurement_type_enum) AND (weight_kg IS NOT NULL) AND (systolic IS NULL) AND (diastolic IS NULL) AND (pulse_bpm IS NULL) AND (spo2 IS NULL) AND (temperature_c IS NULL)) OR ((type = 'temperature'::public.measurement_type_enum) AND (temperature_c IS NOT NULL) AND (systolic IS NULL) AND (diastolic IS NULL) AND (pulse_bpm IS NULL) AND (spo2 IS NULL) AND (weight_kg IS NULL))))
);


--
-- Name: measurement_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.measurement_history (
    history_id bigint NOT NULL,
    entity_id uuid NOT NULL,
    record jsonb NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by uuid,
    change_type text NOT NULL
);


--
-- Name: measurement_history_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.measurement_history_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: measurement_history_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.measurement_history_history_id_seq OWNED BY public.measurement_history.history_id;


--
-- Name: residence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.residence (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    address text,
    phone_encrypted bytea,
    email_encrypted bytea,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: resident; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resident (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    residence_id uuid NOT NULL,
    full_name text NOT NULL,
    birth_date date NOT NULL,
    sex text,
    gender text,
    comments text,
    status public.resident_status_enum DEFAULT 'active'::public.resident_status_enum NOT NULL,
    status_changed_at timestamp with time zone,
    deleted_at timestamp with time zone,
    bed_id uuid,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT ck_resident_bed_when_active CHECK (((status = 'active'::public.resident_status_enum) OR (bed_id IS NULL)))
);


--
-- Name: resident_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resident_history (
    history_id bigint NOT NULL,
    entity_id uuid NOT NULL,
    record jsonb NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by uuid,
    change_type text NOT NULL
);


--
-- Name: resident_history_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.resident_history_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: resident_history_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.resident_history_history_id_seq OWNED BY public.resident_history.history_id;


--
-- Name: resident_tag; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.resident_tag (
    resident_id uuid NOT NULL,
    tag_id uuid NOT NULL,
    assigned_by uuid NOT NULL,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: room; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.room (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    residence_id uuid NOT NULL,
    floor_id uuid NOT NULL,
    name text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: tag; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tag (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: task_application; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_application (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    residence_id uuid NOT NULL,
    resident_id uuid NOT NULL,
    task_template_id uuid NOT NULL,
    applied_by uuid NOT NULL,
    applied_at timestamp with time zone DEFAULT now() NOT NULL,
    selected_status_index smallint,
    selected_status_text text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone,
    CONSTRAINT task_application_selected_status_index_check CHECK (((selected_status_index >= 1) AND (selected_status_index <= 6)))
);


--
-- Name: task_application_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_application_history (
    history_id bigint NOT NULL,
    entity_id uuid NOT NULL,
    record jsonb NOT NULL,
    changed_at timestamp with time zone DEFAULT now() NOT NULL,
    changed_by uuid,
    change_type text NOT NULL
);


--
-- Name: task_application_history_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.task_application_history_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: task_application_history_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.task_application_history_history_id_seq OWNED BY public.task_application_history.history_id;


--
-- Name: task_category; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_category (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    residence_id uuid NOT NULL,
    name text NOT NULL,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: task_template; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.task_template (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    residence_id uuid NOT NULL,
    task_category_id uuid NOT NULL,
    name text NOT NULL,
    status1 text,
    status2 text,
    status3 text,
    status4 text,
    status5 text,
    status6 text,
    audio_phrase text,
    is_block boolean,
    created_by uuid,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public."user" (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    role public.user_role_enum NOT NULL,
    alias_encrypted bytea NOT NULL,
    alias_hash text NOT NULL,
    password_hash text NOT NULL,
    email_encrypted bytea,
    phone_encrypted bytea,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    deleted_at timestamp with time zone
);


--
-- Name: user_residence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_residence (
    user_id uuid NOT NULL,
    residence_id uuid NOT NULL
);


--
-- Name: device_history history_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_history ALTER COLUMN history_id SET DEFAULT nextval('public.device_history_history_id_seq'::regclass);


--
-- Name: event_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_log ALTER COLUMN id SET DEFAULT nextval('public.event_log_id_seq'::regclass);


--
-- Name: measurement_history history_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.measurement_history ALTER COLUMN history_id SET DEFAULT nextval('public.measurement_history_history_id_seq'::regclass);


--
-- Name: resident_history history_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resident_history ALTER COLUMN history_id SET DEFAULT nextval('public.resident_history_history_id_seq'::regclass);


--
-- Name: task_application_history history_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_application_history ALTER COLUMN history_id SET DEFAULT nextval('public.task_application_history_history_id_seq'::regclass);


--
-- Name: bed bed_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bed
    ADD CONSTRAINT bed_pkey PRIMARY KEY (id);


--
-- Name: bed bed_room_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bed
    ADD CONSTRAINT bed_room_id_name_key UNIQUE (room_id, name);


--
-- Name: device_history device_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_history
    ADD CONSTRAINT device_history_pkey PRIMARY KEY (history_id);


--
-- Name: device device_mac_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device
    ADD CONSTRAINT device_mac_key UNIQUE (mac);


--
-- Name: device device_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device
    ADD CONSTRAINT device_pkey PRIMARY KEY (id);


--
-- Name: event_log event_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_log
    ADD CONSTRAINT event_log_pkey PRIMARY KEY (id);


--
-- Name: floor floor_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.floor
    ADD CONSTRAINT floor_pkey PRIMARY KEY (id);


--
-- Name: floor floor_residence_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.floor
    ADD CONSTRAINT floor_residence_id_name_key UNIQUE (residence_id, name);


--
-- Name: measurement_history measurement_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.measurement_history
    ADD CONSTRAINT measurement_history_pkey PRIMARY KEY (history_id);


--
-- Name: measurement measurement_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.measurement
    ADD CONSTRAINT measurement_pkey PRIMARY KEY (id);


--
-- Name: residence residence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.residence
    ADD CONSTRAINT residence_pkey PRIMARY KEY (id);


--
-- Name: resident_history resident_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resident_history
    ADD CONSTRAINT resident_history_pkey PRIMARY KEY (history_id);


--
-- Name: resident resident_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resident
    ADD CONSTRAINT resident_pkey PRIMARY KEY (id);


--
-- Name: resident_tag resident_tag_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resident_tag
    ADD CONSTRAINT resident_tag_pkey PRIMARY KEY (resident_id, tag_id);


--
-- Name: room room_floor_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room
    ADD CONSTRAINT room_floor_id_name_key UNIQUE (floor_id, name);


--
-- Name: room room_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room
    ADD CONSTRAINT room_pkey PRIMARY KEY (id);


--
-- Name: tag tag_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tag
    ADD CONSTRAINT tag_name_key UNIQUE (name);


--
-- Name: tag tag_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tag
    ADD CONSTRAINT tag_pkey PRIMARY KEY (id);


--
-- Name: task_application_history task_application_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_application_history
    ADD CONSTRAINT task_application_history_pkey PRIMARY KEY (history_id);


--
-- Name: task_application task_application_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_application
    ADD CONSTRAINT task_application_pkey PRIMARY KEY (id);


--
-- Name: task_category task_category_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_category
    ADD CONSTRAINT task_category_pkey PRIMARY KEY (id);


--
-- Name: task_category task_category_residence_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_category
    ADD CONSTRAINT task_category_residence_id_name_key UNIQUE (residence_id, name);


--
-- Name: task_template task_template_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_template
    ADD CONSTRAINT task_template_pkey PRIMARY KEY (id);


--
-- Name: task_template task_template_task_category_id_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_template
    ADD CONSTRAINT task_template_task_category_id_name_key UNIQUE (task_category_id, name);


--
-- Name: user user_alias_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_alias_hash_key UNIQUE (alias_hash);


--
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- Name: user_residence user_residence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_residence
    ADD CONSTRAINT user_residence_pkey PRIMARY KEY (user_id, residence_id);


--
-- Name: ix_device_residence; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_device_residence ON public.device USING btree (residence_id);


--
-- Name: ix_event_log_res_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_event_log_res_time ON public.event_log USING btree (residence_id, at DESC);


--
-- Name: ix_measurement_res_type_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_measurement_res_type_time ON public.measurement USING btree (residence_id, type, taken_at);


--
-- Name: ix_measurement_resident_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_measurement_resident_time ON public.measurement USING btree (resident_id, taken_at DESC);


--
-- Name: ix_task_app_resident_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_task_app_resident_time ON public.task_application USING btree (resident_id, applied_at DESC);


--
-- Name: ux_active_resident_bed; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_active_resident_bed ON public.resident USING btree (bed_id) WHERE ((bed_id IS NOT NULL) AND (status = 'active'::public.resident_status_enum) AND (deleted_at IS NULL));


--
-- Name: ux_residence_name; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_residence_name ON public.residence USING btree (name);


--
-- Name: bed tg_bed_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_bed_upd BEFORE UPDATE ON public.bed FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: device tg_device_hist_evt; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_device_hist_evt AFTER INSERT OR DELETE OR UPDATE ON public.device FOR EACH ROW EXECUTE FUNCTION public.trg_write_history_and_event();


--
-- Name: device tg_device_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_device_upd BEFORE UPDATE ON public.device FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: floor tg_floor_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_floor_upd BEFORE UPDATE ON public.floor FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: measurement tg_measurement_hist_evt; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_measurement_hist_evt AFTER INSERT OR DELETE OR UPDATE ON public.measurement FOR EACH ROW EXECUTE FUNCTION public.trg_write_history_and_event();


--
-- Name: measurement tg_measurement_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_measurement_upd BEFORE UPDATE ON public.measurement FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: residence tg_residence_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_residence_upd BEFORE UPDATE ON public.residence FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: resident tg_resident_bed_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_resident_bed_guard BEFORE INSERT OR UPDATE ON public.resident FOR EACH ROW EXECUTE FUNCTION public.trg_resident_bed_guard();


--
-- Name: resident tg_resident_hist_evt; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_resident_hist_evt AFTER INSERT OR DELETE OR UPDATE ON public.resident FOR EACH ROW EXECUTE FUNCTION public.trg_write_history_and_event();


--
-- Name: resident_tag tg_resident_tag_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_resident_tag_upd BEFORE UPDATE ON public.resident_tag FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: resident tg_resident_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_resident_upd BEFORE UPDATE ON public.resident FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: room tg_room_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_room_upd BEFORE UPDATE ON public.room FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: tag tg_tag_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_tag_upd BEFORE UPDATE ON public.tag FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: task_application tg_task_app_fill_status; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_task_app_fill_status BEFORE INSERT OR UPDATE ON public.task_application FOR EACH ROW EXECUTE FUNCTION public.trg_task_app_fill_status();


--
-- Name: task_application tg_task_application_hist_evt; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_task_application_hist_evt AFTER INSERT OR DELETE OR UPDATE ON public.task_application FOR EACH ROW EXECUTE FUNCTION public.trg_write_history_and_event();


--
-- Name: task_application tg_task_application_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_task_application_upd BEFORE UPDATE ON public.task_application FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: task_category tg_task_category_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_task_category_upd BEFORE UPDATE ON public.task_category FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: task_template tg_task_template_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_task_template_upd BEFORE UPDATE ON public.task_template FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: user tg_user_upd; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER tg_user_upd BEFORE UPDATE ON public."user" FOR EACH ROW EXECUTE FUNCTION public.trg_set_updated_at();


--
-- Name: bed bed_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bed
    ADD CONSTRAINT bed_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: bed bed_residence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bed
    ADD CONSTRAINT bed_residence_id_fkey FOREIGN KEY (residence_id) REFERENCES public.residence(id) ON DELETE RESTRICT;


--
-- Name: bed bed_room_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bed
    ADD CONSTRAINT bed_room_id_fkey FOREIGN KEY (room_id) REFERENCES public.room(id) ON DELETE RESTRICT;


--
-- Name: device device_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device
    ADD CONSTRAINT device_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: device_history device_history_changed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device_history
    ADD CONSTRAINT device_history_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES public."user"(id);


--
-- Name: device device_residence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.device
    ADD CONSTRAINT device_residence_id_fkey FOREIGN KEY (residence_id) REFERENCES public.residence(id) ON DELETE RESTRICT;


--
-- Name: event_log event_log_actor_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_log
    ADD CONSTRAINT event_log_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES public."user"(id);


--
-- Name: event_log event_log_residence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event_log
    ADD CONSTRAINT event_log_residence_id_fkey FOREIGN KEY (residence_id) REFERENCES public.residence(id);


--
-- Name: floor floor_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.floor
    ADD CONSTRAINT floor_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: floor floor_residence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.floor
    ADD CONSTRAINT floor_residence_id_fkey FOREIGN KEY (residence_id) REFERENCES public.residence(id) ON DELETE RESTRICT;


--
-- Name: measurement measurement_device_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.measurement
    ADD CONSTRAINT measurement_device_id_fkey FOREIGN KEY (device_id) REFERENCES public.device(id);


--
-- Name: measurement_history measurement_history_changed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.measurement_history
    ADD CONSTRAINT measurement_history_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES public."user"(id);


--
-- Name: measurement measurement_recorded_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.measurement
    ADD CONSTRAINT measurement_recorded_by_fkey FOREIGN KEY (recorded_by) REFERENCES public."user"(id);


--
-- Name: measurement measurement_residence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.measurement
    ADD CONSTRAINT measurement_residence_id_fkey FOREIGN KEY (residence_id) REFERENCES public.residence(id) ON DELETE RESTRICT;


--
-- Name: measurement measurement_resident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.measurement
    ADD CONSTRAINT measurement_resident_id_fkey FOREIGN KEY (resident_id) REFERENCES public.resident(id) ON DELETE RESTRICT;


--
-- Name: residence residence_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.residence
    ADD CONSTRAINT residence_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: resident resident_bed_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resident
    ADD CONSTRAINT resident_bed_id_fkey FOREIGN KEY (bed_id) REFERENCES public.bed(id) ON DELETE SET NULL;


--
-- Name: resident resident_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resident
    ADD CONSTRAINT resident_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: resident_history resident_history_changed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resident_history
    ADD CONSTRAINT resident_history_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES public."user"(id);


--
-- Name: resident resident_residence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resident
    ADD CONSTRAINT resident_residence_id_fkey FOREIGN KEY (residence_id) REFERENCES public.residence(id) ON DELETE RESTRICT;


--
-- Name: resident_tag resident_tag_assigned_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resident_tag
    ADD CONSTRAINT resident_tag_assigned_by_fkey FOREIGN KEY (assigned_by) REFERENCES public."user"(id);


--
-- Name: resident_tag resident_tag_resident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resident_tag
    ADD CONSTRAINT resident_tag_resident_id_fkey FOREIGN KEY (resident_id) REFERENCES public.resident(id) ON DELETE CASCADE;


--
-- Name: resident_tag resident_tag_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.resident_tag
    ADD CONSTRAINT resident_tag_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tag(id) ON DELETE RESTRICT;


--
-- Name: room room_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room
    ADD CONSTRAINT room_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: room room_floor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room
    ADD CONSTRAINT room_floor_id_fkey FOREIGN KEY (floor_id) REFERENCES public.floor(id) ON DELETE RESTRICT;


--
-- Name: room room_residence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.room
    ADD CONSTRAINT room_residence_id_fkey FOREIGN KEY (residence_id) REFERENCES public.residence(id) ON DELETE RESTRICT;


--
-- Name: tag tag_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tag
    ADD CONSTRAINT tag_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: task_application task_application_applied_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_application
    ADD CONSTRAINT task_application_applied_by_fkey FOREIGN KEY (applied_by) REFERENCES public."user"(id);


--
-- Name: task_application_history task_application_history_changed_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_application_history
    ADD CONSTRAINT task_application_history_changed_by_fkey FOREIGN KEY (changed_by) REFERENCES public."user"(id);


--
-- Name: task_application task_application_residence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_application
    ADD CONSTRAINT task_application_residence_id_fkey FOREIGN KEY (residence_id) REFERENCES public.residence(id) ON DELETE RESTRICT;


--
-- Name: task_application task_application_resident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_application
    ADD CONSTRAINT task_application_resident_id_fkey FOREIGN KEY (resident_id) REFERENCES public.resident(id) ON DELETE RESTRICT;


--
-- Name: task_application task_application_task_template_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_application
    ADD CONSTRAINT task_application_task_template_id_fkey FOREIGN KEY (task_template_id) REFERENCES public.task_template(id) ON DELETE RESTRICT;


--
-- Name: task_category task_category_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_category
    ADD CONSTRAINT task_category_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: task_category task_category_residence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_category
    ADD CONSTRAINT task_category_residence_id_fkey FOREIGN KEY (residence_id) REFERENCES public.residence(id) ON DELETE RESTRICT;


--
-- Name: task_template task_template_created_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_template
    ADD CONSTRAINT task_template_created_by_fkey FOREIGN KEY (created_by) REFERENCES public."user"(id);


--
-- Name: task_template task_template_residence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_template
    ADD CONSTRAINT task_template_residence_id_fkey FOREIGN KEY (residence_id) REFERENCES public.residence(id) ON DELETE RESTRICT;


--
-- Name: task_template task_template_task_category_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.task_template
    ADD CONSTRAINT task_template_task_category_id_fkey FOREIGN KEY (task_category_id) REFERENCES public.task_category(id) ON DELETE RESTRICT;


--
-- Name: user_residence user_residence_residence_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_residence
    ADD CONSTRAINT user_residence_residence_id_fkey FOREIGN KEY (residence_id) REFERENCES public.residence(id) ON DELETE CASCADE;


--
-- Name: user_residence user_residence_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_residence
    ADD CONSTRAINT user_residence_user_id_fkey FOREIGN KEY (user_id) REFERENCES public."user"(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict LZOd91KbYf6lc784IQZ8Hpi4F8yFCYFhqFkgih5UDx0OLOM4V3jKmo1kItDHU1q

```

# Roles y permisos

- **Superadmin**: puede hacer todo, crear residencias, gestores, profesionales, dispositivos, etc.
- **Gestor**: asignado a n residencias, puede crear otros gestores dentro de esas residencias, crear categorías/tareas, dar de alta residentes, asignar camas.
- **Profesional**: asignado a una o varias residencias, puede tomar mediciones y aplicar tareas. Solo puede borrar/editar sus propias mediciones/tareas.
- **Residente**: tiene estado (`active | discharged | deceased`), solo puede ocupar una cama activa, con histórico de cambios.

# Políticas importantes
- Login con `alias` + `password` (alias cifrado + hash).
- Selección de residencia obligatoria para gestor/profesional si tienen varias.
- Dispositivos: vinculados a residencia, MAC única global. 
- Tags: solo los crean/gestionan gestores o superadmin, globales en el sistema.
