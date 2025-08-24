import SwiftUI

public final class TagStore: ObservableObject {
    @Published public var tags: [PlannerTag] = []
    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        return dir.appendingPathComponent("tags.json")
    }()
    public init() { load() }

    public func load() {
        guard let data = try? Data(contentsOf: fileURL) else { return }
        if let decoded = try? JSONDecoder().decode([PlannerTag].self, from: data) {
            tags = decoded
        }
    }

    public func save() {
        if let data = try? JSONEncoder().encode(tags) {
            try? data.write(to: fileURL)
        }
    }

    public func syncFromSupabase() async {
        do {
            let remote = try await SupabaseService.shared.fetchTags()
            await MainActor.run {
                self.tags = remote
                self.save()
            }
        } catch {
            await MainActor.run {
                print("fetchTags failed:", error.localizedDescription)
            }
        }
    }

    public func backupToSupabase() async {
        try? await SupabaseService.shared.upsertTags(tags)
    }

    public func replaceSupabaseWithLocal() async {
        try? await SupabaseService.shared.replaceTags(tags)
    }
}
