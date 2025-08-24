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
        SyncStatusManager.shared.startRefresh()
        
        do {
            // Sırayla çek (FK bağımlılıkları nedeniyle)
            await tags.syncFromSupabase()
            await projects.syncFromSupabase()
            await tasks.syncFromSupabase()
            await events.syncFromSupabase()
            
            SyncStatusManager.shared.finishRefresh()
        } catch {
            SyncStatusManager.shared.finishRefresh(error: error.localizedDescription)
        }
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
        SyncStatusManager.shared.startBackup()
        
        do {
            // Güvenlik kontrolü - local verilerin boş olup olmadığını kontrol et
            let hasData = !tags.tags.isEmpty ||
                         !projects.projects.isEmpty ||
                         !tasks.tasks.isEmpty ||
                         !events.events.isEmpty
            
            guard hasData else {
                SyncStatusManager.shared.finishBackup(error: "Local veriler boş, uzak veriler korundu")
                return
            }
            
            // 1) Uzaktaki verileri temizle (FK bağımlılıkları nedeniyle sırayla)
            try await SupabaseService.shared.deleteAllEvents()
            try await SupabaseService.shared.deleteAllTasks()
            try await SupabaseService.shared.deleteAllProjects()
            try await SupabaseService.shared.deleteAllTags()

            // 2) Lokalden sırayla yaz (FK bütünlüğü için önce tag, sonra project, sonra task/event)
            try await SupabaseService.shared.upsertTags(tags.tags)
            try await SupabaseService.shared.upsertProjects(projects.projects)
            try await SupabaseService.shared.upsertTasks(tasks.tasks)
            try await SupabaseService.shared.upsertEvents(events.events)
            
            SyncStatusManager.shared.finishBackup()
        } catch {
            SyncStatusManager.shared.finishBackup(error: error.localizedDescription)
        }
    }
    
    /// Hızlı güncellemeler için - sadece değişen verileri gönder
    public static func incrementalSync(
        tags: TagStore,
        projects: ProjectStore,
        tasks: TaskStore,
        events: EventStore
    ) async {
        // Her store'un değişen verilerini ayrı ayrı gönder
        await withTaskGroup(of: Void.self) { group in
            group.addTask { await tags.backupToSupabase() }
            group.addTask { await projects.backupToSupabase() }
            group.addTask { await tasks.backupToSupabase() }
            group.addTask { await events.backupToSupabase() }
        }
    }
    
    /// Çakışma kontrolü ile güvenli senkronizasyon
    public static func safeSync(
        tags: TagStore,
        projects: ProjectStore,
        tasks: TaskStore,
        events: EventStore,
        forceReplace: Bool = false
    ) async -> Bool {
        SyncStatusManager.shared.startRefresh()
        
        do {
            // Önce uzaktaki verileri çek
            let remoteTags = try await SupabaseService.shared.fetchTags()
            let remoteProjects = try await SupabaseService.shared.fetchProjects()
            let remoteTasks = try await SupabaseService.shared.fetchTasks()
            let remoteEvents = try await SupabaseService.shared.fetchEvents()
            
            // Çakışma kontrolü (basit versiyon - ID'lerin çakışıp çakışmadığını kontrol et)
            let localIds = Set(tags.tags.map(\.id) + projects.projects.map(\.id) +
                             tasks.tasks.map(\.id) + events.events.map(\.id))
            let remoteIds = Set(remoteTags.map(\.id) + remoteProjects.map(\.id) +
                              remoteTasks.map(\.id) + remoteEvents.map(\.id))
            
            let hasConflicts = !localIds.intersection(remoteIds).isEmpty
            
            if hasConflicts && !forceReplace {
                SyncStatusManager.shared.finishRefresh(error: "Veri çakışması tespit edildi")
                return false
            }
            
            // Çakışma yoksa veya zorla güncelleme istenmişse devam et
            if forceReplace {
                await replaceRemoteWithLocal(tags: tags, projects: projects, tasks: tasks, events: events)
            } else {
                await initialPull(tags: tags, projects: projects, tasks: tasks, events: events)
            }
            
            return true
        } catch {
            SyncStatusManager.shared.finishRefresh(error: error.localizedDescription)
            return false
        }
    }
}
