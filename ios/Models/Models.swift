import Foundation
import HealthKit

public struct ActivitySnapshot: Equatable {
    public var date: Date
    public var steps: Int
    public var activeEnergyKcal: Double
    public var distanceKm: Double
    public var latestHeartRateBPM: Double?
}

public struct DayEnergy: Identifiable, Hashable {
    public let id = UUID()
    public let date: Date
    public let kcal: Double
}

public struct WorkoutItem: Identifiable, Hashable {
    public let id = UUID()
    public let start: Date
    public let end: Date
    public let activity: HKWorkoutActivityType
    public let durationMin: Int
    public let energyKcal: Double
}

public struct WeekMenu: Identifiable, Hashable {
    public let id = UUID()
    public let weekStart: Date
    public var days: [MenuDay]
}

public struct MenuDay: Identifiable, Hashable {
    public let id = UUID()
    public let date: Date
    public var breakfast: String
    public var lunch: String
    public var dinner: String
}

public struct StepDay: Identifiable, Hashable {
    public let id = UUID()
    public let date: Date
    public let steps: Int
}

public struct WeightEntry: Codable, Identifiable, Equatable {
    public let id: UUID
    public let date: Date
    public let kg: Double
    public init(date: Date, kg: Double) { self.id = UUID(); self.date = date; self.kg = kg }
}

public struct Advice: Identifiable, Equatable {
    public let id = UUID()
    public let title: String
    public let details: String
    public let category: Category
    public enum Category { case nutrition, exercise, lifestyle }
}
