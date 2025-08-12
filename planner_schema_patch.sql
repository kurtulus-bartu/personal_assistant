-- === Planner Schema Patch (idempotent) ===
-- Tasks: notes, has_time, due_date
-- Events: title, notes, rrule

-- 1) TASKS kolonları
ALTER TABLE IF EXISTS public.tasks
  ADD COLUMN IF NOT EXISTS notes    text NOT NULL DEFAULT '';

ALTER TABLE IF EXISTS public.tasks
  ADD COLUMN IF NOT EXISTS has_time boolean NOT NULL DEFAULT false;

ALTER TABLE IF EXISTS public.tasks
  ADD COLUMN IF NOT EXISTS due_date date NULL;

-- 2) EVENTS kolonları
ALTER TABLE IF EXISTS public.events
  ADD COLUMN IF NOT EXISTS title text NULL;

ALTER TABLE IF EXISTS public.events
  ADD COLUMN IF NOT EXISTS notes text NOT NULL DEFAULT '';

ALTER TABLE IF EXISTS public.events
  ADD COLUMN IF NOT EXISTS rrule text NULL;

-- 3) Faydalı indeksler
CREATE INDEX IF NOT EXISTS idx_events_starts_at ON public.events (starts_at);
CREATE INDEX IF NOT EXISTS idx_events_task_id  ON public.events (task_id);

-- 4) Sadece zaman atanmamış görevler için opsiyonel view/index
CREATE INDEX IF NOT EXISTS idx_tasks_unscheduled ON public.tasks (id)
WHERE COALESCE(has_time, false) = false;

CREATE OR REPLACE VIEW public.tasks_unscheduled AS
SELECT *
FROM public.tasks
WHERE COALESCE(has_time, false) = false;

-- NOT: updated_at trigger'ların zaten tanımlı.
-- RLS kullanıyorsan, select/insert/update/delete policy'lerini ayrıca eklemeyi unutma.
