import Foundation

public final class WeightStore: ObservableObject {
    @Published public private(set) var entries: [WeightEntry] = []
    public init() { load() }
    private var fileURL: URL { FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!.appendingPathComponent("weights.json") }
    public func addEntry(kg: Double, date: Date = Date()) { entries.append(WeightEntry(date: date, kg: kg)); entries.sort { $0.date < $1.date }; save() }
    private func load() { do { entries = try JSONDecoder().decode([WeightEntry].self, from: Data(contentsOf: fileURL)) } catch { entries = [] } }
    private func save() { do { try JSONEncoder().encode(entries).write(to: fileURL) } catch { print("WeightStore save error:", error) } }
}
