import Foundation

public struct SupabaseConfig { public static var url = ""; public static var anonKey = "" }

public final class SupabaseService {
    public static let shared = SupabaseService(); private init() {}
    private func request(path: String, method: String = "POST", body: Data?) -> URLRequest? {
        guard let base = URL(string: SupabaseConfig.url)?.appendingPathComponent("/rest/v1").appendingPathComponent(path) else { return nil }
        var req = URLRequest(url: base)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("Bearer \(SupabaseConfig.anonKey)", forHTTPHeaderField: "Authorization")
        req.setValue(SupabaseConfig.anonKey, forHTTPHeaderField: "apikey")
        req.setValue("return=minimal", forHTTPHeaderField: "Prefer")
        req.httpBody = body
        return req
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
