import Foundation

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
        req.setValue("return=minimal", forHTTPHeaderField: "Prefer")
        req.httpBody = body
        return req
    }
    public func fetchEvents() async throws -> [PlannerEvent] {
        guard let req = request(path: "events?select=*", method: "GET") else { return [] }
        let (data, _) = try await URLSession.shared.data(for: req)
        let dec = JSONDecoder(); dec.dateDecodingStrategy = .iso8601
        return try dec.decode([PlannerEvent].self, from: data)
    }
    public func upsertEvents(_ items: [PlannerEvent]) async throws {
        let enc = JSONEncoder(); enc.dateEncodingStrategy = .iso8601
        let data = try enc.encode(items)
        if let req = request(path: "events", body: data) {
            _ = try await URLSession.shared.data(for: req)
        }
    }
    public func uploadWeeklyEnergy(userId: String, items: [DayEnergy]) async {
        let rows: [[String: Any]] = items.map { [
            "user_id": userId,
            "type": "activeEnergyBurned",
            "start_at": ISO8601DateFormatter().string(from: $0.date),
            "end_at": ISO8601DateFormatter().string(from: Calendar.current.date(byAdding: .day, value: 1, to: $0.date)!),
            "value_numeric": $0.kcal,
            "unit": "kcal"
        ]}
        do { let data = try JSONSerialization.data(withJSONObject: rows)
            if let req = request(path: "health_samples", body: data) { _ = try await URLSession.shared.data(for: req) }
        } catch { print("Supabase upload error:", error) }
    }
}
