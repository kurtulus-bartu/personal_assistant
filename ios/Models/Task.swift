import Foundation

public struct PlannerTask: Identifiable, Codable, Hashable {
    public var id: Int
    public var title: String
    public var status: String?
    public var tag: String?
    public var project: String?
    public init(id: Int = Int(Date().timeIntervalSince1970),
                title: String,
                status: String? = nil,
                tag: String? = nil,
                project: String? = nil) {
        self.id = id
        self.title = title
        self.status = status
        self.tag = tag
        self.project = project
    }
}
