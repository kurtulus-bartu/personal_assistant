import Foundation

private func makeId() -> Int {
    let ms = Int(Date().timeIntervalSince1970 * 1000)
    let r  = Int.random(in: 0..<1000)
    return ms * 1000 + r
}

public struct PlannerTask: Identifiable, Codable, Hashable {
    public var id: Int
    public var title: String
    public var notes: String?
    public var status: String?
    public var tagId: Int?
    public var tag: String?
    public var projectId: Int?
    public var project: String?
    public var parentId: Int?
    public var parent: String?
    public var due: Date?
    public var start: Date?
    public var end: Date?
    public var hasTime: Bool?
    public init(
        id: Int? = nil,
        title: String,
        notes: String? = nil,
        status: String? = nil,
        tagId: Int? = nil,
        tag: String? = nil,
        projectId: Int? = nil,
        project: String? = nil,
        parentId: Int? = nil,
        parent: String? = nil,
        due: Date? = nil,
        start: Date? = nil,
        end: Date? = nil,
        hasTime: Bool? = nil
    ) {
        self.id = id ?? makeId()
        self.title = title
        self.notes = notes
        self.status = status
        self.tagId = tagId
        self.tag = tag
        self.projectId = projectId
        self.project = project
        self.parentId = parentId
        self.parent = parent
        self.due = due
        self.start = start
        self.end = end
        self.hasTime = hasTime
    }

    enum CodingKeys: String, CodingKey {
        case id, title, notes, status, tag, project, parent
        case tagId = "tag_id"
        case projectId = "project_id"
        case parentId = "parent_id"
        case hasTime = "has_time"
        case due = "due_date"
        case start = "start_ts"
        case end = "end_ts"
    }
}
