import Foundation
import HealthKit

public final class HealthActivityService {
    private let store = HealthStoreManager.shared.store
    public init() {}

    public func fetchTodaySnapshot() async throws -> ActivitySnapshot {
        async let steps   = sumToday(.stepCount, unit: HKUnit.count())
        async let energy  = sumToday(.activeEnergyBurned, unit: HKUnit.kilocalorie())
        async let distM   = sumToday(.distanceWalkingRunning, unit: HKUnit.meter())
        async let hrLatest = latestHeartRate()
        let s  = try await steps
        let e  = try await energy
        let dM = try await distM
        let hr = try await hrLatest
        return ActivitySnapshot(date: Calendar.current.startOfDay(for: Date()),
                                steps: Int(s.rounded()),
                                activeEnergyKcal: e,
                                distanceKm: max(0, dM/1000),
                                latestHeartRateBPM: hr)
    }

    public func stepsLast7Days() async throws -> [StepDay] {
        guard let type = HKObjectType.quantityType(forIdentifier: .stepCount) else { return [] }
        let now = Date()
        let start = Calendar.current.date(byAdding: .day, value: -6, to: Calendar.current.startOfDay(for: now))!
        return try await withCheckedThrowingContinuation { cont in
            var interval = DateComponents(); interval.day = 1
            let q = HKStatisticsCollectionQuery(quantityType: type,
                                                quantitySamplePredicate: HKQuery.predicateForSamples(withStart: start, end: now, options: .strictStartDate),
                                                options: .cumulativeSum,
                                                anchorDate: Calendar.current.startOfDay(for: start),
                                                intervalComponents: interval)
            q.initialResultsHandler = { _, results, error in
                if let error = error { cont.resume(throwing: error); return }
                var arr: [StepDay] = []
                results?.enumerateStatistics(from: start, to: now) { stats, _ in
                    let v = stats.sumQuantity()?.doubleValue(for: HKUnit.count()) ?? 0
                    arr.append(StepDay(date: stats.startDate, steps: Int(v.rounded())))
                }
                cont.resume(returning: arr)
            }
            self.store.execute(q)
        }
    }

    public func energyByDay(weekStart: Date) async throws -> [DayEnergy] {
        guard let type = HKObjectType.quantityType(forIdentifier: .activeEnergyBurned) else { return [] }
        let start = Calendar.current.startOfDay(for: weekStart)
        let end = Calendar.current.date(byAdding: .day, value: 7, to: start)!
        return try await withCheckedThrowingContinuation { cont in
            var interval = DateComponents(); interval.day = 1
            let q = HKStatisticsCollectionQuery(quantityType: type,
                                                quantitySamplePredicate: HKQuery.predicateForSamples(withStart: start, end: end, options: .strictStartDate),
                                                options: .cumulativeSum,
                                                anchorDate: start,
                                                intervalComponents: interval)
            q.initialResultsHandler = { _, results, error in
                if let error = error { cont.resume(throwing: error); return }
                var arr: [DayEnergy] = []
                results?.enumerateStatistics(from: start, to: end) { stats, _ in
                    let kcal = stats.sumQuantity()?.doubleValue(for: HKUnit.kilocalorie()) ?? 0
                    arr.append(DayEnergy(date: stats.startDate, kcal: kcal))
                }
                cont.resume(returning: arr)
            }
            self.store.execute(q)
        }
    }

    public func workouts(weekStart: Date) async throws -> [WorkoutItem] {
        let type = HKObjectType.workoutType()
        let start = Calendar.current.startOfDay(for: weekStart)
        let end = Calendar.current.date(byAdding: .day, value: 7, to: start)!
        let predicate = HKQuery.predicateForSamples(withStart: start, end: end, options: .strictStartDate)
        return try await withCheckedThrowingContinuation { cont in
            let q = HKSampleQuery(sampleType: type, predicate: predicate, limit: HKObjectQueryNoLimit, sortDescriptors: nil) { _, samples, error in
                if let error = error { cont.resume(throwing: error); return }
                let ws = (samples as? [HKWorkout] ?? []).map { w in
                    WorkoutItem(start: w.startDate,
                                end: w.endDate,
                                activity: w.workoutActivityType,
                                durationMin: Int(w.duration/60),
                                energyKcal: w.totalEnergyBurned?.doubleValue(for: HKUnit.kilocalorie()) ?? 0)
                }
                cont.resume(returning: ws)
            }
            self.store.execute(q)
        }
    }

    private func sumToday(_ id: HKQuantityTypeIdentifier, unit: HKUnit) async throws -> Double {
        guard let type = HKObjectType.quantityType(forIdentifier: id) else { return 0 }
        let start = Calendar.current.startOfDay(for: Date())
        return try await withCheckedThrowingContinuation { cont in
            let q = HKStatisticsQuery(quantityType: type,
                                      quantitySamplePredicate: HKQuery.predicateForSamples(withStart: start, end: Date(), options: .strictStartDate),
                                      options: .cumulativeSum) { _, stats, error in
                if let error = error { cont.resume(throwing: error); return }
                let v = stats?.sumQuantity()?.doubleValue(for: unit) ?? 0
                cont.resume(returning: v)
            }
            self.store.execute(q)
        }
    }

    private func latestHeartRate() async throws -> Double? {
        guard let type = HKObjectType.quantityType(forIdentifier: .heartRate) else { return nil }
        return try await withCheckedThrowingContinuation { cont in
            let sort = NSSortDescriptor(key: HKSampleSortIdentifierEndDate, ascending: false)
            let q = HKSampleQuery(sampleType: type, predicate: nil, limit: 1, sortDescriptors: [sort]) { _, samples, error in
                if let error = error { cont.resume(throwing: error); return }
                guard let s = samples?.first as? HKQuantitySample else { cont.resume(returning: nil); return }
                let bpm = s.quantity.doubleValue(for: HKUnit.count().unitDivided(by: HKUnit.minute()))
                cont.resume(returning: bpm)
            }
            self.store.execute(q)
        }
    }
}
