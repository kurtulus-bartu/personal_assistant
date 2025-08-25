import SwiftUI

public final class TagStore: ObservableObject {
    @Published public var tags: [PlannerTag] = []
    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        return dir.appendingPathComponent("tags.json")
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
        if let decoded = try? decoder.decode([PlannerTag].self, from: data) {
            tags = decoded
        }
    }

    public func save() {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        if let data = try? encoder.encode(tags) {
            try? data.write(to: fileURL)
        }

        DispatchQueue.main.async {
            NotificationCenter.default.post(name: .tagsDidUpdate, object: self)
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
                SyncStatusManager.shared.finishRefresh(error: error.localizedDescription)
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
