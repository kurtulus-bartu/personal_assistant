import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

// Supabase backend configuration used by the app. The URL and anon key are
// the same values defined in the Python `services/supabase_api.py` helper so
// both clients talk to the same project.
public struct SupabaseConfig {
    public static var url = "https://mfxykkgmsfqipmqpwnoj.supabase.co"
    public static var anonKey = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im1meHlra2dtc2ZxaXBtcXB3bm9qIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQ5NDgwNDIsImV4cCI6MjA3MDUyNDA0Mn0.2bbS-4khj1oFkEz-GsICBS15Nl1d-HVldxvE-nsYbLE"
}

public final class SupabaseService {
    public static let shared = SupabaseService(); private init() {}
    private func request(path: String, method: String = "POST", body: Data? = nil) -> URLRequest? {
        guard let url = URL(string: "\(SupabaseConfig.url)/rest/v1/\(path)") else { return nil }
        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(SupabaseConfig.anonKey)", forHTTPHeaderField: "Authorization")
        req.setValue(SupabaseConfig.anonKey, forHTTPHeaderField: "apikey")
        req.setValue("return=minimal,resolution=merge-duplicates", forHTTPHeaderField: "Prefer")
        req.httpBody = body
        return req
    }

    // MARK: Tags
    public func fetchTags() async throws -> [PlannerTag] {
        guard let req = request(path: "tags?select=*", method: "GET") else { return [] }
        let (data, _) = try await URLSession.shared.data(for: req)
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        return try dec.decode([PlannerTag].self, from: data)
    }

    public func upsertTags(_ items: [PlannerTag]) async throws {
        struct Row: Codable { var id: Int; var name: String }
        let rows = items.map { Row(id: $0.id, name: $0.name) }
        let data = try JSONEncoder().encode(rows)
        if let req = request(path: "tags?on_conflict=id", body: data) {
            _ = try await URLSession.shared.data(for: req)
        }
    }

    public func deleteAllTags() async throws {
        if let req = request(path: "tags", method: "DELETE") {
            _ = try await URLSession.shared.data(for: req)
        }
    }

    public func replaceTags(_ items: [PlannerTag]) async throws {
        try await deleteAllTags()
        try await upsertTags(items)
    }

    // MARK: Projects
    public func fetchProjects() async throws -> [PlannerProject] {
        guard let req = request(path: "projects?select=*", method: "GET") else { return [] }
        let (data, _) = try await URLSession.shared.data(for: req)
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        return try dec.decode([PlannerProject].self, from: data)
    }

    public func upsertProjects(_ items: [PlannerProject]) async throws {
        struct Row: Codable { var id: Int; var name: String; var tag_id: Int? }
        let rows = items.map { Row(id: $0.id, name: $0.name, tag_id: $0.tagId) }
        let data = try JSONEncoder().encode(rows)
        if let req = request(path: "projects?on_conflict=id", body: data) {
            _ = try await URLSession.shared.data(for: req)
        }
    }

    public func deleteAllProjects() async throws {
        if let req = request(path: "projects", method: "DELETE") {
            _ = try await URLSession.shared.data(for: req)
        }
    }

    public func replaceProjects(_ items: [PlannerProject]) async throws {
        try await deleteAllProjects()
        try await upsertProjects(items)
    }

    // MARK: Tasks
    public func fetchTasks() async throws -> [PlannerTask] {
        let fields = "id,title,notes,status,tag_id,tag:tags(name),project_id,project:projects(name),parent_id,parent:tasks!tasks_parent_id_fkey(title),has_time,due_date,start_ts,end_ts"
        let path = "tasks?select=\(fields)"
        guard let req = request(path: path, method: "GET") else { return [] }
        let (data, _) = try await URLSession.shared.data(for: req)
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        struct TaskRow: Codable {
            let id: Int
            let title: String
            let notes: String?
            let status: String?
            let tag_id: Int?
            let tag: NameHolder?
            let project_id: Int?
            let project: NameHolder?
            let parent_id: Int?
            let parent: NameHolder?
            let has_time: Bool?
            let due_date: String?
            let start_ts: Date?
            let end_ts: Date?
            struct NameHolder: Codable { let name: String }
        }
        let rows = try dec.decode([TaskRow].self, from: data)
        let df = ISO8601DateFormatter(); df.formatOptions = [.withFullDate]
        return rows.map { r in
            let due = r.due_date.flatMap { df.date(from: $0) }
            return PlannerTask(id: r.id,
                               title: r.title,
                               notes: r.notes,
                               status: r.status,
                               tagId: r.tag_id,
                               tag: r.tag?.name,
                               projectId: r.project_id,
                               project: r.project?.name,
                               parentId: r.parent_id,
                               parent: r.parent?.name,
                               due: due,
                               start: r.start_ts,
                               end: r.end_ts,
                               hasTime: r.has_time)
        }
    }
    public func upsertTasks(_ items: [PlannerTask]) async throws {
        struct UpsertTask: Codable {
            var id: Int?
            var title: String
            var notes: String?
            var status: String?
            var has_time: Bool
            var tag_id: Int?
            var project_id: Int?
            var parent_id: Int?
            var due_date: String?
            var start_ts: Date?
            var end_ts: Date?
        }
        let df = ISO8601DateFormatter(); df.formatOptions = [.withFullDate]
        let rows = items.map { t in
            UpsertTask(id: t.id,
                       title: t.title,
                       notes: t.notes,
                       status: t.status,
                       has_time: t.hasTime ?? false,
                       tag_id: t.tagId,
                       project_id: t.projectId,
                       parent_id: t.parentId,
                       due_date: t.due.map { df.string(from: $0) },
                       start_ts: t.start,
                       end_ts: t.end)
        }
        let enc = JSONEncoder(); enc.dateEncodingStrategy = .iso8601
        let data = try enc.encode(rows)
        if let req = request(path: "tasks?on_conflict=id", body: data) {
            _ = try await URLSession.shared.data(for: req)
        }
    }

    public func deleteAllTasks() async throws {
        if let req = request(path: "tasks", method: "DELETE") {
            _ = try await URLSession.shared.data(for: req)
        }
    }
    public func replaceTasks(_ items: [PlannerTask]) async throws {
        try await deleteAllTasks()
        try await upsertTasks(items)
    }

    // MARK: Other
    public func uploadWeeklyEnergy(userId: String, items: [DayEnergy]) async {
        let rows: [[String: Any]] = items.map { [
            "user_id": userId,
            "type": "activeEnergyBurned",
            "start_at": ISO8601DateFormatter().string(from: $0.date),
            "value": $0.kcal,
            "duration_sec": 86400
        ] }
        if let data = try? JSONSerialization.data(withJSONObject: rows),
           let req = request(path: "health_data", body: data) {
            _ = try? await URLSession.shared.data(for: req)
        }
    }
}
