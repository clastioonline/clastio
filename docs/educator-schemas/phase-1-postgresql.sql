BEGIN;

-- Running upgrade h208feedback01 -> i209educator01

ALTER TABLE teacher_profiles ADD COLUMN regulatory_authority VARCHAR(20) DEFAULT 'not_specified' NOT NULL;

ALTER TABLE teacher_profiles ADD COLUMN education_stages VARCHAR[] DEFAULT '{}' NOT NULL;

ALTER TABLE teacher_profiles ADD COLUMN planning_preferences JSONB DEFAULT '{}' NOT NULL;

ALTER TABLE teacher_profiles ADD CONSTRAINT ck_teacher_profiles_regulatory_authority CHECK (regulatory_authority IN ('khda', 'adek', 'moe', 'other', 'not_specified'));

ALTER TABLE teacher_profiles ADD CONSTRAINT ck_teacher_profiles_education_stages CHECK (education_stages <@ ARRAY['early_years', 'primary', 'secondary', 'university']::varchar[]);

CREATE TABLE lesson_plans (
    id UUID NOT NULL, 
    owner_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    lesson_id UUID, 
    class_section_id UUID, 
    title VARCHAR(300) NOT NULL, 
    topic VARCHAR(300) NOT NULL, 
    subject VARCHAR(80) NOT NULL, 
    grade VARCHAR(30) NOT NULL, 
    curriculum VARCHAR(40) NOT NULL, 
    language VARCHAR(10) DEFAULT 'en' NOT NULL, 
    education_stage VARCHAR(20) DEFAULT 'secondary' NOT NULL, 
    framework VARCHAR(20) DEFAULT 'not_specified' NOT NULL, 
    schema_version INTEGER DEFAULT '1' NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    duration_minutes INTEGER DEFAULT '45' NOT NULL, 
    status VARCHAR(20) DEFAULT 'draft' NOT NULL, 
    learning_objectives JSONB DEFAULT '[]' NOT NULL, 
    success_criteria JSONB DEFAULT '[]' NOT NULL, 
    cross_curricular_links JSONB DEFAULT '[]' NOT NULL, 
    uae_context JSONB DEFAULT '{}' NOT NULL, 
    differentiation JSONB DEFAULT '{}' NOT NULL, 
    formative_assessment JSONB DEFAULT '[]' NOT NULL, 
    lesson_sequence JSONB DEFAULT '[]' NOT NULL, 
    prerequisites JSONB DEFAULT '[]' NOT NULL, 
    homework JSONB DEFAULT '""' NOT NULL, 
    resources JSONB DEFAULT '[]' NOT NULL, 
    source_references JSONB DEFAULT '[]' NOT NULL, 
    review_checks JSONB DEFAULT '{}' NOT NULL, 
    pdf_key VARCHAR(500), 
    error TEXT, 
    reviewed_at TIMESTAMP WITH TIME ZONE, 
    CONSTRAINT pk_lesson_plans PRIMARY KEY (id), 
    CONSTRAINT ck_lesson_plans_framework CHECK (framework IN ('khda', 'adek', 'moe', 'other', 'not_specified')), 
    CONSTRAINT ck_lesson_plans_education_stage CHECK (education_stage IN ('early_years', 'primary', 'secondary', 'university')), 
    CONSTRAINT ck_lesson_plans_status CHECK (status IN ('draft', 'queued', 'generating', 'ready', 'reviewed', 'failed', 'archived')), 
    CONSTRAINT ck_lesson_plans_duration_positive CHECK (duration_minutes > 0), 
    CONSTRAINT ck_lesson_plans_versions_positive CHECK (version > 0 AND schema_version > 0), 
    CONSTRAINT ck_lesson_plans_ready_content CHECK (status NOT IN ('ready', 'reviewed') OR (
    jsonb_typeof(learning_objectives) = 'array' AND learning_objectives <> '[]'::jsonb
    AND jsonb_typeof(success_criteria) = 'array' AND success_criteria <> '[]'::jsonb
    AND jsonb_typeof(cross_curricular_links) = 'array' AND cross_curricular_links <> '[]'::jsonb
    AND jsonb_typeof(formative_assessment) = 'array' AND formative_assessment <> '[]'::jsonb
    AND jsonb_typeof(lesson_sequence) = 'array' AND lesson_sequence <> '[]'::jsonb
    AND jsonb_typeof(uae_context) = 'object'
    AND uae_context ?& ARRAY['national_identity', 'moral_education', 'arabic_culture']
    AND jsonb_typeof(uae_context -> 'national_identity') = 'object'
    AND (uae_context -> 'national_identity') <> '{}'::jsonb
    AND jsonb_typeof(uae_context -> 'moral_education') = 'object'
    AND (uae_context -> 'moral_education') <> '{}'::jsonb
    AND jsonb_typeof(uae_context -> 'arabic_culture') = 'object'
    AND (uae_context -> 'arabic_culture') <> '{}'::jsonb
    AND jsonb_typeof(differentiation) = 'object'
    AND differentiation ?& ARRAY['sen', 'ell']
    AND jsonb_typeof(differentiation -> 'sen') = 'array'
    AND (differentiation -> 'sen') <> '[]'::jsonb
    AND jsonb_typeof(differentiation -> 'ell') = 'array'
    AND (differentiation -> 'ell') <> '[]'::jsonb
)), 
    CONSTRAINT ck_lesson_plans_university_framework CHECK (education_stage <> 'university' OR framework IN ('other', 'not_specified')), 
    CONSTRAINT fk_lesson_plans_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_lesson_plans_lesson_id_lessons FOREIGN KEY(lesson_id) REFERENCES lessons (id) ON DELETE SET NULL, 
    CONSTRAINT fk_lesson_plans_class_section_id_class_sections FOREIGN KEY(class_section_id) REFERENCES class_sections (id) ON DELETE SET NULL
);

