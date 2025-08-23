import Foundation

public struct PlannerEvent: Identifiable, Codable, Hashable {
    public var id: Int
    public var title: String
    public var start: Date
    public var end: Date
    public var status: String?
    public var tag: String?
    public var project: String?
    public init(id: Int = Int(Date().timeIntervalSince1970),
                title: String,
                start: Date,
                end: Date,
                status: String? = nil,
                tag: String? = nil,
                project: String? = nil) {
        self.id = id
        self.title = title
        self.start = start
        self.end = end
        self.status = status
        self.tag = tag
        self.project = project
    }
}
