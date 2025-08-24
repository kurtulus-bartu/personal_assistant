import Foundation

public struct PlannerEvent: Identifiable, Codable, Hashable {
    public var id: Int
    public var title: String
    public var start: Date
    public var end: Date
    public var status: String?
    public var notes: String?
    public var tagId: Int?
    public var tag: String?
    public var projectId: Int?
    public var project: String?
    public init(id: Int = Int(Date().timeIntervalSince1970),
                title: String,
                start: Date,
                end: Date,
                status: String? = nil,
                notes: String? = nil,
                tagId: Int? = nil,
                tag: String? = nil,
                projectId: Int? = nil,
                project: String? = nil) {
        self.id = id
        self.title = title
        self.start = start
        self.end = end
        self.status = status
        self.notes = notes
        self.tagId = tagId
        self.tag = tag
        self.projectId = projectId
        self.project = project
    }
}
