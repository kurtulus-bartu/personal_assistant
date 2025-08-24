import Foundation

public struct PlannerProject: Identifiable, Codable, Hashable {
    public var id: Int
    public var name: String
    public var tagId: Int?
    public var createdAt: Date?
    public var updatedAt: Date?
    public init(id: Int, name: String, tagId: Int? = nil, createdAt: Date? = nil, updatedAt: Date? = nil) {
        self.id = id
        self.name = name
        self.tagId = tagId
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
    enum CodingKeys: String, CodingKey {
        case id, name
        case tagId = "tag_id"
        case createdAt = "created_at"
        case updatedAt = "updated_at"
    }
}
