import Foundation
import HealthKit

public final class HealthStoreManager: ObservableObject {
    public static let shared = HealthStoreManager()
    public let store = HKHealthStore()
    private init() {}

    public var readTypes: Set<HKObjectType> {
        var s = Set<HKObjectType>()
        for id in [.stepCount, .activeEnergyBurned, .distanceWalkingRunning, .heartRate] as [HKQuantityTypeIdentifier] {
            if let t = HKObjectType.quantityType(forIdentifier: id) { s.insert(t) }
        }
        s.insert(HKObjectType.workoutType())
        return s
    }

    public func requestAuthorization() async throws -> Bool {
        try await withCheckedThrowingContinuation { c in
            store.requestAuthorization(toShare: [], read: readTypes) { ok, err in
                if let err = err { c.resume(throwing: err) } else { c.resume(returning: ok) }
            }
        }
    }
}
