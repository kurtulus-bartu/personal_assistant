import Foundation
import CoreMotion

public final class MotionService {
    private let pedometer = CMPedometer()
    private var baseline = 0
    public init() {}
    public func isAvailable() -> Bool { CMPedometer.isStepCountingAvailable() }
    public func authorizationStatus() -> CMAuthorizationStatus { CMPedometer.authorizationStatus() }
    public func startDaily(onUpdate: @escaping (Int) -> Void) {
        guard isAvailable() else { return }
        let sod = Calendar.current.startOfDay(for: Date())
        pedometer.queryPedometerData(from: sod, to: Date()) { data, _ in
            DispatchQueue.main.async {
                self.baseline = data?.numberOfSteps.intValue ?? 0
                onUpdate(self.baseline)
                self.pedometer.startUpdates(from: Date()) { d, _ in
                    DispatchQueue.main.async { onUpdate(self.baseline + (d?.numberOfSteps.intValue ?? 0)) }
                }
            }
        }
    }
    public func stop() { pedometer.stopUpdates() }
}
