import SwiftUI

public final class EventStore: ObservableObject {
    @Published public var events: [PlannerEvent] = []
    private let fileURL: URL = {
        let dir = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        return dir.appendingPathComponent("events.json")
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
        if let decoded = try? JSONDecoder().decode([PlannerEvent].self, from: data) {
            events = decoded
        }
    }

    public func save() {
        if let data = try? JSONEncoder().encode(events) {
            try? data.write(to: fileURL)
        }

        DispatchQueue.main.async {
            NotificationCenter.default.post(name: .eventsDidUpdate, object: self)
        }
    }

    public func events(for day: Date) -> [PlannerEvent] {
        let cal = Calendar.current
        return events.filter { cal.isDate($0.start, inSameDayAs: day) }
            .sorted { $0.start < $1.start }
    }

    public func move(from offsets: IndexSet, to offset: Int, on day: Date) {
        var daily = events(for: day)
        daily.move(fromOffsets: offsets, toOffset: offset)
        events.removeAll { Calendar.current.isDate($0.start, inSameDayAs: day) }
        events.append(contentsOf: daily)
        save()
    }

    public func syncFromSupabase() async {
        do {
            let remote = try await SupabaseService.shared.fetchEvents()
            await MainActor.run {
                self.events = remote
                self.save()
            }
        } catch {
            await MainActor.run {
                print("fetchEvents failed:", error.localizedDescription)
                SyncStatusManager.shared.finishRefresh(error: error.localizedDescription)
            }
        }
    }

    public func backupToSupabase() async {
        try? await SupabaseService.shared.upsertEvents(events)
    }

    public func replaceSupabaseWithLocal() async {
        try? await SupabaseService.shared.replaceEvents(events)
    }
}
