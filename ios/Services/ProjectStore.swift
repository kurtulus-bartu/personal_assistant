import SwiftUI

public final class ProjectStore: ObservableObject {
    @Published public var projects: [PlannerProject] = []
    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        return dir.appendingPathComponent("projects.json")
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
            self?.objectWillChange.send()
        }
    }

    public func load() {
        guard let data = try? Data(contentsOf: fileURL) else { return }
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .iso8601
        if let decoded = try? decoder.decode([PlannerProject].self, from: data) {
            projects = decoded
        }
    }

    public func save() {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        if let data = try? encoder.encode(projects) {
            try? data.write(to: fileURL)
        }

        DispatchQueue.main.async {
            NotificationCenter.default.post(name: .projectsDidUpdate, object: self)
        }
    }

    public func syncFromSupabase() async {
        do {
            let remote = try await SupabaseService.shared.fetchProjects()
            await MainActor.run {
                self.projects = remote
                self.save()
            }
        } catch {
            await MainActor.run {
                print("fetchProjects failed:", error.localizedDescription)
                SyncStatusManager.shared.finishRefresh(error: error.localizedDescription)
            }
        }
    }

    public func backupToSupabase() async {
        try? await SupabaseService.shared.upsertProjects(projects)
    }

    public func replaceSupabaseWithLocal() async {
        try? await SupabaseService.shared.replaceProjects(projects)
    }
}
