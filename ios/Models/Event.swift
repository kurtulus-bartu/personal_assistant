import Foundation

public struct PlannerEvent: Identifiable, Codable, Hashable {
    public var id: UUID
    public var title: String
    public var start: Date
    public var end: Date
    public var status: String?
    public init(id: UUID = UUID(), title: String, start: Date, end: Date, status: String? = nil) {
        self.id = id
        self.title = title
        self.start = start
        self.end = end
        self.status = status
    }
}
