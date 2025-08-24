import Foundation

public struct PlannerTask: Identifiable, Codable, Hashable {
    public var id: Int
    public var title: String
    public var notes: String?
    public var status: String?
    public var tagId: Int?
    public var tag: String?
    public var projectId: Int?
    public var project: String?
    public var due: Date?
    public var start: Date?
    public var end: Date?
    public var hasTime: Bool?
    private static func makeId() -> Int {
        let ms = Int(Date().timeIntervalSince1970 * 1000)
        let rand = Int.random(in: 0..<1000)
        return ms * 1000 + rand
    }
    public init(id: Int = Self.makeId(),
                title: String,
                notes: String? = nil,
                status: String? = nil,
                tagId: Int? = nil,
                tag: String? = nil,
                projectId: Int? = nil,
                project: String? = nil,
                due: Date? = nil,
                start: Date? = nil,
                end: Date? = nil,
                hasTime: Bool? = nil) {
        self.id = id
        self.title = title
        self.notes = notes
        self.status = status
        self.tagId = tagId
        self.tag = tag
        self.projectId = projectId
        self.project = project
        self.due = due
        self.start = start
        self.end = end
        self.hasTime = hasTime
    }
}
