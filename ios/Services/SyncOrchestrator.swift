import Foundation

@MainActor
public enum SyncOrchestrator {
    /// Uygulama açılışında tek yönlü çekiş:
    /// Supabase -> Lokal (tags -> projects -> tasks -> events)
    public static func initialPull(
        tags: TagStore,
        projects: ProjectStore,
        tasks: TaskStore,
        events: EventStore
    ) async {
        // Lokal dosyalar zaten load() ile geldi.
        // Şimdi “uzaktaki gerçeği” çekip lokal JSON’a yazalım (sırayla).
        await tags.syncFromSupabase()
        await projects.syncFromSupabase()
        await tasks.syncFromSupabase()
        await events.syncFromSupabase()
    }

    /// Yenile (replace): Lokal -> Supabase (tam yer değiştir)
    /// Sıra: önce uzaktaki tasks (event+task) silinsin, sonra projeler ve tagler
    /// de silinsin, ardından tag -> project -> task -> event upsert.
    public static func replaceRemoteWithLocal(
        tags: TagStore,
        projects: ProjectStore,
        tasks: TaskStore,
        events: EventStore
    ) async {
        // 1) Uzaktaki tasks tablosunu tamamen boşalt
        try? await SupabaseService.shared.deleteAllEvents()
        try? await SupabaseService.shared.deleteAllTasks()

        // 2) Uzaktaki projects/tags’ı boşalt
        try? await SupabaseService.shared.deleteAllProjects()
        try? await SupabaseService.shared.deleteAllTags()

        // 3) Lokalden sırayla yaz (FK bütünlüğü için önce tag, sonra project, sonra task/event)
        try? await SupabaseService.shared.upsertTags(tags.tags)
        try? await SupabaseService.shared.upsertProjects(projects.projects)
        try? await SupabaseService.shared.upsertTasks(tasks.tasks)
        try? await SupabaseService.shared.upsertEvents(events.events)
    }
}
