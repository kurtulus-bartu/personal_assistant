import SwiftUI

public final class TaskStore: ObservableObject {
    @Published public var tasks: [PlannerTask] = []
    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        return dir.appendingPathComponent("tasks.json")
    }()
    public init() { load() }

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
    }

    public func syncFromSupabase() async {
        if let remote = try? await SupabaseService.shared.fetchTasks() {
            DispatchQueue.main.async {
                self.tasks = remote
                self.save()
            }
        }
    }

    public func backupToSupabase() async {
        try? await SupabaseService.shared.upsertTasks(tasks)
    }
    public func replaceSupabaseWithLocal() async {
        try? await SupabaseService.shared.replaceTasks(tasks)
    }
}
