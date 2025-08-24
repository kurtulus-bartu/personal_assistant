import SwiftUI

public final class ProjectStore: ObservableObject {
    @Published public var projects: [PlannerProject] = []
    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        return dir.appendingPathComponent("projects.json")
    }()
    public init() { load() }

    public func load() {
        guard let data = try? Data(contentsOf: fileURL) else { return }
        if let decoded = try? JSONDecoder().decode([PlannerProject].self, from: data) {
            projects = decoded
        }
    }

    public func save() {
        if let data = try? JSONEncoder().encode(projects) {
            try? data.write(to: fileURL)
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
