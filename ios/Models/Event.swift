import Foundation

private func makeId() -> Int {
    let ms = Int(Date().timeIntervalSince1970 * 1000)
    let r  = Int.random(in: 0..<1000)
    return ms * 1000 + r
}

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

    public init(
        id: Int? = nil,
        title: String,
        start: Date,
        end: Date,
        status: String? = nil,
        notes: String? = nil,
        tagId: Int? = nil,
        tag: String? = nil,
        projectId: Int? = nil,
        project: String? = nil
    ) {
        self.id = id ?? makeId()
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
