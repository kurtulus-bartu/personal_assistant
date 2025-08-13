-- === Planner Schema Patch (idempotent) ===
-- Tasks: notes, has_time, due_date, start_ts, end_ts, parent_id

-- 1) TASKS kolonları
ALTER TABLE IF EXISTS public.tasks
  ADD COLUMN IF NOT EXISTS notes    text NOT NULL DEFAULT '';

ALTER TABLE IF EXISTS public.tasks
  ADD COLUMN IF NOT EXISTS has_time boolean NOT NULL DEFAULT false;

ALTER TABLE IF EXISTS public.tasks
  ADD COLUMN IF NOT EXISTS due_date date NULL;

ALTER TABLE IF EXISTS public.tasks
  ADD COLUMN IF NOT EXISTS start_ts timestamptz NULL;

ALTER TABLE IF EXISTS public.tasks
  ADD COLUMN IF NOT EXISTS end_ts   timestamptz NULL;

ALTER TABLE IF EXISTS public.tasks
  ADD COLUMN IF NOT EXISTS parent_id bigint NULL REFERENCES public.tasks(id);

-- 2) Faydalı indeksler
CREATE INDEX IF NOT EXISTS idx_tasks_starts_at ON public.tasks (start_ts);

CREATE INDEX IF NOT EXISTS idx_tasks_parent_id ON public.tasks (parent_id);

-- 3) Sadece zaman atanmamış görevler için opsiyonel view/index
CREATE INDEX IF NOT EXISTS idx_tasks_unscheduled ON public.tasks (id)
WHERE COALESCE(has_time, false) = false;

CREATE OR REPLACE VIEW public.tasks_unscheduled AS
SELECT *
FROM public.tasks
WHERE COALESCE(has_time, false) = false;

-- NOT: updated_at trigger'ların zaten tanımlı.
-- RLS kullanıyorsan, select/insert/update/delete policy'lerini ayrıca eklemeyi unutma.