CREATE INDEX ix_lesson_plans_owner_id ON lesson_plans (owner_id);

CREATE INDEX ix_lesson_plans_status ON lesson_plans (status);

CREATE INDEX ix_lesson_plans_lesson_id ON lesson_plans (lesson_id);

CREATE INDEX ix_lesson_plans_class_section_id ON lesson_plans (class_section_id);

CREATE INDEX ix_lesson_plans_owner_created ON lesson_plans (owner_id, created_at);

CREATE TABLE demo_classes (
    id UUID NOT NULL, 
    owner_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    lesson_plan_id UUID, 
    lesson_id UUID, 
    title VARCHAR(300) NOT NULL, 
    topic VARCHAR(300) NOT NULL, 
    subject VARCHAR(80) NOT NULL, 
    grade VARCHAR(30) NOT NULL, 
    curriculum VARCHAR(40) NOT NULL, 
    language VARCHAR(10) DEFAULT 'en' NOT NULL, 
    framework VARCHAR(20) DEFAULT 'not_specified' NOT NULL, 
    duration_minutes INTEGER DEFAULT '15' NOT NULL, 
    status VARCHAR(20) DEFAULT 'draft' NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    hook JSONB DEFAULT '{}' NOT NULL, 
    teacher_script JSONB DEFAULT '[]' NOT NULL, 
    slide_payload JSONB DEFAULT '{}' NOT NULL, 
    source_references JSONB DEFAULT '[]' NOT NULL, 
    review_checks JSONB DEFAULT '{}' NOT NULL, 
    pptx_key VARCHAR(500), 
    pdf_key VARCHAR(500), 
    error TEXT, 
    CONSTRAINT pk_demo_classes PRIMARY KEY (id), 
    CONSTRAINT ck_demo_classes_framework CHECK (framework IN ('khda', 'adek', 'moe', 'other', 'not_specified')), 
    CONSTRAINT ck_demo_classes_status CHECK (status IN ('draft', 'queued', 'generating', 'ready', 'reviewed', 'failed', 'archived')), 
    CONSTRAINT ck_demo_classes_fifteen_minutes CHECK (duration_minutes = 15), 
    CONSTRAINT ck_demo_classes_version_positive CHECK (version > 0), 
    CONSTRAINT ck_demo_classes_ready_content CHECK (status NOT IN ('ready', 'reviewed') OR (
    jsonb_typeof(teacher_script) = 'array' AND teacher_script <> '[]'::jsonb
    AND jsonb_typeof(hook) = 'object' AND hook <> '{}'::jsonb
    AND jsonb_typeof(slide_payload) = 'object'
    AND slide_payload ? 'slides'
    AND jsonb_typeof(slide_payload -> 'slides') = 'array'
    AND (slide_payload -> 'slides') <> '[]'::jsonb
)), 
    CONSTRAINT fk_demo_classes_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_demo_classes_lesson_plan_id_lesson_plans FOREIGN KEY(lesson_plan_id) REFERENCES lesson_plans (id) ON DELETE SET NULL, 
    CONSTRAINT fk_demo_classes_lesson_id_lessons FOREIGN KEY(lesson_id) REFERENCES lessons (id) ON DELETE SET NULL
);

