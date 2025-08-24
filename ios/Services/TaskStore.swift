import SwiftUI

public final class TaskStore: ObservableObject {
    @Published public var tasks: [PlannerTask] = []
    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        return dir.appendingPathComponent("tasks.json")
    }()
    
    public init() {
        load()
        setupNotifications()
    }
    
    deinit {
        NotificationCenter.default.removeObserver(self)
    }
    
    private func setupNotifications() {
        NotificationCenter.default.addObserver(
            forName: .dataDidSync,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            // Senkronizasyon sonrası UI güncellemesi için
            self?.objectWillChange.send()
        }
    }

    public func load() {
        guard let data = try? Data(contentsOf: fileURL) else { return }
        if let decoded = try? JSONDecoder().decode([PlannerTask].self, from: data) {
            tasks = decoded
        }
    }

    public func save() {
        if let data = try? JSONEncoder().encode(tasks) {
            try? data.write(to: fileURL)
        }
        
        // Değişiklik bildirimi gönder
        DispatchQueue.main.async {
            NotificationCenter.default.post(name: .tasksDidUpdate, object: self)
        }
    }

    public func syncFromSupabase() async {
        do {
            let remote = try await SupabaseService.shared.fetchTasks()
            await MainActor.run {
                self.tasks = remote
                self.save()
            }
        } catch {
            await MainActor.run {
                print("fetchTasks failed:", error.localizedDescription)
                SyncStatusManager.shared.finishRefresh(error: error.localizedDescription)
            }
        }
    }

    public func backupToSupabase() async {
        do {
            try await SupabaseService.shared.upsertTasks(tasks)
        } catch {
            print("backupTasks failed:", error.localizedDescription)
        }
    }

    public func replaceSupabaseWithLocal() async {
        do {
            try await SupabaseService.shared.replaceTasks(tasks)
        } catch {
            print("replaceTasks failed:", error.localizedDescription)
        }
    }
    
    // Yardımcı fonksiyonlar
    public func addTask(_ task: PlannerTask) {
        tasks.append(task)
        save()
        Task { await backupToSupabase() }
    }
    
    public func updateTask(id: Int, updates: (inout PlannerTask) -> Void) {
        if let index = tasks.firstIndex(where: { $0.id == id }) {
            updates(&tasks[index])
            save()
            Task { await backupToSupabase() }
        }
    }
    
    public func removeTask(id: Int) {
        tasks.removeAll { $0.id == id }
        save()
        Task { await backupToSupabase() }
    }
    
    // Filtreleme yardımcıları
    public func tasks(forStatus status: String) -> [PlannerTask] {
        tasks.filter { normalizeStatus($0.status) == status }
    }

    public func tasks(forTag tag: String) -> [PlannerTask] {
        tasks.filter { $0.tag == tag }
    }

    public func tasks(forProject project: String) -> [PlannerTask] {
        tasks.filter { $0.project == project }
    }
    
    private func normalizeStatus(_ raw: String?) -> String {
        let s = raw?.trimmingCharacters(in: .whitespacesAndNewlines).lowercased() ?? ""
        if ["todo","to-do","to do","backlog","open","not started","not_started","new","ns","bekliyor","yapilacak","yapılacak"].contains(s) {
            return "todo"
        }
        if ["doing","in progress","in_progress","progress","wip","calisiyor","çalışıyor","yapiliyor","yapılıyor"].contains(s) {
            return "doing"
        }
        if ["done","completed","complete","finished","bitti","closed","resolved","tamamlandi","tamamlandı"].contains(s) {
            return "done"
        }
        return "todo"
    }
}
