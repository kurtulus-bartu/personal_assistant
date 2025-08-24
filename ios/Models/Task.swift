import Foundation

public struct PlannerTask: Identifiable, Codable, Hashable {
    public var id: Int
    public var title: String
    public var status: String?
    public var tagId: Int?
    public var tag: String?
    public var projectId: Int?
    public var project: String?
    public var due: Date?
    public init(id: Int = Int(Date().timeIntervalSince1970),
                title: String,
                status: String? = nil,
                tagId: Int? = nil,
                tag: String? = nil,
                projectId: Int? = nil,
                project: String? = nil,
                due: Date? = nil) {
        self.id = id
        self.title = title
        self.status = status
        self.tagId = tagId
        self.tag = tag
        self.projectId = projectId
        self.project = project
        self.due = due
    }
}