CREATE INDEX ix_demo_classes_owner_id ON demo_classes (owner_id);

CREATE INDEX ix_demo_classes_status ON demo_classes (status);

CREATE INDEX ix_demo_classes_lesson_plan_id ON demo_classes (lesson_plan_id);

CREATE INDEX ix_demo_classes_lesson_id ON demo_classes (lesson_id);

CREATE INDEX ix_demo_classes_owner_created ON demo_classes (owner_id, created_at);

CREATE TABLE digital_resources (
    id UUID NOT NULL, 
    owner_id UUID NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    uploaded_file_id UUID, 
    document_id UUID, 
    title VARCHAR(300) NOT NULL, 
    topic VARCHAR(300) NOT NULL, 
    subject VARCHAR(80) NOT NULL, 
    education_stage VARCHAR(20) NOT NULL, 
    grade VARCHAR(30), 
    curriculum VARCHAR(40) NOT NULL, 
    language VARCHAR(10) DEFAULT 'en' NOT NULL, 
    kind VARCHAR(30) NOT NULL, 
    origin VARCHAR(20) NOT NULL, 
    status VARCHAR(20) DEFAULT 'draft' NOT NULL, 
    version INTEGER DEFAULT '1' NOT NULL, 
    schema_version INTEGER DEFAULT '1' NOT NULL, 
    cache_key VARCHAR(64) NOT NULL, 
    content JSONB DEFAULT '{}' NOT NULL, 
    chapters JSONB DEFAULT '[]' NOT NULL, 
    source_references JSONB DEFAULT '[]' NOT NULL, 
    license_metadata JSONB DEFAULT '{}' NOT NULL, 
    pdf_key VARCHAR(500), 
    error TEXT, 
    CONSTRAINT pk_digital_resources PRIMARY KEY (id), 
    CONSTRAINT uq_digital_resources_owner_cache UNIQUE (owner_id, cache_key), 
    CONSTRAINT ck_digital_resources_education_stage CHECK (education_stage IN ('early_years', 'primary', 'secondary', 'university')), 
    CONSTRAINT ck_digital_resources_status CHECK (status IN ('draft', 'queued', 'generating', 'ready', 'reviewed', 'failed', 'archived')), 
    CONSTRAINT ck_digital_resources_versions_positive CHECK (version > 0 AND schema_version > 0), 
    CONSTRAINT ck_digital_resources_origin CHECK (origin IN ('uploaded', 'official', 'generated')), 
    CONSTRAINT ck_digital_resources_kind CHECK (kind IN ('book', 'guide', 'subject_primer', 'study_guide')), 
    CONSTRAINT ck_digital_resources_generated_kind CHECK (origin <> 'generated' OR kind IN ('subject_primer', 'study_guide')), 
    CONSTRAINT ck_digital_resources_ready_generated_content CHECK (origin <> 'generated' OR status NOT IN ('ready', 'reviewed') OR (
    jsonb_typeof(content) = 'object' AND content <> '{}'::jsonb
    AND jsonb_typeof(chapters) = 'array' AND chapters <> '[]'::jsonb
)), 
    CONSTRAINT fk_digital_resources_owner_id_users FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT fk_digital_resources_uploaded_file_id_uploaded_files FOREIGN KEY(uploaded_file_id) REFERENCES uploaded_files (id) ON DELETE SET NULL, 
    CONSTRAINT fk_digital_resources_document_id_documents FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE SET NULL
);

CREATE INDEX ix_digital_resources_owner_id ON digital_resources (owner_id);

CREATE INDEX ix_digital_resources_status ON digital_resources (status);

CREATE INDEX ix_digital_resources_uploaded_file_id ON digital_resources (uploaded_file_id);

CREATE INDEX ix_digital_resources_document_id ON digital_resources (document_id);

CREATE INDEX ix_digital_resources_owner_created ON digital_resources (owner_id, created_at);

CREATE INDEX ix_digital_resources_lookup ON digital_resources (owner_id, subject, education_stage, curriculum, language);

UPDATE alembic_version SET version_num='i209educator01' WHERE alembic_version.version_num = 'h208feedback01';

COMMIT;

